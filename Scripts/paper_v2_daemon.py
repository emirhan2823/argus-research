"""ARGUS v2 Paper Trading Daemon.

Continuously runs the v2 pipeline (src/main.py ArgusPipeline) in a loop,
collecting data, executing paper trades, and building telemetry logs for
post-mortem analysis and learning pipeline integration.

Usage:
    python Scripts/paper_v2_daemon.py [--interval 60] [--assets crypto] [--v25]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "runs" / "paper_v2_daemon.log", encoding="utf-8"),
    ],
)
LOG = logging.getLogger("argus.paper_daemon_v2")

# ---------------------------------------------------------------------------
# Heartbeat / Metrics writers
# ---------------------------------------------------------------------------

def _write_json_atomic(path: Path, data: dict) -> None:
    """Write JSON atomically (write to .tmp, then replace)."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        LOG.debug("atomic write failed for %s", path, exc_info=True)


class DaemonMetrics:
    """Accumulates run-level metrics for monitoring."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = datetime.now(timezone.utc)
        self.cycles = 0
        self.signals_generated = 0
        self.trades_filled = 0
        self.trades_rejected = 0
        self.errors = 0
        self.last_cycle_time: float = 0.0
        self.decisions_log = run_dir / "decisions.jsonl"
        self.heartbeat_path = run_dir / "heartbeat.json"
        self.metrics_path = run_dir / "metrics.json"
        # Engine-level monitoring
        self.engine_signals: dict[str, int] = {}
        self.engine_fills: dict[str, int] = {}
        self.engine_rejects: dict[str, int] = {}
        self.regime_activity: dict[str, int] = {}
        self.rejection_reasons: dict[str, int] = {}
        self.engine_pnl: dict[str, float] = {}

    def record_cycle(self, outputs: list[dict], elapsed: float) -> None:
        self.cycles += 1
        self.last_cycle_time = elapsed
        for out in outputs:
            action = out.get("action", "")
            engine = out.get("engine", "UNKNOWN")
            regime = out.get("v6_regime", out.get("regime", "UNKNOWN"))
            reason = out.get("reason", "")

            if action == "fill":
                self.trades_filled += 1
                self.signals_generated += 1
                self.engine_fills[engine] = self.engine_fills.get(engine, 0) + 1
                pnl = float(out.get("pnl_pct", 0))
                self.engine_pnl[engine] = self.engine_pnl.get(engine, 0.0) + pnl
            elif action == "reject":
                self.trades_rejected += 1
                self.engine_rejects[engine] = self.engine_rejects.get(engine, 0) + 1
                self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
            elif action in ("advisory", "signal"):
                self.signals_generated += 1
                self.engine_signals[engine] = self.engine_signals.get(engine, 0) + 1

            # Track regime activity
            if regime and regime != "UNKNOWN":
                self.regime_activity[regime] = self.regime_activity.get(regime, 0) + 1

            # Log every decision
            with open(self.decisions_log, "a", encoding="utf-8") as f:
                out["_cycle"] = self.cycles
                out["_ts"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(out, default=str) + "\n")

    def record_error(self) -> None:
        self.errors += 1

    def write_heartbeat(self) -> None:
        uptime_s = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        _write_json_atomic(self.heartbeat_path, {
            "status": "RUNNING",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": round(uptime_s, 1),
            "cycles": self.cycles,
            "last_cycle_seconds": round(self.last_cycle_time, 2),
            "signals": self.signals_generated,
            "fills": self.trades_filled,
            "rejects": self.trades_rejected,
            "errors": self.errors,
        })

    def write_metrics(self) -> None:
        uptime_s = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        _write_json_atomic(self.metrics_path, {
            "daemon_start": self.start_time.isoformat(),
            "now": datetime.now(timezone.utc).isoformat(),
            "uptime_hours": round(uptime_s / 3600, 2),
            "total_cycles": self.cycles,
            "avg_cycle_time": round(uptime_s / max(self.cycles, 1), 2),
            "signals_generated": self.signals_generated,
            "trades_filled": self.trades_filled,
            "trades_rejected": self.trades_rejected,
            "errors": self.errors,
            "fill_rate": round(self.trades_filled / max(self.signals_generated, 1), 4),
            # Engine-level monitoring
            "engine_signals": dict(sorted(self.engine_signals.items())),
            "engine_fills": dict(sorted(self.engine_fills.items())),
            "engine_rejects": dict(sorted(self.engine_rejects.items())),
            "engine_pnl": {k: round(v, 4) for k, v in sorted(self.engine_pnl.items())},
            "regime_activity": dict(sorted(self.regime_activity.items())),
            "top_rejection_reasons": dict(sorted(
                self.rejection_reasons.items(), key=lambda x: x[1], reverse=True
            )[:10]),
        })


# ---------------------------------------------------------------------------
# Reflector integration (post-trade learning)
# ---------------------------------------------------------------------------

def _maybe_run_reflector(outputs: list[dict], cycle: int) -> None:
    """Run the Reflector on completed trades for self-improvement telemetry."""
    try:
        from src.learning.reflector import Reflector, TradeContext
    except ImportError:
        return  # Reflector not available

    fills = [o for o in outputs if o.get("action") == "fill"]
    if not fills:
        return

    try:
        reflector = Reflector()
        for fill in fills:
            ctx = TradeContext(
                trade_id=fill.get("trade_id", f"paper_{cycle}_{fill.get('symbol', 'UNK')}"),
                symbol=fill.get("symbol", "UNKNOWN"),
                side=fill.get("side", "long"),
                entry_price=float(fill.get("entry_price", 0)),
                exit_price=float(fill.get("exit_price", fill.get("entry_price", 0))),
                sl_price=float(fill.get("sl_price", 0)),
                pnl_pct=float(fill.get("pnl_pct", 0)),
                regime=fill.get("regime", "UNKNOWN"),
                regime_confidence=float(fill.get("regime_confidence", 0.5)),
                engine=fill.get("engine", "UNKNOWN"),
                hermes_sentiment=float(fill.get("hermes_sentiment", 0)),
                adx_14=float(fill.get("adx_14", 20)),
                rsi_14=float(fill.get("rsi_14", 50)),
                atr_14_pct=float(fill.get("atr_14_pct", 0.02)),
            )
            reflector.reflect(ctx)
            LOG.info("Reflector processed trade %s", ctx.trade_id)
    except Exception:
        LOG.debug("Reflector failed", exc_info=True)


# ---------------------------------------------------------------------------
# Main daemon loop
# ---------------------------------------------------------------------------

_SHUTDOWN = False

def _signal_handler(sig, frame):
    global _SHUTDOWN
    LOG.info("Shutdown signal received (%s). Completing current cycle...", sig)
    _SHUTDOWN = True


def run_daemon(
    mode: str = "paper",
    assets: list[str] | None = None,
    interval_seconds: int = 60,
    v25: bool = True,
    v25_db: str = "runs/v25/argus_v25.db",
    run_dir: str = "runs/paper_v2",
) -> None:
    """Run the v2 pipeline continuously in paper mode."""

    global _SHUTDOWN
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if assets is None:
        assets = ["crypto"]

    run_path = PROJECT_ROOT / run_dir
    metrics = DaemonMetrics(run_path)

    # --- v2.5 bootstrap ---
    v25_conn = None
    if v25:
        try:
            from src.v25.bootstrap import load_v25_config, run_v25_migrations
            os.makedirs(os.path.dirname(v25_db) or ".", exist_ok=True)
            v25_cfg = load_v25_config()
            v25_conn = run_v25_migrations(v25_db)
            LOG.info("[v25] Bootstrap OK | db=%s", v25_db)
        except Exception as exc:
            LOG.error("[v25] Bootstrap FAILED: %s", exc)
            v25 = False

    # --- Create pipeline ---
    from src.main import ArgusPipeline
    pipeline = ArgusPipeline(
        mode=mode,
        assets=assets,
        evolve=False,
        time_machine_dir="data/time_machine",
        v25_conn=v25_conn,
    )

    LOG.info("=" * 60)
    LOG.info("ARGUS v2 Paper Trading Daemon")
    LOG.info("  Mode:     %s", mode)
    LOG.info("  Assets:   %s", ", ".join(assets))
    LOG.info("  Interval: %ds", interval_seconds)
    LOG.info("  v2.5:     %s", "ON" if v25 else "OFF")
    LOG.info("  Run dir:  %s", run_path)
    LOG.info("=" * 60)

    cycle = 0
    while not _SHUTDOWN:
        cycle += 1
        t0 = time.time()

        try:
            LOG.info("[Cycle %d] Starting pipeline run...", cycle)
            outputs = pipeline.run_once()
            elapsed = time.time() - t0

            metrics.record_cycle(outputs, elapsed)

            # Log summary with engine breakdown
            fills = sum(1 for o in outputs if o.get("action") == "fill")
            rejects = sum(1 for o in outputs if o.get("action") == "reject")
            advisories = [o for o in outputs if o.get("action") in ("advisory", "signal")]
            engine_summary = {}
            for o in advisories:
                eng = o.get("engine", "?")
                engine_summary[eng] = engine_summary.get(eng, 0) + 1
            eng_str = " ".join(f"{k}={v}" for k, v in sorted(engine_summary.items())) if engine_summary else "none"
            LOG.info(
                "[Cycle %d] Done in %.1fs | signals=%d fills=%d rejects=%d | engines: %s",
                cycle, elapsed, len(outputs), fills, rejects, eng_str,
            )

            # Post-trade reflection (learning)
            _maybe_run_reflector(outputs, cycle)

        except Exception:
            elapsed = time.time() - t0
            metrics.record_error()
            LOG.error("[Cycle %d] Pipeline error after %.1fs", cycle, elapsed, exc_info=True)
            # Write error to file
            err_path = run_path / "errors.log"
            with open(err_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n[Cycle {cycle}] {datetime.now(timezone.utc).isoformat()}\n")
                traceback.print_exc(file=f)

        # Write heartbeat + metrics every cycle
        metrics.write_heartbeat()
        if cycle % 10 == 0:
            metrics.write_metrics()

        # Sleep until next interval
        elapsed = time.time() - t0
        sleep_time = max(0, interval_seconds - elapsed)
        if sleep_time > 0 and not _SHUTDOWN:
            LOG.debug("Sleeping %.1fs until next cycle...", sleep_time)
            # Sleep in small chunks so we can respond to SIGINT quickly
            sleep_end = time.time() + sleep_time
            while time.time() < sleep_end and not _SHUTDOWN:
                time.sleep(min(1.0, sleep_end - time.time()))

    # Final metrics dump
    metrics.write_metrics()
    LOG.info("Daemon stopped after %d cycles.", cycle)
    LOG.info("Final metrics: fills=%d rejects=%d errors=%d",
             metrics.trades_filled, metrics.trades_rejected, metrics.errors)

    # Mark heartbeat as stopped
    _write_json_atomic(metrics.heartbeat_path, {
        "status": "STOPPED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cycles": cycle,
        "fills": metrics.trades_filled,
        "rejects": metrics.trades_rejected,
    })


def main():
    parser = argparse.ArgumentParser(description="ARGUS v2 Paper Trading Daemon")
    parser.add_argument("--mode", choices=["paper", "backtest"], default="paper")
    parser.add_argument("--assets", default="crypto", help="Comma-separated asset classes")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between pipeline cycles")
    parser.add_argument("--v25", action="store_true", default=True, help="Enable v2.5 bootstrap")
    parser.add_argument("--no-v25", dest="v25", action="store_false", help="Disable v2.5")
    parser.add_argument("--v25-db", default="runs/v25/argus_v25.db", help="v2.5 SQLite DB path")
    parser.add_argument("--run-dir", default="runs/paper_v2", help="Output directory for logs/metrics")
    args = parser.parse_args()

    assets = [a.strip() for a in args.assets.split(",") if a.strip()]

    run_daemon(
        mode=args.mode,
        assets=assets,
        interval_seconds=args.interval,
        v25=args.v25,
        v25_db=args.v25_db,
        run_dir=args.run_dir,
    )


if __name__ == "__main__":
    main()
