"""Tests for PR-SHADOW-PERSIST: telemetry wiring for dynamic exit and validated sizing."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.v25.db.migrations import run_v25_migrations
from src.v25.telemetry.log_writer import log_dynamic_exit, log_validated_sizing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def v25_conn(tmp_path) -> sqlite3.Connection:
    """In-memory v2.5 DB with all migrations applied."""
    db_path = str(tmp_path / "test_v25.db")
    conn = run_v25_migrations(db_path)
    return conn


# ---------------------------------------------------------------------------
# 1. PreTradeResult now exposes validated_sizing
# ---------------------------------------------------------------------------


def test_pre_trade_result_carries_validated_sizing() -> None:
    """PreTradeResult.validated_sizing is populated after compute_validated_size()."""
    from src.risk.pre_trade import PreTradeChecker, PreTradeInput

    checker = PreTradeChecker()
    result = checker.check(
        PreTradeInput(
            asset_class="crypto",
            symbol="BTC-USDT",
            position_size=0.10,
            leverage=1.0,
            trades_today=0,
            stop_loss=0.01,
            correlation_with_book=0.1,
            allocation_ok=True,
            risk_usd=Decimal("100"),
            fee_bps=Decimal("5"),
            slippage_bps=Decimal("3"),
        )
    )
    assert result.approved is True
    assert result.validated_sizing is not None
    assert result.validated_sizing.symbol == "BTC-USDT"
    assert result.validated_sizing.passed_gate9 is True
    assert result.validated_sizing.notional_usd > Decimal("0")


def test_pre_trade_result_carries_validated_sizing_on_rejection() -> None:
    """Even rejected results carry the sizing object for telemetry."""
    from src.risk.pre_trade import PreTradeChecker, PreTradeInput

    checker = PreTradeChecker()
    result = checker.check(
        PreTradeInput(
            asset_class="crypto",
            symbol="BTC-USDT",
            position_size=0.10,
            leverage=1.0,
            trades_today=0,
            stop_loss=0.01,
            correlation_with_book=0.1,
            allocation_ok=True,
            risk_usd=Decimal("100"),
            fee_bps=Decimal("300"),
            slippage_bps=Decimal("100"),
        )
    )
    assert result.approved is False
    assert result.validated_sizing is not None
    assert result.validated_sizing.passed_gate9 is False


def test_pre_trade_result_validated_sizing_none_when_violations() -> None:
    """If pre-trade fails before compute_validated_size(), sizing is None."""
    from src.risk.pre_trade import PreTradeChecker, PreTradeInput

    checker = PreTradeChecker()
    result = checker.check(
        PreTradeInput(
            asset_class="crypto",
            symbol="BTC-USDT",
            position_size=0.10,
            leverage=1.0,
            trades_today=0,
            stop_loss=-0.01,  # Non-positive => violation before sizing
            correlation_with_book=0.1,
            allocation_ok=True,
        )
    )
    assert result.approved is False
    assert "stop_loss_non_positive" in result.violations
    assert result.validated_sizing is None


# ---------------------------------------------------------------------------
# 2. log_validated_sizing() writes to validated_sizing_log table
# ---------------------------------------------------------------------------


def test_log_validated_sizing_inserts_row(v25_conn: sqlite3.Connection) -> None:
    """log_validated_sizing() inserts exactly one row with correct field values."""
    log_validated_sizing(
        v25_conn,
        symbol="BTC-USDT",
        equity=10000.0,
        risk_pct=0.01,
        risk_usd=100.0,
        entry_price=50000.0,
        sl_price=49500.0,
        sl_pct=0.01,
        notional_usd=9900.0,
        quantity=0.198,
        leverage_derived=0.99,
        breakeven_r=0.08,
        fee_reserved=8.0,
        net_risk_usd=92.0,
        passed_breakeven_gate=True,
    )
    v25_conn.commit()

    rows = v25_conn.execute("SELECT * FROM validated_sizing_log").fetchall()
    assert len(rows) == 1
    # Column order: id, timestamp, symbol, equity, risk_pct, risk_usd, entry_price,
    #               sl_price, sl_pct, notional_usd, quantity, leverage_derived,
    #               leverage_capped, breakeven_r, fee_reserved, net_risk_usd, passed_breakeven_gate
    row = rows[0]
    assert row[2] == "BTC-USDT"  # symbol
    assert row[5] == 100.0  # risk_usd
    assert row[9] == 9900.0  # notional_usd
    assert row[16] == 1  # passed_breakeven_gate (True -> 1)


# ---------------------------------------------------------------------------
# 3. log_dynamic_exit() writes to dynamic_exit_log table
# ---------------------------------------------------------------------------


def test_log_dynamic_exit_inserts_row(v25_conn: sqlite3.Connection) -> None:
    """log_dynamic_exit() inserts exactly one row with valid stage."""
    log_dynamic_exit(
        v25_conn,
        position_id="pos-BTCUSDT-12345",
        symbol="BTCUSDT",
        stage="BREAKEVEN_LOCK",
        current_r=0.5,
        pct_closed=0.0,
        partial_pnl_locked=0.0,
        regime="shadow",
        trigger_reason="to_breakeven_lock",
        trailing_sl=50100.0,
    )
    v25_conn.commit()

    rows = v25_conn.execute("SELECT * FROM dynamic_exit_log").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[2] == "pos-BTCUSDT-12345"  # position_id
    assert row[4] == "BTCUSDT"  # symbol
    assert row[5] == "BREAKEVEN_LOCK"  # stage
    assert row[11] == "shadow"  # regime


def test_log_dynamic_exit_rejects_invalid_stage(v25_conn: sqlite3.Connection) -> None:
    """DB CHECK constraint rejects invalid stage values."""
    with pytest.raises(sqlite3.IntegrityError):
        log_dynamic_exit(
            v25_conn,
            position_id="pos-test",
            symbol="BTCUSDT",
            stage="INVALID_STAGE",
            current_r=0.0,
            pct_closed=0.0,
            partial_pnl_locked=0.0,
            regime="shadow",
            trigger_reason="test",
        )


# ---------------------------------------------------------------------------
# 4. Pipeline _persist_dynamic_exit_intent() integration
# ---------------------------------------------------------------------------


def test_persist_dynamic_exit_intent_writes_to_db(v25_conn: sqlite3.Connection) -> None:
    """_persist_dynamic_exit_intent writes a row when v25_conn is set."""
    from src.main import ArgusPipeline

    # Minimal intent mock matching OrderIntent structure
    intent = SimpleNamespace(
        symbol="BTCUSDT",
        action_type="UPDATE_STOP",
        new_stop_price=Decimal("50100"),
        take_profit_fraction=None,
        reason="to_breakeven_lock",
        source="dynamic_exit",
    )

    # Create pipeline with v25_conn but without full init
    pipeline = object.__new__(ArgusPipeline)
    pipeline.v25_conn = v25_conn

    now = datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)
    pipeline._persist_dynamic_exit_intent(intent=intent, now=now)

    rows = v25_conn.execute("SELECT * FROM dynamic_exit_log").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[4] == "BTCUSDT"  # symbol
    assert row[5] == "BREAKEVEN_LOCK"  # stage (mapped from reason)
    assert row[9] == 50100.0  # trailing_sl
    assert row[11] == "shadow"  # regime
    assert row[12] == "to_breakeven_lock"  # trigger_reason


def test_persist_dynamic_exit_intent_skips_when_no_conn() -> None:
    """_persist_dynamic_exit_intent is a no-op when v25_conn is None."""
    from src.main import ArgusPipeline

    intent = SimpleNamespace(
        symbol="BTCUSDT",
        action_type="UPDATE_STOP",
        new_stop_price=Decimal("50100"),
        take_profit_fraction=None,
        reason="to_breakeven_lock",
    )

    pipeline = object.__new__(ArgusPipeline)
    pipeline.v25_conn = None

    now = datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)
    # Should not raise
    pipeline._persist_dynamic_exit_intent(intent=intent, now=now)


def test_persist_dynamic_exit_intent_partial_take(v25_conn: sqlite3.Connection) -> None:
    """TAKE_PARTIAL intents are logged with pct_closed from take_profit_fraction."""
    from src.main import ArgusPipeline

    intent = SimpleNamespace(
        symbol="ETHUSDT",
        action_type="TAKE_PARTIAL",
        new_stop_price=None,
        take_profit_fraction=Decimal("0.30"),
        reason="to_profit_capture",
        source="dynamic_exit",
    )

    pipeline = object.__new__(ArgusPipeline)
    pipeline.v25_conn = v25_conn

    now = datetime(2026, 2, 16, 13, 0, 0, tzinfo=timezone.utc)
    pipeline._persist_dynamic_exit_intent(intent=intent, now=now)

    rows = v25_conn.execute("SELECT * FROM dynamic_exit_log").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[4] == "ETHUSDT"
    assert row[5] == "PROFIT_CAPTURE"  # mapped from to_profit_capture
    assert row[7] == 0.30  # pct_closed


# ---------------------------------------------------------------------------
# 5. Pipeline _persist_validated_sizing() integration
# ---------------------------------------------------------------------------


def test_persist_validated_sizing_writes_to_db(v25_conn: sqlite3.Connection) -> None:
    """_persist_validated_sizing writes a row when v25_conn is set and sizing is present."""
    from src.main import ArgusPipeline
    from src.risk.pre_trade import PreTradeChecker, PreTradeInput

    checker = PreTradeChecker()
    pre = checker.check(
        PreTradeInput(
            asset_class="crypto",
            symbol="BTC-USDT",
            position_size=0.10,
            leverage=1.0,
            trades_today=0,
            stop_loss=0.01,
            correlation_with_book=0.1,
            allocation_ok=True,
            risk_usd=Decimal("100"),
            fee_bps=Decimal("5"),
            slippage_bps=Decimal("3"),
        )
    )
    assert pre.validated_sizing is not None

    pipeline = object.__new__(ArgusPipeline)
    pipeline.v25_conn = v25_conn

    pipeline._persist_validated_sizing(pre=pre, symbol="BTC-USDT")

    rows = v25_conn.execute("SELECT * FROM validated_sizing_log").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[2] == "BTC-USDT"  # symbol
    assert row[5] == float(pre.validated_sizing.risk_usd)  # risk_usd
    assert row[16] == 1  # passed_breakeven_gate


def test_persist_validated_sizing_skips_when_no_conn() -> None:
    """_persist_validated_sizing is a no-op when v25_conn is None."""
    from src.main import ArgusPipeline
    from src.risk.pre_trade import PreTradeChecker, PreTradeInput

    checker = PreTradeChecker()
    pre = checker.check(
        PreTradeInput(
            asset_class="crypto",
            symbol="BTC-USDT",
            position_size=0.10,
            leverage=1.0,
            trades_today=0,
            stop_loss=0.01,
            correlation_with_book=0.1,
            allocation_ok=True,
            risk_usd=Decimal("100"),
        )
    )

    pipeline = object.__new__(ArgusPipeline)
    pipeline.v25_conn = None

    # Should not raise
    pipeline._persist_validated_sizing(pre=pre, symbol="BTC-USDT")


def test_persist_validated_sizing_skips_when_no_sizing() -> None:
    """_persist_validated_sizing is a no-op when pre has no validated_sizing."""
    from src.main import ArgusPipeline

    pre = SimpleNamespace(validated_sizing=None)

    pipeline = object.__new__(ArgusPipeline)
    pipeline.v25_conn = sqlite3.connect(":memory:")

    # Should not raise, should not write
    pipeline._persist_validated_sizing(pre=pre, symbol="BTC-USDT")


# ---------------------------------------------------------------------------
# 6. _stage_from_reason mapping
# ---------------------------------------------------------------------------


def test_stage_from_reason_mapping() -> None:
    """Reason strings map to valid DB stage values."""
    from src.main import ArgusPipeline

    assert ArgusPipeline._stage_from_reason("to_breakeven_lock") == "BREAKEVEN_LOCK"
    assert ArgusPipeline._stage_from_reason("to_profit_capture") == "PROFIT_CAPTURE"
    assert ArgusPipeline._stage_from_reason("to_trend_rider") == "TREND_RIDER"
    assert ArgusPipeline._stage_from_reason("trail_tightened") == "ENTRY"
    assert ArgusPipeline._stage_from_reason("unknown") == "ENTRY"
