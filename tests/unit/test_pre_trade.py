from __future__ import annotations

from src.risk.pre_trade import PreTradeChecker, PreTradeInput


def test_pre_trade_happy_path() -> None:
    checker = PreTradeChecker()
    out = checker.check(
        PreTradeInput(
            asset_class="crypto",
            position_size=0.05,
            leverage=1.5,
            trades_today=3,
            stop_loss=0.02,
            correlation_with_book=0.2,
            allocation_ok=True,
        )
    )
    assert out.approved is True
    assert out.reason == "ok"


def test_pre_trade_rejects_multiple_violations() -> None:
    checker = PreTradeChecker()
    out = checker.check(
        PreTradeInput(
            asset_class="crypto",
            position_size=0.20,
            leverage=2.5,
            trades_today=20,
            stop_loss=0.10,
            correlation_with_book=0.9,
            within_funding_blackout=True,
            allocation_ok=False,
        )
    )
    assert out.approved is False
    assert "position_size_limit" in out.violations
    assert "leverage_limit" in out.violations
    assert "daily_trade_limit" in out.violations
    assert "funding_blackout" in out.violations
    assert "correlation_limit" in out.violations
    assert "stop_loss_too_wide" in out.violations
    assert "allocation_limit" in out.violations


def test_pre_trade_weekend_size_reduction_for_crypto() -> None:
    checker = PreTradeChecker()
    out = checker.check(
        PreTradeInput(
            asset_class="crypto",
            position_size=0.10,
            leverage=1.2,
            trades_today=1,
            stop_loss=0.02,
            correlation_with_book=0.2,
            is_weekend=True,
            allocation_ok=True,
        )
    )
    assert out.approved is True
    assert out.adjusted_position_size == 0.05
