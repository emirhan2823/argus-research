"""Regression test: regime_at_entry must reflect actual regime, not 'REPLAY'."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from src.main import ArgusPipeline
from src.v25.bootstrap import run_v25_migrations


@pytest.fixture()
def _pipeline_with_db(tmp_path):
    db_path = tmp_path / "argus_v25.db"
    conn = run_v25_migrations(str(db_path))
    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=30,
    )
    return pipeline, conn


class TestRegimePersistence:
    def test_regime_passed_through_to_trades(self, _pipeline_with_db):
        """When regime='RANGING' is passed, trades.regime_at_entry must be 'RANGING'."""
        pipeline, conn = _pipeline_with_db
        now = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

        pipeline._persist_backtest_execution_sim_trade(
            symbol="BTCUSDT",
            side="long",
            engine="POSEIDON",
            confidence=0.70,
            stop_distance=0.02,
            entry_time=now,
            exit_time=now + timedelta(hours=6),
            entry_price=100.0,
            exit_price=101.0,
            size=10.0,
            leverage=5.0,
            hold_minutes=360,
            fees_pct=0.001,
            slippage_pct=0.0005,
            reason_exit="time_exit_backtest_sim",
            regime="RANGING",
        )
        conn.commit()

        row = conn.execute(
            "SELECT regime_at_entry, regime_at_exit FROM trades LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "RANGING"
        assert row[1] == "RANGING"

    def test_regime_defaults_to_unknown_when_empty(self, _pipeline_with_db):
        """When regime is omitted, trades.regime_at_entry must be 'UNKNOWN', not 'REPLAY'."""
        pipeline, conn = _pipeline_with_db
        now = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

        pipeline._persist_backtest_execution_sim_trade(
            symbol="ETHUSDT",
            side="short",
            engine="AEGEAN",
            confidence=0.65,
            stop_distance=0.015,
            entry_time=now,
            exit_time=now + timedelta(hours=3),
            entry_price=3000.0,
            exit_price=2970.0,
            size=1.0,
            leverage=3.0,
            hold_minutes=180,
            fees_pct=0.001,
            slippage_pct=0.0005,
            reason_exit="stop_loss_hit",
        )
        conn.commit()

        row = conn.execute(
            "SELECT regime_at_entry FROM trades LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "UNKNOWN"
        assert row[0] != "REPLAY"

    def test_regime_never_replay(self, _pipeline_with_db):
        """No code path should produce 'REPLAY' as regime_at_entry."""
        pipeline, conn = _pipeline_with_db
        now = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

        for idx, regime_val in enumerate(("TRENDING", "VOLATILE", "CRISIS", "")):
            pipeline._persist_backtest_execution_sim_trade(
                symbol="BTCUSDT",
                side="long",
                engine="HYDRA",
                confidence=0.60,
                stop_distance=0.01,
                entry_time=now + timedelta(hours=idx * 2),
                exit_time=now + timedelta(hours=idx * 2 + 1),
                entry_price=100.0,
                exit_price=99.0,
                size=5.0,
                leverage=2.0,
                hold_minutes=60,
                fees_pct=0.001,
                slippage_pct=0.0005,
                regime=regime_val,
            )
        conn.commit()

        rows = conn.execute("SELECT regime_at_entry FROM trades").fetchall()
        for row in rows:
            assert row[0] != "REPLAY", f"Found 'REPLAY' in regime_at_entry: {row}"
