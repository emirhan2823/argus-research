"""Validated sizing for Phase G (derived leverage, fee-aware Gate 9)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.v25.contracts.validated_sizing import ValidatedSizing


_BPS_DENOMINATOR = Decimal("10000")
_GATE9_MAX_FEE_RISK_RATIO = Decimal("0.30")
_GATE9_HYSTERESIS_EPSILON = Decimal("0.000001")


def compute_validated_size(
    *,
    symbol: str,
    ts: datetime,
    risk_usd: Decimal,
    sl_pct: Decimal,
    price: Decimal | None = None,
    equity_usd: Decimal | None = None,
    max_leverage: Decimal | None = None,
    fee_bps: Decimal = Decimal("5"),
    slippage_bps: Decimal = Decimal("3"),
    gate9_threshold: Decimal = _GATE9_MAX_FEE_RISK_RATIO,
    gate9_epsilon: Decimal = _GATE9_HYSTERESIS_EPSILON,
) -> ValidatedSizing:
    """Compute validated notional/fee and apply Gate 9.

    Safety policy for `max_leverage`: FAIL (no clamp).
    """
    if risk_usd <= Decimal("0"):
        raise ValueError("risk_usd must be > 0")
    if sl_pct <= Decimal("0"):
        raise ValueError("sl_pct must be > 0")
    if fee_bps < Decimal("0") or slippage_bps < Decimal("0"):
        raise ValueError("fee_bps and slippage_bps must be >= 0")
    if price is not None and price <= Decimal("0"):
        raise ValueError("price must be > 0 when provided")
    if equity_usd is not None and equity_usd <= Decimal("0"):
        raise ValueError("equity_usd must be > 0 when provided")
    if max_leverage is not None and max_leverage <= Decimal("0"):
        raise ValueError("max_leverage must be > 0 when provided")
    if gate9_threshold <= Decimal("0"):
        raise ValueError("gate9_threshold must be > 0")
    if gate9_epsilon < Decimal("0"):
        raise ValueError("gate9_epsilon must be >= 0")

    # Fee-adjusted notional: notional = risk_usd / (sl_pct + fee_round_trip_pct)
    # This ensures total risk (SL hit + fees) never exceeds risk_usd.
    # Blueprint Pivot 1: fees are pre-deducted from the risk budget.
    total_bps = fee_bps + slippage_bps
    fee_round_trip_pct = total_bps / _BPS_DENOMINATOR
    notional_usd = risk_usd / (sl_pct + fee_round_trip_pct)
    fee_est_usd = notional_usd * fee_round_trip_pct
    fee_risk_ratio = fee_est_usd / risk_usd

    gate9_limit = gate9_threshold + gate9_epsilon
    passed_gate9 = fee_risk_ratio <= gate9_limit
    if passed_gate9:
        reason = "ok"
    else:
        reason = (
            "gate9_fail "
            f"fee_est_usd={fee_est_usd} risk_usd={risk_usd} "
            f"fee_risk_ratio={fee_risk_ratio} threshold={gate9_threshold}"
        )

    leverage: Decimal | None = None
    if equity_usd is not None:
        leverage = notional_usd / equity_usd
        if max_leverage is not None and leverage > max_leverage:
            passed_gate9 = False
            reason = f"leverage_fail derived={leverage} max_leverage={max_leverage}"

    qty: Decimal | None = None
    if price is not None:
        qty = notional_usd / price

    net_risk_usd = risk_usd - fee_est_usd

    return ValidatedSizing(
        symbol=symbol,
        ts=ts,
        risk_usd=risk_usd,
        sl_pct=sl_pct,
        notional_usd=notional_usd,
        leverage=leverage,
        qty=qty,
        fee_est_usd=fee_est_usd,
        fee_risk_ratio=fee_risk_ratio,
        net_risk_usd=net_risk_usd,
        passed_gate9=passed_gate9,
        reason=reason,
    )
