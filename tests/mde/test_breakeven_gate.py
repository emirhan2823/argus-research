from __future__ import annotations

from decimal import Decimal

from src.mde.gates import gate_breakeven_r_fee


def test_gate_breakeven_r_fee_pass() -> None:
    passed, fee_est_usd, fee_risk_ratio, reason = gate_breakeven_r_fee(
        risk_usd=Decimal("100"),
        notional_usd=Decimal("10000"),
        fee_bps=Decimal("5"),
        slippage_bps=Decimal("3"),
    )
    assert passed is True
    assert fee_est_usd == Decimal("8")
    assert fee_risk_ratio == Decimal("0.08")
    assert reason == "gate9_pass"


def test_gate_breakeven_r_fee_fail() -> None:
    passed, fee_est_usd, fee_risk_ratio, reason = gate_breakeven_r_fee(
        risk_usd=Decimal("100"),
        notional_usd=Decimal("10000"),
        fee_bps=Decimal("300"),
        slippage_bps=Decimal("100"),
    )
    assert passed is False
    assert fee_est_usd == Decimal("400")
    assert fee_risk_ratio == Decimal("4")
    assert "gate9_fail" in reason


def test_gate_breakeven_r_fee_hysteresis_borderline_pass() -> None:
    passed, fee_est_usd, fee_risk_ratio, reason = gate_breakeven_r_fee(
        risk_usd=Decimal("1"),
        notional_usd=Decimal("3000.005"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0"),
        threshold=Decimal("0.30"),
        epsilon=Decimal("0.000001"),
    )
    assert fee_est_usd == Decimal("0.3000005")
    assert fee_risk_ratio == Decimal("0.3000005")
    assert passed is True
    assert reason == "gate9_pass"
