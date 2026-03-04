"""ARGUS v2.5 — Dynamic Leverage Calibrator.

Computes leverage to exactly match a fixed equity-risk budget at any stop distance.

Core invariant:
    risk_usd = equity * risk_pct  (CONSTANT for a given trade)
    leverage = risk_usd / (stop_distance_pct * position_notional)

This means:
    - Tight stop (0.5%) → higher leverage (e.g., 10x)
    - Wide stop (3%)    → lower leverage (e.g., 1x)
    - Risk per trade is ALWAYS the same absolute dollar amount.

This module is self-contained, deterministic, and unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeverageCalibrationConfig:
    """Calibration parameters."""

    enabled: bool = False
    max_leverage: float = 20.0       # Hard ceiling
    min_leverage: float = 1.0        # Floor
    risk_pct: float = 0.02           # Fixed equity risk per trade (2%)
    safety_margin: float = 0.95      # Use 95% of theoretical max to absorb slippage


# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibratedLeverage:
    """Output of calibrate_leverage()."""

    leverage: float
    risk_usd: float              # Absolute USD risk for this trade
    position_notional_usd: float # Notional position size in USD
    stop_distance_pct: float     # The stop distance that drove the calculation
    was_capped: bool             # True if leverage was capped at max
    reason: str


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------


def calibrate_leverage(
    *,
    equity: float,
    risk_pct: float,
    stop_distance_pct: float,
    entry_price: float,
    config: LeverageCalibrationConfig | None = None,
) -> CalibratedLeverage:
    """Compute leverage that maintains fixed risk_pct at given stop distance.

    Math:
        risk_usd = equity × risk_pct
        At stop_distance_pct, the position loses: notional × stop_distance_pct
        We want: notional × stop_distance_pct = risk_usd
        So: notional = risk_usd / stop_distance_pct
        And: leverage = notional / equity

    Parameters
    ----------
    equity : Current account equity in USD.
    risk_pct : Fraction of equity to risk (e.g., 0.02 = 2%).
    stop_distance_pct : Stop-loss distance as fraction (e.g., 0.03 for 3%).
    entry_price : Entry price (used for position size calculation).
    config : Optional calibration config. Uses defaults if None.

    Returns
    -------
    CalibratedLeverage with the computed leverage, notional, and risk.
    """
    cfg = config or LeverageCalibrationConfig()

    # Guard against invalid inputs
    if equity <= 0 or not math.isfinite(equity):
        return CalibratedLeverage(
            leverage=1.0, risk_usd=0.0, position_notional_usd=0.0,
            stop_distance_pct=stop_distance_pct, was_capped=False,
            reason="invalid_equity",
        )
    if stop_distance_pct <= 0 or not math.isfinite(stop_distance_pct):
        return CalibratedLeverage(
            leverage=1.0, risk_usd=0.0, position_notional_usd=0.0,
            stop_distance_pct=stop_distance_pct, was_capped=False,
            reason="invalid_stop_distance",
        )
    if entry_price <= 0 or not math.isfinite(entry_price):
        return CalibratedLeverage(
            leverage=1.0, risk_usd=0.0, position_notional_usd=0.0,
            stop_distance_pct=stop_distance_pct, was_capped=False,
            reason="invalid_entry_price",
        )

    effective_risk_pct = _clamp(risk_pct, 0.001, 0.10)

    # Core calculation
    risk_usd = equity * effective_risk_pct
    target_notional = risk_usd / stop_distance_pct

    # Apply safety margin (absorb slippage)
    target_notional *= cfg.safety_margin

    # Derive leverage
    raw_leverage = target_notional / equity

    # Clamp to bounds
    was_capped = raw_leverage > cfg.max_leverage
    leverage = _clamp(raw_leverage, cfg.min_leverage, cfg.max_leverage)

    # Recompute actual notional after capping
    actual_notional = equity * leverage

    # If leverage was capped, actual risk is lower than target — that's fine
    actual_risk_at_stop = actual_notional * stop_distance_pct

    reason = "calibrated"
    if was_capped:
        reason = f"capped_at_{cfg.max_leverage:.1f}x"
    elif raw_leverage < cfg.min_leverage:
        reason = "floored_at_1x"

    return CalibratedLeverage(
        leverage=leverage,
        risk_usd=min(risk_usd, actual_risk_at_stop),
        position_notional_usd=actual_notional,
        stop_distance_pct=stop_distance_pct,
        was_capped=was_capped,
        reason=reason,
    )


def calibrate_leverage_for_scale_in(
    *,
    equity: float,
    risk_pct: float,
    avg_entry_price: float,
    current_sl_price: float,
    side: str,
    config: LeverageCalibrationConfig | None = None,
) -> CalibratedLeverage:
    """Calibrate leverage using the average entry from scale-in layers.

    After scale-in, the stop distance is relative to the AVERAGE entry,
    not the individual layer entries. This recalibrates leverage accordingly.

    Parameters
    ----------
    avg_entry_price : Weighted average entry price across all layers.
    current_sl_price : Current stop-loss price.
    side : "long" or "short".
    """
    if avg_entry_price <= 0:
        return CalibratedLeverage(
            leverage=1.0, risk_usd=0.0, position_notional_usd=0.0,
            stop_distance_pct=0.0, was_capped=False,
            reason="invalid_avg_entry",
        )

    if side == "long":
        stop_distance_pct = abs(avg_entry_price - current_sl_price) / avg_entry_price
    else:
        stop_distance_pct = abs(current_sl_price - avg_entry_price) / avg_entry_price

    return calibrate_leverage(
        equity=equity,
        risk_pct=risk_pct,
        stop_distance_pct=max(stop_distance_pct, 1e-6),
        entry_price=avg_entry_price,
        config=config,
    )
