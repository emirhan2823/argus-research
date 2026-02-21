"""Stage-2B integration & unit tests.

- 3 slippage model bounds tests
- 2 fee calculation tests
- 1 training_dataset.csv integration test
- 1 paper_cycle_log population test
- 1 backtest no-regression test
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ===========================================================================
# Unit tests: Slippage model bounds
# ===========================================================================

class TestSlippageModel:
    """Tests for compute_paper_slippage."""

    def test_slippage_lower_bound(self):
        """Very low ATR + very high volume should give base slippage only (≥ 0.0001 clamp)."""
        from src.execution.paper_execution import compute_paper_slippage

        result = compute_paper_slippage(atr_14_pct=0.0, volume_ratio=100.0)
        # base=0.0002, vol_comp=0, liq_penalty=0 → result=0.0002
        assert result >= 0.0001, f"Should be above clamp floor, got {result}"
        assert result == 0.0002, f"Expected base slippage 0.0002, got {result}"

    def test_slippage_upper_bound(self):
        """Extreme ATR + zero volume should clamp to 0.003."""
        from src.execution.paper_execution import compute_paper_slippage

        result = compute_paper_slippage(atr_14_pct=1.0, volume_ratio=0.0)
        assert result == 0.003, f"Expected upper bound 0.003, got {result}"

    def test_slippage_normal_range(self):
        """Typical ATR (2%) + normal volume (1.0) should be in range."""
        from src.execution.paper_execution import compute_paper_slippage

        result = compute_paper_slippage(atr_14_pct=0.02, volume_ratio=1.0)
        assert 0.0001 <= result <= 0.003, f"Expected in [0.0001, 0.003], got {result}"
        # base=0.0002 + vol_comp=min(0.01,0.002)=0.002 + liq=max(0,0.001-0.0005)=0.0005
        # = 0.0027 -- should be correct
        expected = 0.0002 + 0.002 + 0.0005  # 0.0027
        assert abs(result - expected) < 1e-8, f"Expected ~{expected}, got {result}"


# ===========================================================================
# Unit tests: Fee calculations
# ===========================================================================

class TestFeeModel:
    """Tests for compute_paper_fees."""

    def test_fee_calculation_taker(self):
        """Taker fee on $10,000 position at 0.04%."""
        from src.execution.paper_execution import compute_paper_fees

        result = compute_paper_fees(size_usd=10000.0, fee_pct=0.0004)
        expected = 4.0  # $10,000 * 0.0004
        assert abs(result - expected) < 1e-6, f"Expected {expected}, got {result}"

    def test_fee_calculation_maker(self):
        """Maker fee on $5,000 position at 0.02%."""
        from src.execution.paper_execution import compute_paper_fees

        result = compute_paper_fees(size_usd=5000.0, fee_pct=0.0002)
        expected = 1.0  # $5,000 * 0.0002
        assert abs(result - expected) < 1e-6, f"Expected {expected}, got {result}"


# ===========================================================================
# Integration test: training_dataset.csv creation
# ===========================================================================

def test_training_dataset_csv_created(tmp_path):
    """Export training dataset and verify CSV has correct columns."""
    from src.v25.db.migrations import run_v25_migrations

    db_path = str(tmp_path / "test.db")
    conn = run_v25_migrations(db_path)

    # Insert a test decision and paper_cycle_log entry
    conn.execute(
        """INSERT INTO decisions
           (run_id, timestamp, symbol, action, capital_engine, regime, reason, engine,
            confidence, gate_results_json, status, position_size_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "test-run", "2025-01-01T00:00:00", "BTCUSDT", "long", "core",
            "TRENDING", "test_signal", "NAUTILUS", 0.85,
            json.dumps({"path": "test", "features_snapshot": {"atr_14": 500.0, "atr_14_pct": 0.02}}),
            "executed", 0.05,
        ),
    )
    conn.execute(
        """INSERT INTO paper_cycle_log
           (decision_cycle, timestamp, symbol, regime_json, engine_weights_json,
            candidate_signals_json, final_decision_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            1, "2025-01-01T00:00:00", "BTCUSDT",
            json.dumps({"TRENDING": 0.7}),
            json.dumps({"NAUTILUS": 0.4}),
            json.dumps({"NAUTILUS": "long"}),
            json.dumps({"hold_minutes": 60, "net_pnl_pct": 0.02}),
        ),
    )
    conn.commit()

    # Export
    csv_path = tmp_path / "training_dataset.csv"
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT d.timestamp, d.symbol, d.regime, d.engine AS engine_selected,
                  d.confidence, d.reason, d.gate_results_json, d.status,
                  d.position_size_pct,
                  p.regime_json AS regime_probabilities_json,
                  p.engine_weights_json, p.final_decision_json
           FROM decisions d
           LEFT JOIN paper_cycle_log p ON d.timestamp = p.timestamp AND d.symbol = p.symbol
           ORDER BY d.decision_id ASC"""
    ).fetchall()

    expected_headers = [
        "timestamp", "symbol", "regime", "engine_selected",
        "engine_weights_json", "confidence", "atr_14", "atr_14_pct",
        "volume_ratio", "bb_pct_b", "ema_21_vs_55", "price_vs_ma200",
        "net_pnl_pct", "hold_minutes", "regime_probabilities_json",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=expected_headers)
        writer.writeheader()
        for r in rows:
            fd = json.loads(r["final_decision_json"] or "{}")
            gate = json.loads(r["gate_results_json"] or "{}")
            feats = gate.get("features_snapshot", {})
            writer.writerow({
                "timestamp": r["timestamp"],
                "symbol": r["symbol"],
                "regime": r["regime"],
                "engine_selected": r["engine_selected"],
                "engine_weights_json": r["engine_weights_json"] or "",
                "confidence": r["confidence"],
                "atr_14": feats.get("atr_14", ""),
                "atr_14_pct": feats.get("atr_14_pct", ""),
                "volume_ratio": feats.get("volume_ratio", ""),
                "bb_pct_b": feats.get("bb_pct_b", ""),
                "ema_21_vs_55": feats.get("ema_21_vs_55", ""),
                "price_vs_ma200": feats.get("price_vs_ma200", ""),
                "net_pnl_pct": fd.get("net_pnl_pct", ""),
                "hold_minutes": fd.get("hold_minutes", ""),
                "regime_probabilities_json": r["regime_probabilities_json"] or "",
            })

    conn.close()

    # Verify CSV
    assert csv_path.exists(), "training_dataset.csv should be created"
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
    assert len(csv_rows) == 1, f"Expected 1 row, got {len(csv_rows)}"
    assert csv_rows[0]["symbol"] == "BTCUSDT"
    assert csv_rows[0]["engine_selected"] == "NAUTILUS"
    assert csv_rows[0]["atr_14"] == "500.0"


# ===========================================================================
# Integration test: paper_cycle_log populated
# ===========================================================================

def test_paper_cycle_log_populated(tmp_path):
    """Verify paper_cycle_log table can be written to after migration."""
    from src.v25.db.migrations import run_v25_migrations

    db_path = str(tmp_path / "test.db")
    conn = run_v25_migrations(db_path)

    # Insert test data
    conn.execute(
        """INSERT INTO paper_cycle_log
           (decision_cycle, timestamp, symbol, regime_json,
            engine_weights_json, candidate_signals_json, final_decision_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            1, "2025-01-01T00:00:00", "BTCUSDT",
            json.dumps({"TRENDING": 0.7}),
            json.dumps({"NAUTILUS": 0.4}),
            json.dumps({"NAUTILUS": "long"}),
            json.dumps({"action": "long"}),
        ),
    )
    conn.commit()

    # Verify
    rows = conn.execute("SELECT * FROM paper_cycle_log").fetchall()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    assert rows[0][3] == "BTCUSDT"  # symbol column (index 3)

    # Verify new trades columns exist
    trades_cols = {
        str(r[1]).lower()
        for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    assert "fees_pct" in trades_cols, "trades table should have fees_pct column"
    assert "slippage_pct" in trades_cols, "trades table should have slippage_pct column"

    conn.close()


# ===========================================================================
# Integration test: backtest no regression
# ===========================================================================

def test_backtest_no_regression(tmp_path):
    """Existing pipeline should run in backtest mode without regression."""
    from src.main import ArgusPipeline

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        evolve=False,
        v25_conn=conn,
    )

    # Run one cycle
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    outputs = pipeline.run_once(now=now)

    # Basic validation: list returned, no crash
    assert isinstance(outputs, list)
    assert len(outputs) > 0

    # Each output must have required fields
    for out in outputs:
        assert "symbol" in out
        assert "status" in out

    conn.close()
