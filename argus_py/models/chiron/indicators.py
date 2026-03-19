from __future__ import annotations

import math
from typing import List


def calculate_chop_index(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> float:
    """Choppiness Index: 0-100, higher = more choppy."""
    if period <= 1:
        raise ValueError("period must be > 1")
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return 50.0

    atr_sum = 0.0
    for i in range(1, period + 1):
        tr = max(
            highs[-i] - lows[-i],
            abs(highs[-i] - closes[-i - 1]),
            abs(lows[-i] - closes[-i - 1]),
        )
        atr_sum += tr

    highest = max(highs[-period:])
    lowest = min(lows[-period:])

    if highest == lowest:
        return 50.0

    chop = 100.0 * math.log10(atr_sum / (highest - lowest)) / math.log10(period)
    return max(0.0, min(100.0, float(chop)))
