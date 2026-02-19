"""Precision Entry Filter — microstructure quality grading (Phase E).

Evaluates entry microstructure quality at the moment of signal,
producing a grade A-F. Grade F signals are rejected.

Sits between signal quality assessment (step 6.5) and gates (step 7).
This module is independent from hyper_precision.py (PR-J01) which
handles order-type decisions (limit/market/skip). This filter grades
the overall *quality* of the entry opportunity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Grade thresholds (configurable via PrecisionConfig)
# ---------------------------------------------------------------------------
DEFAULT_GRADE_THRESHOLDS = {
    "A": 0.80,
    "B": 0.65,
    "C": 0.50,
    "D": 0.35,
    # Below D threshold → Grade F (reject)
}

# Minimum grade to pass: D or above
MIN_PASSING_GRADE = "D"
_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


@dataclass(frozen=True)
class PrecisionConfig:
    """Configuration for precision filter thresholds."""

    grade_a_threshold: float = 0.80
    grade_b_threshold: float = 0.65
    grade_c_threshold: float = 0.50
    grade_d_threshold: float = 0.35
    min_passing_grade: str = "D"
    # Confidence adjustments per grade
    conf_boost_a: float = 0.05
    conf_boost_b: float = 0.02
    conf_penalty_d: float = -0.05
    conf_penalty_f: float = -0.10


@dataclass(frozen=True)
class PrecisionGrade:
    """Result of entry precision assessment."""

    grade: str  # "A" | "B" | "C" | "D" | "F"
    score: float  # 0.0 to 1.0
    obi: float | None  # orderbook imbalance at entry
    spread_ratio: float  # current_spread / median_spread
    vwap_deviation: float  # VWAP deviation percentage
    recommended_entry: float  # optimal limit price
    recommended_order_type: str  # "limit" | "market"
    reason: str
    passed: bool  # True if grade meets minimum threshold
    confidence_adjustment: float  # How much to adjust signal confidence


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _grade_passes(grade: str, min_grade: str) -> bool:
    """Check if a grade meets the minimum threshold."""
    return _GRADE_ORDER.get(grade, 0) >= _GRADE_ORDER.get(min_grade, 0)


def assess_entry_precision(
    *,
    direction: str,  # "long" | "short"
    current_price: float,
    obi: float | None,  # orderbook imbalance [-1, 1]
    spread_pct: float,
    median_spread_pct: float,
    vwap_dev_pct: float,
    volume_ratio: float,
    atr_pct: float,
    config: PrecisionConfig | None = None,
) -> PrecisionGrade:
    """Evaluate microstructure quality at entry moment.

    Factors scored (0-1):
    1. OBI alignment with direction (weight: 0.30)
    2. Spread tightness (weight: 0.25)
    3. VWAP proximity (weight: 0.20)
    4. Volume support (weight: 0.15)
    5. ATR reasonableness (weight: 0.10)

    Returns a PrecisionGrade with grade A-F and entry recommendation.
    """
    if config is None:
        config = PrecisionConfig()

    factors: list[tuple[float, float]] = []  # (score, weight)

    # --- Factor 1: OBI alignment (weight 0.30) ---
    obi_score = _score_obi(obi, direction)
    factors.append((obi_score, 0.30))

    # --- Factor 2: Spread tightness (weight 0.25) ---
    spread_ratio = spread_pct / max(median_spread_pct, 1e-8)
    spread_score = _score_spread(spread_ratio)
    factors.append((spread_score, 0.25))

    # --- Factor 3: VWAP proximity (weight 0.20) ---
    vwap_score = _score_vwap(vwap_dev_pct, direction)
    factors.append((vwap_score, 0.20))

    # --- Factor 4: Volume support (weight 0.15) ---
    volume_score = _score_volume(volume_ratio)
    factors.append((volume_score, 0.15))

    # --- Factor 5: ATR reasonableness (weight 0.10) ---
    atr_score = _score_atr(atr_pct)
    factors.append((atr_score, 0.10))

    # Weighted average score
    total_score = sum(s * w for s, w in factors) / sum(w for _, w in factors)
    total_score = _clamp(total_score, 0.0, 1.0)

    # Assign grade
    grade = _assign_grade(total_score, config)

    # Determine order type recommendation
    if obi_score >= 0.60 and spread_score >= 0.50:
        recommended_order_type = "limit"
    else:
        recommended_order_type = "market"

    # Compute recommended entry price
    recommended_entry = _compute_recommended_entry(
        direction, current_price, vwap_dev_pct
    )

    # Confidence adjustment
    conf_adj = _confidence_adjustment(grade, config)

    passed = _grade_passes(grade, config.min_passing_grade)

    reason = _build_reason(grade, total_score, obi_score, spread_score)

    return PrecisionGrade(
        grade=grade,
        score=round(total_score, 4),
        obi=obi,
        spread_ratio=round(spread_ratio, 4),
        vwap_deviation=vwap_dev_pct,
        recommended_entry=round(recommended_entry, 8),
        recommended_order_type=recommended_order_type,
        reason=reason,
        passed=passed,
        confidence_adjustment=conf_adj,
    )


# ---------------------------------------------------------------------------
# Factor scoring functions
# ---------------------------------------------------------------------------


def _score_obi(obi: float | None, direction: str) -> float:
    """Score OBI alignment with direction (0-1)."""
    if obi is None:
        return 0.40  # Neutral when missing

    if direction == "long":
        # Positive OBI = buy pressure → good for long
        if obi >= 0.60:
            return 1.0
        elif obi >= 0.30:
            return 0.70
        elif obi >= 0.0:
            return 0.50
        elif obi >= -0.30:
            return 0.30
        else:
            return 0.10  # Strong sell pressure → bad for long
    else:  # short
        # Negative OBI = sell pressure → good for short
        if obi <= -0.60:
            return 1.0
        elif obi <= -0.30:
            return 0.70
        elif obi <= 0.0:
            return 0.50
        elif obi <= 0.30:
            return 0.30
        else:
            return 0.10  # Strong buy pressure → bad for short


def _score_spread(spread_ratio: float) -> float:
    """Score spread tightness (0-1). Lower ratio = better."""
    if spread_ratio <= 0.5:
        return 1.0  # Unusually tight
    elif spread_ratio <= 1.0:
        return 0.85  # Normal or better
    elif spread_ratio <= 1.5:
        return 0.60  # Slightly wide
    elif spread_ratio <= 2.0:
        return 0.35  # Wide
    else:
        return 0.10  # Very wide — bad microstructure


def _score_vwap(vwap_dev_pct: float, direction: str) -> float:
    """Score VWAP proximity and direction (0-1).

    For longs: price below VWAP is better (negative dev).
    For shorts: price above VWAP is better (positive dev).
    """
    dev = abs(vwap_dev_pct)

    if direction == "long":
        if vwap_dev_pct <= -0.003:
            return 0.90  # Below VWAP — good for longs
        elif vwap_dev_pct <= 0:
            return 0.75
        elif vwap_dev_pct <= 0.003:
            return 0.55  # Slightly above VWAP
        else:
            return max(0.20, 0.55 - dev * 50)
    else:
        if vwap_dev_pct >= 0.003:
            return 0.90  # Above VWAP — good for shorts
        elif vwap_dev_pct >= 0:
            return 0.75
        elif vwap_dev_pct >= -0.003:
            return 0.55
        else:
            return max(0.20, 0.55 - dev * 50)


def _score_volume(volume_ratio: float) -> float:
    """Score volume support (0-1). Higher volume = better."""
    if volume_ratio >= 2.0:
        return 1.0
    elif volume_ratio >= 1.5:
        return 0.85
    elif volume_ratio >= 1.0:
        return 0.65
    elif volume_ratio >= 0.7:
        return 0.45
    elif volume_ratio >= 0.5:
        return 0.30
    else:
        return 0.15  # Dead market


def _score_atr(atr_pct: float) -> float:
    """Score ATR reasonableness (0-1).

    Too low ATR = no volatility = hard to profit.
    Too high ATR = excessive volatility = hard to manage risk.
    """
    if atr_pct <= 0.001:
        return 0.20  # Too low
    elif atr_pct <= 0.005:
        return 0.60
    elif atr_pct <= 0.015:
        return 0.90  # Sweet spot
    elif atr_pct <= 0.03:
        return 0.70
    elif atr_pct <= 0.05:
        return 0.45
    else:
        return 0.20  # Extreme volatility


# ---------------------------------------------------------------------------
# Grade assignment and helpers
# ---------------------------------------------------------------------------


def _assign_grade(score: float, config: PrecisionConfig) -> str:
    """Assign letter grade based on score and config thresholds."""
    if score >= config.grade_a_threshold:
        return "A"
    elif score >= config.grade_b_threshold:
        return "B"
    elif score >= config.grade_c_threshold:
        return "C"
    elif score >= config.grade_d_threshold:
        return "D"
    else:
        return "F"


def _confidence_adjustment(grade: str, config: PrecisionConfig) -> float:
    """Compute confidence adjustment based on grade."""
    if grade == "A":
        return config.conf_boost_a
    elif grade == "B":
        return config.conf_boost_b
    elif grade == "C":
        return 0.0
    elif grade == "D":
        return config.conf_penalty_d
    else:  # F
        return config.conf_penalty_f


def _compute_recommended_entry(
    direction: str,
    current_price: float,
    vwap_dev_pct: float,
) -> float:
    """Compute recommended entry price.

    Place limit at a favourable offset from current price.
    """
    band = 0.003  # 0.3% VWAP band
    if direction == "long":
        return current_price * (1.0 - band)
    else:
        return current_price * (1.0 + band)


def _build_reason(
    grade: str,
    score: float,
    obi_score: float,
    spread_score: float,
) -> str:
    """Build a human-readable reason string."""
    parts = [f"grade={grade}", f"score={score:.2f}"]
    if obi_score < 0.30:
        parts.append("weak_obi")
    if spread_score < 0.35:
        parts.append("wide_spread")
    if grade == "F":
        parts.append("REJECTED")
    return "; ".join(parts)
