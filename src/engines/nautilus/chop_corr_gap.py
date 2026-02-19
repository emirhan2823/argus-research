"""CHOP correlation gap detection (D-03).

In CHOP/RANGING regime: if a normally-correlated pair shows one asset
deviating while both remain in the same range → generate convergence signal.
Pure function, no side effects.
"""

from __future__ import annotations

from typing import Optional

from src.core.constants import ENGINE_NAUTILUS, REGIME_RANGING
from src.core.types import EngineSignal, FeatureVector, RegimeState


# --- Thresholds ---
MIN_CORRELATION = 0.60  # Pair must be normally correlated
MAX_ADX = 25.0  # Both assets must be in low-trend environment
MIN_SPREAD_ZSCORE = 1.5  # Minimum deviation to trigger signal
STOP_ZSCORE = 3.0  # Stop at this z-score level
CONFIDENCE_BASE = 0.55  # Base confidence for a correlation gap signal


def detect_chop_correlation_gap(
    features_a: FeatureVector,
    features_b: FeatureVector,
    regime_a: RegimeState,
    regime_b: RegimeState,
    correlation: float,
    spread_zscore: float,
    half_life: float | None = None,
    is_cointegrated: bool = False,
) -> Optional[EngineSignal]:
    """Generate convergence signal when correlated pair deviates in CHOP.

    Only fires when BOTH assets are in RANGING regime and the pair
    has a correlation >= 0.60. The deviating asset is traded back
    toward the mean.

    Parameters
    ----------
    features_a : FeatureVector
        Features for asset A.
    features_b : FeatureVector
        Features for asset B.
    regime_a : RegimeState
        Regime state for asset A.
    regime_b : RegimeState
        Regime state for asset B.
    correlation : float
        Rolling correlation between the pair.
    spread_zscore : float
        Current spread z-score (positive = A above B relative to mean).
    half_life : float | None
        Mean-reversion half-life in bars (if available).
    is_cointegrated : bool
        Whether the pair passes cointegration tests.

    Returns
    -------
    EngineSignal | None
        A convergence signal for asset A, or None.
    """
    # Both must be in RANGING
    if regime_a.regime != REGIME_RANGING or regime_b.regime != REGIME_RANGING:
        return None

    # Both must have low ADX (true CHOP)
    if features_a.adx_14 > MAX_ADX or features_b.adx_14 > MAX_ADX:
        return None

    # Pair must be normally correlated
    if abs(correlation) < MIN_CORRELATION:
        return None

    abs_zscore = abs(spread_zscore)

    # Deviation must be significant
    if abs_zscore < MIN_SPREAD_ZSCORE:
        return None

    # Determine direction: trade asset A toward convergence
    if spread_zscore > 0:
        # A is above relative to B → SHORT A (expect convergence down)
        bias = "short"
    else:
        # A is below relative to B → LONG A (expect convergence up)
        bias = "long"

    # Compute confidence
    zscore_factor = min(abs_zscore / STOP_ZSCORE, 1.0)
    corr_factor = min(abs(correlation), 1.0)
    confidence = CONFIDENCE_BASE + 0.20 * zscore_factor + 0.15 * corr_factor

    # Boost for cointegration
    if is_cointegrated:
        confidence += 0.05

    # Boost for fast mean-reversion (short half-life)
    if half_life is not None and half_life > 0 and half_life < 20:
        confidence += 0.05

    confidence = _clamp(confidence, 0.0, 1.0)

    # Stop distance: use asset A's ATR
    atr = features_a.atr_14
    approx_price = max(atr / max(features_a.atr_14_pct, 1e-6), 1.0)
    stop_distance = _clamp((atr * 1.5) / approx_price, 0.001, 0.10)

    # Expected return: proportional to z-score deviation
    # Target is z-score returning to ~0.5 (partial mean reversion)
    target_zscore_move = max(abs_zscore - 0.5, 0.5)
    # Map z-score move to price move: rough approximation
    expected_return = _clamp(
        stop_distance * (target_zscore_move / MIN_SPREAD_ZSCORE) * 1.2,
        0.001,
        0.10,
    )

    return EngineSignal(
        engine=ENGINE_NAUTILUS,
        sub_strategy="chop_corr_gap",
        asset_class=features_a.asset_class,
        symbol=features_a.symbol,
        bias=bias,
        confidence=confidence,
        stop_distance=stop_distance,
        expected_return=expected_return,
        atr=atr,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
