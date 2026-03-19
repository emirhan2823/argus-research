from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from src.risk.pre_trade import PreTradeChecker, PreTradeInput


def _fee_adjusted_notional(risk_usd: Decimal, sl_pct: Decimal, fee_bps: Decimal, slippage_bps: Decimal) -> Decimal:
    """Mirror the canonical fee-adjusted formula."""
    fee_round_trip_pct = (fee_bps + slippage_bps) / Decimal("10000")
    return risk_usd / (sl_pct + fee_round_trip_pct)


def test_pre_trade_approved_uses_fee_adjusted_notional() -> None:
    checker = PreTradeChecker()
    out = checker.check(
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
    expected = _fee_adjusted_notional(Decimal("100"), Decimal("0.01"), Decimal("5"), Decimal("3"))
    assert out.approved is True
    assert out.adjusted_position_size == 0.10
    assert Decimal(out.sizing_snapshot["notional_usd"]) == expected
    assert out.validated_notional_usd is not None
    assert Decimal(out.validated_notional_usd) == expected
    # Fee-adjusted notional is strictly less than old formula (risk/sl_pct)
    assert expected < Decimal("10000")


def test_pre_trade_rejects_gate9_fail() -> None:
    checker = PreTradeChecker()
    out = checker.check(
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
    assert out.approved is False
    assert "validated_sizing_reject" in out.violations
    assert "gate9_fail" in out.reason
    assert out.adjusted_position_size >= 0.0
    # With extreme fees, notional uses fee-adjusted formula
    expected = _fee_adjusted_notional(Decimal("100"), Decimal("0.01"), Decimal("300"), Decimal("100"))
    assert Decimal(out.sizing_snapshot["notional_usd"]) == expected
    assert out.validated_notional_usd is not None


def test_pre_trade_handles_missing_max_leverage_attr() -> None:
    checker = PreTradeChecker()
    inp = SimpleNamespace(
        asset_class="crypto",
        symbol="BTC-USDT",
        position_size=0.10,
        leverage=1.0,
        trades_today=0,
        stop_loss=0.01,
        correlation_with_book=0.1,
        within_funding_blackout=False,
        is_weekend=False,
        allocation_ok=True,
        max_position_size=0.15,
        max_trades_per_day=15,
        max_correlation=0.6,
        max_stop_crypto=0.05,
        max_stop_stock=0.08,
        max_stop_commodity=0.06,
        ts=None,
        risk_usd=Decimal("100"),
        entry_price=None,
        equity_usd=None,
        fee_bps=Decimal("5"),
        slippage_bps=Decimal("3"),
        stop_loss_is_pct=True,
    )
    out = checker.check(cast(Any, inp))
    expected = _fee_adjusted_notional(Decimal("100"), Decimal("0.01"), Decimal("5"), Decimal("3"))
    assert out.approved is True
    assert out.adjusted_position_size == 0.10
    assert out.validated_notional_usd is not None
    assert Decimal(out.validated_notional_usd) == expected
