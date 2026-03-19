"""Range detection for CHOP/RANGING regime (D-01).

Identifies horizontal price ranges from recent candle data using
pivot-high/low clustering. Pure function, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RangeResult:
    """Detected horizontal range boundaries."""

    range_high: float
    range_low: float
    midpoint: float
    range_width_pct: float  # (high - low) / midpoint
    touch_count_high: int  # number of candles near high
    touch_count_low: int  # number of candles near low


def identify_range(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr: float,
    lookback: int = 50,
    atr_filter: float = 0.5,
    min_touches: int = 2,
) -> Optional[RangeResult]:
    """Detect horizontal range from recent candle data.

    Uses cluster analysis on pivot highs/lows: finds the most-tested
    high and low zones within ``atr * atr_filter`` tolerance.

    Parameters
    ----------
    highs : list[float]
        High prices (most recent last). Must have len >= lookback.
    lows : list[float]
        Low prices (most recent last). Must have len >= lookback.
    closes : list[float]
        Close prices (most recent last). Must have len >= lookback.
    atr : float
        Current ATR(14) for the asset. Used for zone tolerance.
    lookback : int
        Number of bars to analyze (default 50).
    atr_filter : float
        Zone tolerance as fraction of ATR (default 0.5).
    min_touches : int
        Minimum number of touches at each boundary to confirm range.

    Returns
    -------
    RangeResult | None
        Detected range, or None if no valid range found.
    """
    if len(highs) < lookback or len(lows) < lookback or len(closes) < lookback:
        return None
    if atr <= 0:
        return None

    # Work with the most recent `lookback` bars
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]
    recent_closes = closes[-lookback:]

    tolerance = atr * atr_filter

    # Find resistance zone: cluster pivot highs
    # A pivot high is a bar whose high is >= its neighbours
    pivot_highs = _find_pivot_highs(recent_highs)
    if not pivot_highs:
        return None

    # Find support zone: cluster pivot lows
    pivot_lows = _find_pivot_lows(recent_lows)
    if not pivot_lows:
        return None

    # Find the strongest resistance level (most-touched)
    best_resist, resist_touches = _find_best_cluster(pivot_highs, tolerance)
    if resist_touches < min_touches:
        return None

    # Find the strongest support level (most-touched)
    best_support, support_touches = _find_best_cluster(pivot_lows, tolerance)
    if support_touches < min_touches:
        return None

    # Validate: resistance must be above support
    if best_resist <= best_support:
        return None

    midpoint = (best_resist + best_support) / 2.0

    # Validate: range width should be reasonable (not too narrow, not too wide)
    range_width_pct = (best_resist - best_support) / midpoint
    if range_width_pct < 0.005:  # Less than 0.5% is noise
        return None
    if range_width_pct > 0.15:  # More than 15% is not a range
        return None

    # Validate: current price is within the range
    current_close = recent_closes[-1]
    if current_close > best_resist + tolerance or current_close < best_support - tolerance:
        return None

    return RangeResult(
        range_high=best_resist,
        range_low=best_support,
        midpoint=midpoint,
        range_width_pct=range_width_pct,
        touch_count_high=resist_touches,
        touch_count_low=support_touches,
    )


def _find_pivot_highs(highs: list[float]) -> list[float]:
    """Find local pivot high prices (bar higher than both neighbours)."""
    pivots: list[float] = []
    for i in range(1, len(highs) - 1):
        if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]:
            pivots.append(highs[i])
    return pivots


def _find_pivot_lows(lows: list[float]) -> list[float]:
    """Find local pivot low prices (bar lower than both neighbours)."""
    pivots: list[float] = []
    for i in range(1, len(lows) - 1):
        if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]:
            pivots.append(lows[i])
    return pivots


def _find_best_cluster(
    values: list[float],
    tolerance: float,
) -> tuple[float, int]:
    """Find the price level with the most values within tolerance.

    Returns (best_level, touch_count). If values is empty, returns (0, 0).
    """
    if not values:
        return 0.0, 0

    best_level = 0.0
    best_count = 0

    for candidate in values:
        count = sum(1 for v in values if abs(v - candidate) <= tolerance)
        if count > best_count:
            best_count = count
            best_level = candidate

    # Refine: average all values in the winning cluster
    cluster = [v for v in values if abs(v - best_level) <= tolerance]
    refined_level = sum(cluster) / len(cluster)

    return refined_level, best_count
