"""Indicator profiles and optimal condition definitions for the Consortium system.

Each indicator has a profile defining:
- Which consortium it belongs to (mr, volume, trend, structure)
- A base weight (used in consortium internal scoring)
- Optimal conditions: when these are met, the indicator's weight gets boosted
- Adverse conditions: when these are met, the indicator's weight gets penalized

The Condition dataclass evaluates feature values against thresholds to
determine whether an indicator is operating in its optimal or adverse zone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Condition evaluation ─────────────────────────────────────────


@dataclass(frozen=True)
class Condition:
    """A single condition that can boost or penalize an indicator's weight.

    Parameters
    ----------
    feature : str
        Feature name from FeatureVector or regime string.
    operator : str
        One of "lt", "gt", "eq", "neq", "between", "in".
    value : Any
        Threshold value.  For "between", a (low, high) tuple.
        For "in", a set/list of allowed values.
    boost_factor : float
        Multiplier applied to indicator weight when this condition is true.
        >1.0 = boost, <1.0 = penalty.
    """
    feature: str
    operator: str
    value: Any
    boost_factor: float

    def evaluate(self, features: dict[str, Any], regime: str) -> bool:
        """Return True if this condition is satisfied."""
        if self.feature == "regime":
            actual = regime
        else:
            actual = features.get(self.feature)

        if actual is None:
            return False

        try:
            if self.operator == "lt":
                return float(actual) < float(self.value)
            if self.operator == "gt":
                return float(actual) > float(self.value)
            if self.operator == "eq":
                return str(actual) == str(self.value)
            if self.operator == "neq":
                return str(actual) != str(self.value)
            if self.operator == "between":
                lo, hi = self.value
                return float(lo) <= float(actual) <= float(hi)
            if self.operator == "in":
                return str(actual) in {str(v) for v in self.value}
        except (TypeError, ValueError):
            return False

        return False


# ── Indicator Profile ────────────────────────────────────────────


@dataclass
class IndicatorProfile:
    """Meta-profile for one indicator inside a consortium.

    The effective weight at runtime is:
        effective = base_weight * Π(boost_factor for each met optimal condition)
                                * Π(boost_factor for each met adverse condition)

    All boost_factors are multiplied together.  Optimal conditions should
    have boost_factor > 1.0, adverse conditions should have boost_factor < 1.0.
    """
    name: str
    consortium: str  # "mr", "volume", "trend", "structure"
    base_weight: float

    optimal_conditions: list[Condition] = field(default_factory=list)
    adverse_conditions: list[Condition] = field(default_factory=list)

    def effective_weight(self, features: dict[str, Any], regime: str) -> float:
        """Compute the dynamic weight given current market conditions."""
        w = self.base_weight
        for cond in self.optimal_conditions:
            if cond.evaluate(features, regime):
                w *= cond.boost_factor
        for cond in self.adverse_conditions:
            if cond.evaluate(features, regime):
                w *= cond.boost_factor
        return max(w, 0.01)  # Never fully zero


# ── Default Indicator Profiles ───────────────────────────────────


def build_default_profiles() -> dict[str, IndicatorProfile]:
    """Build the default set of indicator profiles.

    Returns a dict keyed by indicator name.
    """
    profiles: dict[str, IndicatorProfile] = {}

    # ── MR Consortium ──────────────────────────────────────────
    profiles["rsi_14"] = IndicatorProfile(
        name="rsi_14",
        consortium="mr",
        base_weight=1.5,
        optimal_conditions=[
            Condition("adx_14", "lt", 25.0, 1.8),       # Low ADX → MR friendly
            Condition("regime", "eq", "RANGING", 1.3),   # Ranging = ideal for MR
        ],
        adverse_conditions=[
            Condition("adx_14", "gt", 40.0, 0.6),       # Strong trend → RSI misleading
            Condition("regime", "eq", "TRENDING", 0.7),
        ],
    )

    profiles["cci_20"] = IndicatorProfile(
        name="cci_20",
        consortium="mr",
        base_weight=1.5,
        optimal_conditions=[
            Condition("bb_width", "gt", 0.04, 1.5),     # Wide bands → CCI reliable
        ],
        adverse_conditions=[
            Condition("bb_width", "lt", 0.015, 0.7),    # Narrow bands → CCI noisy
        ],
    )

    profiles["willr_14"] = IndicatorProfile(
        name="willr_14",
        consortium="mr",
        base_weight=1.0,
        optimal_conditions=[
            Condition("volume_ratio", "gt", 1.3, 1.6),  # High volume → WillR reliable
        ],
        adverse_conditions=[
            Condition("volume_ratio", "lt", 0.5, 0.5),  # Low volume → noisy
        ],
    )

    profiles["harsi"] = IndicatorProfile(
        name="harsi",
        consortium="mr",
        base_weight=2.5,
        optimal_conditions=[
            Condition("candle_count", "gt", 100.0, 1.3), # Enough data for smoothing
        ],
        adverse_conditions=[
            Condition("candle_count", "lt", 50.0, 0.5),  # Too few candles
        ],
    )

    profiles["wave_trend"] = IndicatorProfile(
        name="wave_trend",
        consortium="mr",
        base_weight=2.0,
        optimal_conditions=[
            Condition("regime", "neq", "CRISIS", 1.2),   # Anything but crisis
        ],
        adverse_conditions=[
            Condition("regime", "eq", "CRISIS", 0.3),    # Crisis kills MR
        ],
    )

    # ── Volume Consortium ──────────────────────────────────────
    profiles["cmf_20"] = IndicatorProfile(
        name="cmf_20",
        consortium="volume",
        base_weight=1.5,
        optimal_conditions=[
            Condition("cmf_20", "gt", 0.15, 1.5),       # Extreme CMF is more reliable
            Condition("cmf_20", "lt", -0.15, 1.5),
        ],
        adverse_conditions=[
            Condition("cmf_20", "between", (-0.05, 0.05), 0.6),  # Neutral CMF = noise
        ],
    )

    profiles["obv_slope"] = IndicatorProfile(
        name="obv_slope",
        consortium="volume",
        base_weight=1.0,
        optimal_conditions=[
            Condition("volume_ratio", "gt", 1.2, 1.4),
        ],
        adverse_conditions=[
            Condition("volume_ratio", "lt", 0.6, 0.5),
        ],
    )

    profiles["volume_delta"] = IndicatorProfile(
        name="volume_delta",
        consortium="volume",
        base_weight=1.0,
        optimal_conditions=[
            Condition("volume_ratio", "gt", 1.0, 1.3),
        ],
        adverse_conditions=[
            Condition("volume_ratio", "lt", 0.5, 0.5),
        ],
    )

    profiles["volume_ratio_ind"] = IndicatorProfile(
        name="volume_ratio_ind",
        consortium="volume",
        base_weight=1.0,
        optimal_conditions=[
            Condition("adx_14", "lt", 30.0, 1.2),
        ],
        adverse_conditions=[
            Condition("adx_14", "gt", 50.0, 0.7),
        ],
    )

    # ── Trend Consortium ───────────────────────────────────────
    profiles["adx_14"] = IndicatorProfile(
        name="adx_14",
        consortium="trend",
        base_weight=1.5,
        optimal_conditions=[
            Condition("regime", "eq", "TRENDING", 1.5),
        ],
        adverse_conditions=[
            Condition("regime", "eq", "RANGING", 0.7),
        ],
    )

    profiles["ema_cross"] = IndicatorProfile(
        name="ema_cross",
        consortium="trend",
        base_weight=1.2,
        optimal_conditions=[
            Condition("hurst_exponent", "gt", 0.55, 1.4),  # Trending Hurst
        ],
        adverse_conditions=[
            Condition("hurst_exponent", "lt", 0.40, 0.6),  # Mean-reverting Hurst
        ],
    )

    profiles["lr_slope"] = IndicatorProfile(
        name="lr_slope",
        consortium="trend",
        base_weight=1.0,
        optimal_conditions=[
            Condition("lr_r_squared", "gt", 0.70, 1.5),  # High R² → slope reliable
        ],
        adverse_conditions=[
            Condition("lr_r_squared", "lt", 0.30, 0.5),  # Low R² → noise
        ],
    )

    profiles["aroon"] = IndicatorProfile(
        name="aroon",
        consortium="trend",
        base_weight=1.0,
        optimal_conditions=[
            Condition("adx_14", "gt", 25.0, 1.3),
        ],
        adverse_conditions=[
            Condition("adx_14", "lt", 15.0, 0.6),
        ],
    )

    profiles["roc_10"] = IndicatorProfile(
        name="roc_10",
        consortium="trend",
        base_weight=0.8,
        optimal_conditions=[
            Condition("volume_ratio", "gt", 1.0, 1.3),
        ],
        adverse_conditions=[
            Condition("volume_ratio", "lt", 0.5, 0.6),
        ],
    )

    # ── Structure Consortium ───────────────────────────────────
    profiles["bb_pct_b"] = IndicatorProfile(
        name="bb_pct_b",
        consortium="structure",
        base_weight=2.0,
        optimal_conditions=[
            Condition("bb_width", "gt", 0.03, 1.3),     # Wide bands → %B meaningful
        ],
        adverse_conditions=[
            Condition("bb_width", "lt", 0.01, 0.5),     # Squeeze → %B unreliable
        ],
    )

    profiles["vwap_dev"] = IndicatorProfile(
        name="vwap_dev",
        consortium="structure",
        base_weight=2.0,
        optimal_conditions=[
            Condition("volume_ratio", "gt", 1.0, 1.3),
        ],
        adverse_conditions=[
            Condition("volume_ratio", "lt", 0.5, 0.6),
        ],
    )

    profiles["entropy_st"] = IndicatorProfile(
        name="entropy_st",
        consortium="structure",
        base_weight=2.0,
        optimal_conditions=[
            Condition("candle_count", "gt", 100.0, 1.2),
        ],
        adverse_conditions=[
            Condition("candle_count", "lt", 50.0, 0.5),
        ],
    )

    profiles["supertrend"] = IndicatorProfile(
        name="supertrend",
        consortium="structure",
        base_weight=1.5,
        optimal_conditions=[
            Condition("adx_14", "gt", 20.0, 1.3),
        ],
        adverse_conditions=[
            Condition("adx_14", "lt", 10.0, 0.5),
        ],
    )

    return profiles


# Consortium type constants
CONSORTIUM_MR = "mr"
CONSORTIUM_VOLUME = "volume"
CONSORTIUM_TREND = "trend"
CONSORTIUM_STRUCTURE = "structure"

ALL_CONSORTIUMS = (CONSORTIUM_MR, CONSORTIUM_VOLUME, CONSORTIUM_TREND, CONSORTIUM_STRUCTURE)
