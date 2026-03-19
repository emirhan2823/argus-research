from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.risk.validated_sizer import compute_validated_size


def _ts() -> datetime:
    return datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)


def test_fee_adjusted_notional_formula() -> None:
    """Blueprint Pivot 1: notional = risk_usd / (sl_pct + fee_round_trip_pct).

    With default fee_bps=5, slippage_bps=3:
        fee_round_trip_pct = 8/10000 = 0.0008
        notional = 100 / (0.01 + 0.0008) = 100 / 0.0108
    """
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.01"),
    )
    expected_notional = Decimal("100") / (Decimal("0.01") + Decimal("0.0008"))
    assert out.notional_usd == expected_notional
    assert out.notional_usd < Decimal("10000")  # strictly less than old formula


def test_zero_fee_matches_old_formula() -> None:
    """With zero fees, fee-adjusted formula degenerates to risk_usd / sl_pct."""
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.01"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    assert out.notional_usd == Decimal("10000")
    assert out.fee_est_usd == Decimal("0")
    assert out.net_risk_usd == Decimal("100")


def test_qty_computation() -> None:
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.01"),
        price=Decimal("20000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    assert out.qty == Decimal("0.5")


def test_gate9_fail() -> None:
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.01"),
        fee_bps=Decimal("300"),
        slippage_bps=Decimal("100"),
    )
    assert out.passed_gate9 is False
    assert "gate9_fail" in out.reason


def test_gate9_pass() -> None:
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.01"),
        fee_bps=Decimal("5"),
        slippage_bps=Decimal("3"),
    )
    assert out.passed_gate9 is True


def test_gate9_hysteresis_allows_borderline_ratio() -> None:
    fee_pct = Decimal("8") / Decimal("10000")
    target_ratio = Decimal("0.3000005")
    sl_pct = fee_pct * (Decimal("1") - target_ratio) / target_ratio

    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=sl_pct,
        fee_bps=Decimal("5"),
        slippage_bps=Decimal("3"),
        gate9_threshold=Decimal("0.30"),
        gate9_epsilon=Decimal("0.000001"),
    )

    assert out.fee_risk_ratio > Decimal("0.30")
    assert out.passed_gate9 is True


def test_net_risk_usd_is_risk_minus_fees() -> None:
    """net_risk_usd = risk_usd - fee_est_usd."""
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.02"),
        fee_bps=Decimal("5"),
        slippage_bps=Decimal("3"),
    )
    assert out.net_risk_usd == out.risk_usd - out.fee_est_usd
    assert out.net_risk_usd > Decimal("0")


def test_total_risk_within_budget() -> None:
    """Fee-adjusted formula guarantees: sl_loss + fees <= risk_usd.

    sl_loss = notional * sl_pct
    fees    = notional * fee_pct
    total   = notional * (sl_pct + fee_pct) = risk_usd
    """
    out = compute_validated_size(
        symbol="BTC-USDT",
        ts=_ts(),
        risk_usd=Decimal("100"),
        sl_pct=Decimal("0.02"),
        fee_bps=Decimal("5"),
        slippage_bps=Decimal("3"),
    )
    sl_loss = out.notional_usd * Decimal("0.02")
    fee_cost = out.notional_usd * Decimal("0.0008")
    total_risk = sl_loss + fee_cost
    assert abs(total_risk - Decimal("100")) < Decimal("0.0001")
