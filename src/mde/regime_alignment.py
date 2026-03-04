"""Regime-Strategy Alignment Scoring.

Enforces that engines only fire when regime conditions are strongly
favorable, not borderline. Returns a confidence multiplier (0.70-1.15)
that naturally filters out borderline signals via the tightened
MIN_CONFIDENCE gate (0.65).

Integration point: Step 6.55 (after signal quality, before whale boost).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_GEMINI,
    ENGINE_HERMES,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_PHOENIX,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
)


@dataclass(frozen=True)
class RegimeAlignmentResult:
    """Result of regime-strategy alignment scoring."""

    aligned: bool
    alignment_score: float       # 0.0-1.0
    confidence_multiplier: float  # 0.70-1.15
    reason: str


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_to_multiplier(score: float) -> float:
    """Map alignment score to a confidence multiplier.

    score < 0.30  →  0.80  (moderate penalty for borderline)
    score 0.30-0.70 → linear 0.90-1.0
    score > 0.70  →  1.0 + (score-0.70)*0.50 capped at 1.15
    """
    if score < 0.30:
        return 0.80
    if score <= 0.70:
        return 0.90 + (score - 0.30) * (0.10 / 0.40)
    return min(1.0 + (score - 0.70) * 0.50, 1.15)


def score_regime_alignment(
    *,
    engine: str,
    regime: str,
    regime_confidence: float,
    candles_in_regime: int,
    adx_14: float,
    hurst_exponent: float,
    atr_ratio_5_20: float,
) -> RegimeAlignmentResult:
    """Score how well the engine matches the current regime conditions.

    Each engine has strict requirements beyond the basic regime classification.
    Borderline regime conditions produce a low multiplier that naturally
    filters signals out at Gate 5 (MIN_CONFIDENCE = 0.65).
    """
    if engine == ENGINE_TITAN:
        return _score_titan(regime, adx_14, regime_confidence, candles_in_regime)

    if engine == ENGINE_NAUTILUS:
        return _score_nautilus(regime, adx_14, hurst_exponent, regime_confidence)

    if engine == ENGINE_HYDRA:
        return _score_hydra(regime, adx_14, hurst_exponent, atr_ratio_5_20, regime_confidence)

    if engine == ENGINE_PHOENIX:
        return _score_phoenix(regime, regime_confidence)

    if engine == ENGINE_HERMES:
        # Sentiment engine is regime-agnostic
        return RegimeAlignmentResult(
            aligned=True,
            alignment_score=0.70,
            confidence_multiplier=1.0,
            reason="hermes_regime_agnostic",
        )

    if engine == ENGINE_GEMINI:
        return _score_gemini(regime, adx_14, hurst_exponent)

    if engine == ENGINE_AEGEAN:
        return _score_aegean(regime, adx_14, hurst_exponent, regime_confidence, atr_ratio_5_20)

    if engine == ENGINE_POSEIDON:
        return _score_poseidon(regime, regime_confidence)

    # Unknown engine: neutral
    return RegimeAlignmentResult(
        aligned=True,
        alignment_score=0.50,
        confidence_multiplier=1.0,
        reason="unknown_engine_neutral",
    )


# ── Per-Engine Scoring ──────────────────────────────────────────────


def _score_titan(
    regime: str, adx_14: float, regime_confidence: float, candles_in_regime: int,
) -> RegimeAlignmentResult:
    """TITAN needs TRENDING with strong ADX, high confidence, established regime."""
    if regime != "TRENDING":
        return RegimeAlignmentResult(
            aligned=False, alignment_score=0.0,
            confidence_multiplier=0.70, reason="titan_wrong_regime",
        )

    factors = []

    # ADX strength: want >=30 (strong trend), 25-30 is borderline
    if adx_14 >= 35:
        factors.append(1.0)
    elif adx_14 >= 30:
        factors.append(0.80)
    elif adx_14 >= 25:
        factors.append(0.50)  # Borderline
    else:
        factors.append(0.20)

    # Regime confidence
    if regime_confidence >= 0.70:
        factors.append(1.0)
    elif regime_confidence >= 0.60:
        factors.append(0.75)
    else:
        factors.append(0.40)

    # Regime establishment
    if candles_in_regime >= 12:
        factors.append(1.0)
    elif candles_in_regime >= 6:
        factors.append(0.75)
    elif candles_in_regime >= 3:
        factors.append(0.45)
    else:
        factors.append(0.20)

    score = sum(factors) / len(factors)
    return RegimeAlignmentResult(
        aligned=score >= 0.40,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"titan_trend_alignment adx={adx_14:.1f} conf={regime_confidence:.2f} candles={candles_in_regime}",
    )


def _score_nautilus(
    regime: str, adx_14: float, hurst_exponent: float, regime_confidence: float,
) -> RegimeAlignmentResult:
    """NAUTILUS needs RANGING with low ADX, mean-reverting Hurst."""
    if regime != "RANGING":
        return RegimeAlignmentResult(
            aligned=False, alignment_score=0.0,
            confidence_multiplier=0.70, reason="nautilus_wrong_regime",
        )

    factors = []

    # ADX: want <=18 (clear range), 18-22 is borderline
    if adx_14 <= 15:
        factors.append(1.0)
    elif adx_14 <= 18:
        factors.append(0.80)
    elif adx_14 <= 22:
        factors.append(0.50)
    else:
        factors.append(0.20)

    # Hurst: want < 0.42 (mean-reverting)
    if hurst_exponent <= 0.35:
        factors.append(1.0)
    elif hurst_exponent <= 0.42:
        factors.append(0.75)
    elif hurst_exponent <= 0.50:
        factors.append(0.45)
    else:
        factors.append(0.20)

    # Regime confidence
    if regime_confidence >= 0.65:
        factors.append(1.0)
    elif regime_confidence >= 0.55:
        factors.append(0.70)
    else:
        factors.append(0.35)

    score = sum(factors) / len(factors)
    return RegimeAlignmentResult(
        aligned=score >= 0.40,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"nautilus_range_alignment adx={adx_14:.1f} hurst={hurst_exponent:.3f}",
    )


def _score_hydra(
    regime: str, adx_14: float, hurst_exponent: float,
    atr_ratio_5_20: float, regime_confidence: float,
) -> RegimeAlignmentResult:
    """HYDRA needs RANGING + calm volatility for scalping."""
    if regime != "RANGING":
        return RegimeAlignmentResult(
            aligned=False, alignment_score=0.0,
            confidence_multiplier=0.70, reason="hydra_wrong_regime",
        )

    factors = []

    # ADX: same as Nautilus
    if adx_14 <= 15:
        factors.append(1.0)
    elif adx_14 <= 18:
        factors.append(0.80)
    elif adx_14 <= 22:
        factors.append(0.50)
    else:
        factors.append(0.20)

    # Hurst: mean-reverting preferred
    if hurst_exponent <= 0.40:
        factors.append(1.0)
    elif hurst_exponent <= 0.48:
        factors.append(0.60)
    else:
        factors.append(0.25)

    # ATR ratio: need calm market (< 1.3)
    if atr_ratio_5_20 <= 0.9:
        factors.append(1.0)
    elif atr_ratio_5_20 <= 1.1:
        factors.append(0.85)
    elif atr_ratio_5_20 <= 1.3:
        factors.append(0.55)
    else:
        factors.append(0.20)  # Too volatile for scalping

    # Regime confidence
    if regime_confidence >= 0.60:
        factors.append(1.0)
    elif regime_confidence >= 0.50:
        factors.append(0.65)
    else:
        factors.append(0.30)

    score = sum(factors) / len(factors)
    return RegimeAlignmentResult(
        aligned=score >= 0.40,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"hydra_scalp_alignment adx={adx_14:.1f} atr_ratio={atr_ratio_5_20:.2f}",
    )


def _score_phoenix(regime: str, regime_confidence: float) -> RegimeAlignmentResult:
    """PHOENIX is regime-tolerant (carry strategies work broadly)."""
    # Phoenix always gets at least 0.50 alignment
    if regime == "CRISIS":
        score = 0.30
    elif regime == "VOLATILE":
        score = 0.60  # Phoenix works well in volatile
    else:
        score = 0.65

    return RegimeAlignmentResult(
        aligned=score >= 0.30,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"phoenix_carry_alignment regime={regime}",
    )


def _score_gemini(
    regime: str, adx_14: float, hurst_exponent: float,
) -> RegimeAlignmentResult:
    """GEMINI (pairs trading) needs ranging/stable conditions."""
    if regime not in ("RANGING", "TRENDING"):
        return RegimeAlignmentResult(
            aligned=False, alignment_score=0.20,
            confidence_multiplier=0.75, reason="gemini_unfavorable_regime",
        )

    factors = []

    # ADX: moderate is fine for pairs
    if adx_14 <= 25:
        factors.append(0.85)
    elif adx_14 <= 35:
        factors.append(0.65)
    else:
        factors.append(0.35)

    # Hurst: mean-reverting preferred for spread convergence
    if hurst_exponent <= 0.45:
        factors.append(1.0)
    elif hurst_exponent <= 0.55:
        factors.append(0.60)
    else:
        factors.append(0.30)

    score = sum(factors) / len(factors)
    return RegimeAlignmentResult(
        aligned=score >= 0.40,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"gemini_pairs_alignment adx={adx_14:.1f} hurst={hurst_exponent:.3f}",
    )


def _score_poseidon(regime: str, regime_confidence: float) -> RegimeAlignmentResult:
    """POSEIDON (MR Consortium) thrives in RANGING, works in VOLATILE, weak in TRENDING."""
    if regime == "CRISIS":
        return RegimeAlignmentResult(
            aligned=False, alignment_score=0.0,
            confidence_multiplier=0.70, reason="poseidon_crisis_blocked",
        )

    if regime == "RANGING":
        score = 0.90
        reason = "poseidon_ranging_ideal"
    elif regime == "VOLATILE":
        score = 0.70
        reason = "poseidon_volatile_ok"
    else:  # TRENDING
        score = 0.45
        reason = "poseidon_trending_weak"

    # Regime confidence boost/penalty
    if regime_confidence >= 0.65:
        score = min(score + 0.05, 1.0)
    elif regime_confidence < 0.45:
        score = max(score - 0.10, 0.0)

    return RegimeAlignmentResult(
        aligned=score >= 0.35,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"{reason} conf={regime_confidence:.2f}",
    )


def _score_aegean(
    regime: str,
    adx_14: float,
    hurst_exponent: float,
    regime_confidence: float,
    atr_ratio_5_20: float,
) -> RegimeAlignmentResult:
    """AEGEAN works across TRENDING/RANGING/VOLATILE with per-regime scoring."""
    if regime == "CRISIS":
        return RegimeAlignmentResult(
            aligned=False, alignment_score=0.0,
            confidence_multiplier=0.70, reason="aegean_crisis_blocked",
        )

    factors = []

    if regime == "TRENDING":
        factors.append(1.0 if adx_14 >= 30 else (0.75 if adx_14 >= 25 else 0.45))
        factors.append(1.0 if hurst_exponent >= 0.55 else (0.65 if hurst_exponent >= 0.48 else 0.40))
        factors.append(1.0 if regime_confidence >= 0.65 else (0.70 if regime_confidence >= 0.55 else 0.40))
    elif regime == "RANGING":
        factors.append(1.0 if adx_14 <= 18 else (0.80 if adx_14 <= 28 else (0.60 if adx_14 <= 32 else 0.40)))
        factors.append(1.0 if hurst_exponent <= 0.42 else (0.65 if hurst_exponent <= 0.50 else 0.35))
        factors.append(1.0 if regime_confidence >= 0.60 else (0.65 if regime_confidence >= 0.50 else 0.35))
    else:  # VOLATILE
        factors.append(0.75 if atr_ratio_5_20 <= 2.0 else 0.45)
        factors.append(0.70)
        factors.append(1.0 if regime_confidence >= 0.55 else 0.60)

    score = sum(factors) / len(factors)
    return RegimeAlignmentResult(
        aligned=score >= 0.35,
        alignment_score=round(score, 4),
        confidence_multiplier=round(_score_to_multiplier(score), 4),
        reason=f"aegean_mom_lrc_alignment regime={regime} adx={adx_14:.1f} hurst={hurst_exponent:.3f}",
    )
