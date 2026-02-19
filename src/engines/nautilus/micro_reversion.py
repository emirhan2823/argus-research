"""Micro-reversion signals within identified ranges (D-02).

Uses 5m microstructure (OBI, RSI) to enter at range boundaries.
Pure function, no side effects.
"""

from __future__ import annotations

from typing import Optional

from src.core.constants import ENGINE_NAUTILUS
from src.core.types import EngineSignal, FeatureVector


# --- Thresholds ---
OBI_LONG_THRESHOLD = 0.55
OBI_SHORT_THRESHOLD = -0.55
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
BOUNDARY_PROXIMITY_ATR = 0.5  # Must be within 0.5 ATR of boundary
STOP_ATR_MULT = 0.5  # Stop outside range by 0.5 ATR


def detect_micro_reversion(
    features: FeatureVector,
    range_high: float,
    range_low: float,
    range_midpoint: float,
) -> Optional[EngineSignal]:
    """Generate micro-reversion signal within an identified range.

    Entry criteria:
    - **Long** at range_low: OBI > 0.55 AND RSI < 35
    - **Short** at range_high: OBI < -0.55 AND RSI > 65

    Stop: outside range by 0.5 ATR.
    Target: range midpoint.

    Parameters
    ----------
    features : FeatureVector
        Current features snapshot (must include OBI and RSI).
    range_high : float
        Upper boundary of the detected range.
    range_low : float
        Lower boundary of the detected range.
    range_midpoint : float
        Midpoint of the detected range.

    Returns
    -------
    EngineSignal | None
        A micro-reversion signal, or None if conditions not met.
    """
    obi = features.orderbook_imbalance
    if obi is None:
        return None

    atr = features.atr_14
    if atr <= 0:
        return None

    # Approximate current price from ATR fields
    approx_price = max(atr / max(features.atr_14_pct, 1e-6), 1.0)
    rsi = features.rsi_14

    # Check proximity to range boundaries
    near_low = approx_price <= range_low + atr * BOUNDARY_PROXIMITY_ATR
    near_high = approx_price >= range_high - atr * BOUNDARY_PROXIMITY_ATR

    bias: Optional[str] = None
    confidence = 0.0

    if near_low and obi > OBI_LONG_THRESHOLD and rsi < RSI_OVERSOLD:
        bias = "long"
        # Confidence from OBI strength and RSI depth
        obi_factor = min((obi - OBI_LONG_THRESHOLD) / 0.45, 1.0)
        rsi_factor = min((RSI_OVERSOLD - rsi) / RSI_OVERSOLD, 1.0)
        confidence = _clamp(0.55 + 0.20 * obi_factor + 0.15 * rsi_factor, 0.0, 1.0)

    elif near_high and obi < OBI_SHORT_THRESHOLD and rsi > RSI_OVERBOUGHT:
        bias = "short"
        obi_factor = min((abs(obi) - abs(OBI_SHORT_THRESHOLD)) / 0.45, 1.0)
        rsi_factor = min((rsi - RSI_OVERBOUGHT) / (100 - RSI_OVERBOUGHT), 1.0)
        confidence = _clamp(0.55 + 0.20 * obi_factor + 0.15 * rsi_factor, 0.0, 1.0)

    if bias is None:
        return None

    # Stop: outside range by STOP_ATR_MULT * ATR
    if bias == "long":
        sl_price = range_low - atr * STOP_ATR_MULT
    else:
        sl_price = range_high + atr * STOP_ATR_MULT

    stop_distance = abs(approx_price - sl_price) / approx_price
    stop_distance = _clamp(stop_distance, 0.001, 0.10)

    # Target: midpoint → compute expected return
    expected_return = abs(range_midpoint - approx_price) / approx_price
    expected_return = max(expected_return, 0.001)

    return EngineSignal(
        engine=ENGINE_NAUTILUS,
        sub_strategy="micro_reversion",
        asset_class=features.asset_class,
        symbol=features.symbol,
        bias=bias,
        confidence=confidence,
        stop_distance=stop_distance,
        expected_return=expected_return,
        atr=atr,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
