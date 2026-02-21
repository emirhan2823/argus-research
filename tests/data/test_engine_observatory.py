"""Tests for P4-D Engine Observatory reporting module."""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import src.main as main_mod
from src.core.types import EngineSignal
from src.v25.bootstrap import run_v25_migrations
from src.v25.reports.engine_observatory import (
    compute_max_drawdown,
    write_engine_observatory,
)


# ---------------------------------------------------------------------------
# Unit test: drawdown computation
# ---------------------------------------------------------------------------


def test_compute_max_drawdown_handcrafted() -> None:
    """Hand-crafted returns → known max drawdown."""
    # equity: 1 → 1.10 → 1.045 → 0.9405 → 1.0346
    # peak:   1 → 1.10 → 1.10  → 1.10   → 1.10
    # dd:         0.0    -0.05  -0.145   -0.06
    returns = [0.10, -0.05, -0.10, 0.10]
    dd = compute_max_drawdown(returns)
    # max dd should be at index 2: (0.9405 / 1.10) - 1 = -0.14500...
    assert dd < -0.14, f"Expected dd < -0.14, got {dd}"
    assert dd > -0.15, f"Expected dd > -0.15, got {dd}"


def test_compute_max_drawdown_empty() -> None:
    assert compute_max_drawdown([]) == 0.0


def test_compute_max_drawdown_all_positive() -> None:
    returns = [0.01, 0.02, 0.03]
    assert compute_max_drawdown(returns) == 0.0


def test_compute_max_drawdown_all_negative() -> None:
    # equity: 1 → 0.99 → 0.9801 → 0.9604
    # peak always 1.0 → dd at end = 0.9604 / 1.0 - 1 ≈ -0.0396
    returns = [-0.01, -0.01, -0.02]
    dd = compute_max_drawdown(returns)
    assert dd < -0.039, f"Expected dd < -0.039, got {dd}"
    assert dd > -0.04, f"Expected dd > -0.04, got {dd}"


# ---------------------------------------------------------------------------
# Integration: write_engine_observatory with in-memory DB
# ---------------------------------------------------------------------------

def _seed_db(conn: sqlite3.Connection, n_decisions: int = 20) -> None:
    """Seed the v25 DB with deterministic decisions and trades."""
    base_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    for i in range(n_decisions):
        cycle_time = base_time + timedelta(minutes=i)
        run_id = f"run_test:c{i + 1:04d}"
        is_executed = i % 3 == 0  # every 3rd cycle produces a trade
        engine = "TITAN" if i % 2 == 0 else "ROUTER"
        action = "long" if is_executed else "rejected"
        reason = "engine_signal:trend_follow" if is_executed else "no_signal"
        confidence = 0.78 if is_executed else 0.0

        gate_json = "{}"
        if i % 7 == 0 and not is_executed:
            gate_json = json.dumps({"gate9": {"pass": False, "fee_risk_ratio": 0.4}})
            reason = "gate9_fail"

        conn.execute(
            """
            INSERT INTO decisions (
                run_id, timestamp, symbol, action, capital_engine,
                confidence, engine, sub_strategy, regime, reason,
                status, gate_results_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                cycle_time.isoformat(),
                "BTCUSDT",
                action,
                "core",
                confidence,
                engine,
                "trend_follow",
                "TRENDING",
                reason,
                "executed" if is_executed else "rejected",
                gate_json,
            ),
        )

        if is_executed:
            exit_time = cycle_time + timedelta(minutes=30)
            pnl_pct = 0.005 if i % 6 == 0 else -0.003
            conn.execute(
                """
                INSERT INTO trades (
                    trade_id, symbol, side, capital_engine,
                    entry_time, exit_time, entry_price, exit_price,
                    size, pnl, pnl_pct, net_pnl_pct,
                    regime_at_entry, engine, sub_strategy,
                    confidence, sqs_score, stop_distance,
                    hold_minutes, reason_entry
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"trade_{i:04d}",
                    "BTCUSDT",
                    "long",
                    "core",
                    cycle_time.isoformat(),
                    exit_time.isoformat(),
                    100.0 + i * 0.01,
                    100.0 + i * 0.01 + pnl_pct * 100,
                    0.01,
                    pnl_pct * 100,
                    pnl_pct,
                    pnl_pct,
                    "TRENDING",
                    engine,
                    "trend_follow",
                    0.78,
                    0.85,
                    0.01,
                    30,
                    "engine_signal:trend_follow",
                ),
            )

    conn.commit()


def test_observatory_produces_all_files(tmp_path: Path) -> None:
    db_path = tmp_path / "test_obs.db"
    conn = run_v25_migrations(str(db_path))
    _seed_db(conn, n_decisions=20)
    conn.close()

    run_dir = tmp_path / "run_output"

    write_engine_observatory(
        db_path=str(db_path),
        run_dir=str(run_dir),
        mode="backtest",
    )

    expected_files = [
        "engine_overview.json",
        "engine_overview.md",
        "engine_overview.csv",
        "engine_regime_breakdown.csv",
        "engine_recent_windows.csv",
        "signal_funnel.csv",
    ]
    for fname in expected_files:
        p = run_dir / fname
        assert p.exists(), f"Missing: {fname}"
        assert p.stat().st_size > 0, f"Empty: {fname}"


def test_observatory_csv_has_expected_headers(tmp_path: Path) -> None:
    db_path = tmp_path / "test_obs_hdrs.db"
    conn = run_v25_migrations(str(db_path))
    _seed_db(conn, n_decisions=20)
    conn.close()

    run_dir = tmp_path / "run_output"
    write_engine_observatory(str(db_path), str(run_dir), "backtest")

    # engine_overview.csv
    with (run_dir / "engine_overview.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert "engine" in reader.fieldnames
        assert "win_rate" in reader.fieldnames
        rows = list(reader)
        assert len(rows) >= 1

    # signal_funnel.csv
    with (run_dir / "signal_funnel.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert "engine" in reader.fieldnames
        assert "decisions_total" in reader.fieldnames
        assert "gate9_fail_count" in reader.fieldnames


def test_observatory_json_contains_engine_data(tmp_path: Path) -> None:
    db_path = tmp_path / "test_obs_json.db"
    conn = run_v25_migrations(str(db_path))
    _seed_db(conn, n_decisions=20)
    conn.close()

    run_dir = tmp_path / "run_output"
    write_engine_observatory(str(db_path), str(run_dir), "backtest")

    data = json.loads((run_dir / "engine_overview.json").read_text(encoding="utf-8"))
    assert "engines" in data
    engines = data["engines"]

    # The seed creates TITAN and ROUTER decisions
    assert "TITAN" in engines or "ROUTER" in engines

    # At least one engine should have closed trades
    has_trades = any(e["closed_trades_count"] > 0 for e in engines.values())
    assert has_trades


def test_observatory_empty_db_does_not_crash(tmp_path: Path) -> None:
    """Observatory with zero decisions/trades should produce files without error."""
    db_path = tmp_path / "test_obs_empty.db"
    conn = run_v25_migrations(str(db_path))
    conn.close()

    run_dir = tmp_path / "run_output"
    write_engine_observatory(str(db_path), str(run_dir), "paper")

    assert (run_dir / "engine_overview.json").exists()
    assert (run_dir / "signal_funnel.csv").exists()


def test_observatory_funnel_counts_gate9_fail(tmp_path: Path) -> None:
    """Verify that gate9 failures from gate_results_json are counted."""
    db_path = tmp_path / "test_obs_funnel.db"
    conn = run_v25_migrations(str(db_path))
    _seed_db(conn, n_decisions=20)
    conn.close()

    run_dir = tmp_path / "run_output"
    write_engine_observatory(str(db_path), str(run_dir), "backtest")

    with (run_dir / "signal_funnel.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        total_gate9 = sum(int(row["gate9_fail_count"]) for row in reader)
        # We seed gate9 fails every 7th non-executed cycle
        assert total_gate9 >= 1


# ---------------------------------------------------------------------------
# Integration test: observatory produced from main() backtest run
# ---------------------------------------------------------------------------


def test_backtest_writes_observatory_files(monkeypatch, tmp_path) -> None:
    """Full main() backtest run produces observatory files alongside summary."""
    db_path = tmp_path / "argus_v25_obs.db"
    run_dir = tmp_path / "backtest_v25"
    dryrun_log = tmp_path / "dryrun_events.jsonl"

    cycle_idx = {"value": 0}

    def _fake_run_once(self, *, now=None):
        _ = self, now
        cycle_idx["value"] += 1
        n = cycle_idx["value"]
        if n % 2 == 0:
            return [
                {
                    "symbol": "BTCUSDT",
                    "status": "executed",
                    "reason": "engine_signal:trend_follow",
                    "action": "long",
                    "engine": "TITAN",
                    "confidence": 0.80,
                }
            ]
        return [
            {
                "symbol": "BTCUSDT",
                "status": "rejected",
                "reason": "no_signal",
                "action": "rejected",
                "engine": "ROUTER",
                "confidence": 0.0,
            }
        ]

    monkeypatch.setattr(main_mod.ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: None))
    monkeypatch.setattr(main_mod.ArgusPipeline, "run_once", _fake_run_once)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "backtest",
            "--assets",
            "crypto",
            "--max-cycles",
            "10",
            "--run-dir",
            str(run_dir),
            "--v25",
            "--v25-db",
            str(db_path),
            "--v25-dryrun-log",
            str(dryrun_log),
            "--replay-now",
            "2024-01-01T00:00:00Z",
        ],
    )

    main_mod.main()

    # Observatory files must exist
    for fname in [
        "engine_overview.json",
        "engine_overview.md",
        "engine_overview.csv",
        "engine_regime_breakdown.csv",
        "engine_recent_windows.csv",
        "signal_funnel.csv",
    ]:
        p = run_dir / fname
        assert p.exists(), f"Missing observatory file: {fname}"
        assert p.stat().st_size > 0, f"Empty observatory file: {fname}"

    # JSON should have engines including TITAN or ROUTER
    data = json.loads((run_dir / "engine_overview.json").read_text(encoding="utf-8"))
    assert "engines" in data
    engine_names = set(data["engines"].keys())
    assert "TITAN" in engine_names or "ROUTER" in engine_names

    # Funnel should have at least one row
    with (run_dir / "signal_funnel.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
        assert len(rows) >= 1
