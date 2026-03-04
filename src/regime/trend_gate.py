"""ARGUS v6 — Trend Verification Gate.

5-condition check that must ALL pass before trend engines receive enhanced
parameters (higher RR, larger size, trailing). Prevents false-trend activation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TrendGateResult:
    """Output of trend verification."""

    verified: bool              # True = all 5 conditions passed
    score: int                  # How many of 5 conditions passed (0-5)
    conditions: dict[str, bool] # Individual condition results
    bias: Optional[str]         # "long" | "short" | None


def check_trend_gate(
    *,
    adx_14: float,
    lr_slope_20: float,
    ema_21_vs_55: float,
    price_vs_ma200: float,
    atr_pctl: float,
    swing_highs: Optional[list[float]] = None,
    swing_lows: Optional[list[float]] = None,
) -> TrendGateResult:
    """Evaluate 5 trend verification conditions.

    Conditions (ALL must pass for verified=True):
        1. ADX > 20          — trend strength present
        2. lr_slope_20 != 0  — EMA21 slope has direction
        3. EMA21/55 aligned with MA200 — macro confirmation
        4. ATR percentile > 0.4  — sufficient volatility for trend
        5. HH/HL structure    — price structure confirms direction
    """

    conditions: dict[str, bool] = {}

    # ── Condition 1: ADX strength ──
    conditions["adx_above_20"] = adx_14 > 20.0

    # ── Condition 2: EMA21 slope direction ──
    conditions["ema_slope_directional"] = abs(lr_slope_20) > 0.0001

    # ── Condition 3: EMA alignment with MA200 ──
    # Both must be same sign (both positive = uptrend, both negative = downtrend)
    if ema_21_vs_55 > 0 and price_vs_ma200 > 0:
        aligned = True
        bias = "long"
    elif ema_21_vs_55 < 0 and price_vs_ma200 < 0:
        aligned = True
        bias = "short"
    else:
        aligned = False
        bias = None

    conditions["ema_ma200_aligned"] = aligned

    # ── Condition 4: ATR percentile ──
    conditions["atr_pctl_above_04"] = atr_pctl > 0.4

    # ── Condition 5: Market structure (HH/HL or LL/LH) ──
    structure_ok = False
    if swing_highs and len(swing_highs) >= 2 and swing_lows and len(swing_lows) >= 2:
        last_hh = swing_highs[-1] > swing_highs[-2]
        last_hl = swing_lows[-1] > swing_lows[-2]
        last_ll = swing_lows[-1] < swing_lows[-2]
        last_lh = swing_highs[-1] < swing_highs[-2]

        if bias == "long":
            structure_ok = last_hh and last_hl  # Uptrend structure
        elif bias == "short":
            structure_ok = last_ll and last_lh  # Downtrend structure
        else:
            # No bias yet from condition 3 → check either direction
            structure_ok = (last_hh and last_hl) or (last_ll and last_lh)
            if last_ll and last_lh:
                bias = "short"
            elif last_hh and last_hl:
                bias = "long"
    else:
        # Insufficient swing data → fail structure check
        structure_ok = False

    conditions["structure_confirms"] = structure_ok

    score = sum(1 for v in conditions.values() if v)
    verified = all(conditions.values())

    return TrendGateResult(
        verified=verified,
        score=score,
        conditions=conditions,
        bias=bias if verified else None,
    )
