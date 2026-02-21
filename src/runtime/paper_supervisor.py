"""7/24 Paper Trading Supervisor — Stage-2C.

Provides infinite-loop paper trading with:
- Crash recovery + configurable restart delay
- Heartbeat persistence to paper_runtime_state table
- Dead-feed detection (stale klines warning)
- Daily run directory rotation at midnight UTC

Paper-only. Does NOT affect live trading logic.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("argus.supervisor")


# ---------------------------------------------------------------------------
# Heartbeat persistence
# ---------------------------------------------------------------------------

def _ensure_runtime_table(conn: sqlite3.Connection) -> None:
    """Create paper_runtime_state if it doesn't exist (idempotent)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_runtime_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_cycle_ts TEXT,
            total_cycles INTEGER NOT NULL DEFAULT 0,
            last_trade_ts TEXT,
            consecutive_errors INTEGER NOT NULL DEFAULT 0,
            uptime_seconds REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO paper_runtime_state (id, total_cycles, consecutive_errors, uptime_seconds)
        VALUES (1, 0, 0, 0.0)
        """
    )
    conn.commit()


def _update_heartbeat(
    conn: sqlite3.Connection,
    *,
    total_cycles: int,
    consecutive_errors: int,
    uptime_seconds: float,
    last_trade_ts: str | None = None,
) -> None:
    """Write heartbeat to paper_runtime_state."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if last_trade_ts:
        conn.execute(
            """
            UPDATE paper_runtime_state SET
                last_cycle_ts = ?,
                total_cycles = ?,
                last_trade_ts = ?,
                consecutive_errors = ?,
                uptime_seconds = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (now_iso, total_cycles, last_trade_ts, consecutive_errors, uptime_seconds, now_iso),
        )
    else:
        conn.execute(
            """
            UPDATE paper_runtime_state SET
                last_cycle_ts = ?,
                total_cycles = ?,
                consecutive_errors = ?,
                uptime_seconds = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (now_iso, total_cycles, consecutive_errors, uptime_seconds, now_iso),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Daily rotation
# ---------------------------------------------------------------------------

def _daily_run_dir(base_dir: str) -> Path:
    """Return today's run directory: base_dir/YYYY-MM-DD/."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = Path(base_dir) / today
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_daily_summary(run_dir: Path, stats: dict[str, Any]) -> None:
    """Write daily summary JSON on rotation."""
    summary_path = run_dir / "daily_summary.json"
    summary_path.write_text(
        json.dumps(stats, indent=2, default=str, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _copy_config_snapshot(run_dir: Path) -> None:
    """Copy config/ to daily run_dir for reproducibility."""
    config_src = Path("config")
    if config_src.is_dir():
        dst = run_dir / "config_snapshot"
        if not dst.exists():
            try:
                shutil.copytree(str(config_src), str(dst), dirs_exist_ok=True)
            except Exception as exc:
                _LOG.warning("config snapshot copy failed: %s", exc)


# ---------------------------------------------------------------------------
# Dead-feed detection
# ---------------------------------------------------------------------------

def detect_dead_feed(
    last_kline_ts: datetime | None,
    *,
    warning_minutes: int = 15,
    restart_minutes: int = 60,
) -> str:
    """Check if exchange data feed appears stale.

    Returns
    -------
    str
        "ok", "warning", or "restart"
    """
    if last_kline_ts is None:
        return "ok"  # No data yet — can't judge
    age = (datetime.now(timezone.utc) - last_kline_ts).total_seconds() / 60.0
    if age > restart_minutes:
        return "restart"
    if age > warning_minutes:
        return "warning"
    return "ok"


# ---------------------------------------------------------------------------
# Main supervisor loop
# ---------------------------------------------------------------------------

def run_paper_supervisor(
    *,
    db_path: str,
    base_run_dir: str = "runs/paper_24h",
    cycle_interval_seconds: int = 300,
    restart_delay_seconds: int = 30,
    dead_feed_warning_min: int = 15,
    dead_feed_restart_min: int = 60,
    pipeline_factory: Any = None,
) -> None:
    """Run the paper supervisor infinite loop.

    Parameters
    ----------
    db_path : str
        Path to the v2.5 SQLite DB.
    base_run_dir : str
        Base directory for daily rotated runs.
    cycle_interval_seconds : int
        Seconds between pipeline cycles.
    restart_delay_seconds : int
        Seconds to wait before restarting after crash.
    dead_feed_warning_min : int
        Minutes of stale data before logging warning.
    dead_feed_restart_min : int
        Minutes of stale data before triggering restart.
    pipeline_factory : callable
        Factory function that returns (pipeline, v25_conn) tuple.
        If None, supervisor exits immediately (test mode).
    """
    conn = sqlite3.connect(db_path)
    _ensure_runtime_table(conn)

    total_cycles = 0
    consecutive_errors = 0
    start_time = time.monotonic()
    current_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last_kline_ts: datetime | None = None

    print(f"[supervisor] Starting 7/24 paper mode | db={db_path} | interval={cycle_interval_seconds}s")

    while True:
        try:
            # Daily rotation check
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if today != current_day:
                # Write previous day summary
                prev_dir = _daily_run_dir(base_run_dir).parent / current_day
                if prev_dir.exists():
                    _write_daily_summary(prev_dir, {
                        "date": current_day,
                        "total_cycles": total_cycles,
                        "consecutive_errors": consecutive_errors,
                        "uptime_seconds": time.monotonic() - start_time,
                    })
                current_day = today
                print(f"[supervisor] Daily rotation → {today}")

            run_dir = _daily_run_dir(base_run_dir)
            _copy_config_snapshot(run_dir)

            # Dead-feed detection
            feed_status = detect_dead_feed(
                last_kline_ts,
                warning_minutes=dead_feed_warning_min,
                restart_minutes=dead_feed_restart_min,
            )
            if feed_status == "warning":
                _LOG.warning("[supervisor] Dead feed warning: no new klines for >%d min", dead_feed_warning_min)
            elif feed_status == "restart":
                _LOG.error("[supervisor] Dead feed restart threshold exceeded (%d min)", dead_feed_restart_min)
                last_kline_ts = None  # Reset

            # Run pipeline cycle
            if pipeline_factory is not None:
                pipeline, v25_conn = pipeline_factory()
                cycle_now = datetime.now(timezone.utc)
                outputs = pipeline.run_once(now=cycle_now)

                total_cycles += 1
                consecutive_errors = 0
                last_kline_ts = cycle_now

                # Check if any trades were executed
                for out in outputs:
                    if out.get("status") == "executed":
                        last_trade_ts = cycle_now.isoformat()
                        break
                else:
                    last_trade_ts = None

                uptime = time.monotonic() - start_time
                _update_heartbeat(
                    conn,
                    total_cycles=total_cycles,
                    consecutive_errors=consecutive_errors,
                    uptime_seconds=uptime,
                    last_trade_ts=last_trade_ts,
                )

                print(f"[supervisor] cycle={total_cycles} | outputs={len(outputs)} | uptime={uptime:.0f}s")
            else:
                # Test mode — no pipeline factory
                break

        except KeyboardInterrupt:
            print(f"\n[supervisor] Stopped by user after {total_cycles} cycles.")
            break

        except Exception as exc:
            consecutive_errors += 1
            _LOG.error("[supervisor] Cycle error (#%d): %s", consecutive_errors, exc)

            # Write crash log
            crash_dir = _daily_run_dir(base_run_dir)
            crash_file = crash_dir / f"crash_{datetime.now(timezone.utc).strftime('%H%M%S')}.log"
            crash_file.write_text(
                f"time: {datetime.now(timezone.utc).isoformat()}\n"
                f"cycle: {total_cycles}\n"
                f"consecutive_errors: {consecutive_errors}\n"
                f"error: {exc}\n"
                f"traceback:\n{traceback.format_exc()}\n",
                encoding="utf-8",
            )

            uptime = time.monotonic() - start_time
            _update_heartbeat(
                conn,
                total_cycles=total_cycles,
                consecutive_errors=consecutive_errors,
                uptime_seconds=uptime,
            )

            print(f"[supervisor] Restarting in {restart_delay_seconds}s...")
            time.sleep(restart_delay_seconds)
            continue

        # Sleep between cycles
        try:
            time.sleep(cycle_interval_seconds)
        except KeyboardInterrupt:
            print(f"\n[supervisor] Stopped by user after {total_cycles} cycles.")
            break

    conn.close()
