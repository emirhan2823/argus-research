from __future__ import annotations

from src.core.constants import REGIME_CRISIS, REGIME_RANGING, REGIME_TRENDING, REGIME_VOLATILE
from src.regime.consensus import RegimeConsensus
from src.regime.rule_based import RuleBasedInput, RuleBasedRegimeClassifier


def test_rule_based_crisis_from_hermes_override() -> None:
    classifier = RuleBasedRegimeClassifier()
    regime = classifier.classify(
        RuleBasedInput(
            adx_14=30.0,
            price_vs_ma200=0.02,
            ema_21_vs_55=0.01,
            hurst_exponent=0.55,
            atr_ratio_5_20=1.0,
            vol_multiple_60d=1.2,
            hermes_urgency="CRITICAL",
            hermes_sentiment_score=-90.0,
        )
    )
    assert regime == REGIME_CRISIS


def test_rule_based_volatile_beats_trending_priority() -> None:
    classifier = RuleBasedRegimeClassifier()
    regime = classifier.classify(
        RuleBasedInput(
            adx_14=35.0,
            price_vs_ma200=0.05,
            ema_21_vs_55=0.03,
            hurst_exponent=0.50,
            atr_ratio_5_20=2.0,
            vol_multiple_60d=1.5,
            directional_alignment_candles=40,
        )
    )
    assert regime == REGIME_VOLATILE


def test_rule_based_trending() -> None:
    classifier = RuleBasedRegimeClassifier()
    regime = classifier.classify(
        RuleBasedInput(
            adx_14=35.0,
            price_vs_ma200=0.03,
            ema_21_vs_55=0.02,
            hurst_exponent=0.60,
            atr_ratio_5_20=1.1,
            vol_multiple_60d=1.1,
            directional_alignment_candles=24,
        )
    )
    assert regime == REGIME_TRENDING


def test_rule_based_weak_trend_is_ranging() -> None:
    """ADX 25-32 with non-persistent Hurst should classify as RANGING."""
    classifier = RuleBasedRegimeClassifier()
    regime = classifier.classify(
        RuleBasedInput(
            adx_14=28.0,
            price_vs_ma200=0.03,
            ema_21_vs_55=0.02,
            hurst_exponent=0.55,
            atr_ratio_5_20=1.1,
            vol_multiple_60d=1.1,
            directional_alignment_candles=24,
        )
    )
    assert regime == REGIME_RANGING


def test_rule_based_ranging_default() -> None:
    classifier = RuleBasedRegimeClassifier()
    regime = classifier.classify(
        RuleBasedInput(
            adx_14=14.0,
            price_vs_ma200=0.0,
            ema_21_vs_55=0.0,
            hurst_exponent=0.40,
            atr_ratio_5_20=1.0,
            vol_multiple_60d=1.0,
        )
    )
    assert regime == REGIME_RANGING


def test_consensus_hermes_forces_crisis() -> None:
    result = RegimeConsensus().resolve(
        {"c1": REGIME_TRENDING, "c2": REGIME_RANGING, "c3": REGIME_TRENDING, "c4": REGIME_RANGING},
        hermes_urgency="CRITICAL",
        hermes_sentiment_score=-80.0,
    )
    assert result.regime == REGIME_CRISIS
    assert result.reason == "hermes_critical_override"


def test_consensus_any_volatile_vote_wins_for_safety() -> None:
    result = RegimeConsensus().resolve(
        {"c1": REGIME_TRENDING, "c2": REGIME_RANGING, "c3": REGIME_VOLATILE, "c4": REGIME_TRENDING},
    )
    assert result.regime == REGIME_VOLATILE


def test_consensus_trending_needs_three_votes() -> None:
    result = RegimeConsensus().resolve(
        {"c1": REGIME_TRENDING, "c2": REGIME_TRENDING, "c3": REGIME_TRENDING, "c4": REGIME_RANGING},
    )
    assert result.regime == REGIME_TRENDING
    assert result.reason == "majority_3of4"


def test_consensus_fallback_to_ranging_when_no_majority() -> None:
    result = RegimeConsensus().resolve(
        {"c1": REGIME_TRENDING, "c2": REGIME_RANGING, "c3": REGIME_TRENDING, "c4": REGIME_RANGING},
    )
    assert result.regime == REGIME_RANGING
    assert result.reason == "default_ranging_low_consensus"
