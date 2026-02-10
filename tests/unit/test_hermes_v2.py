from __future__ import annotations

from src.core.constants import REGIME_RANGING
from src.engines.hermes.engine import HermesEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def test_hermes_short_on_critical_negative() -> None:
    engine = HermesEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            hermes_sentiment_score=-90.0,
            hermes_sentiment_confidence=0.8,
            hermes_urgency="CRITICAL",
        ),
    )
    assert sig is not None
    assert sig.bias == "short"
    assert sig.engine == "HERMES"


def test_hermes_long_on_positive_extreme() -> None:
    engine = HermesEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            hermes_sentiment_score=75.0,
            hermes_sentiment_confidence=0.7,
            hermes_urgency="HIGH",
        ),
    )
    assert sig is not None
    assert sig.bias == "long"


def test_hermes_block_logic() -> None:
    engine = HermesEngine()
    assert engine.is_entry_blocked(sentiment_score=-55.0, urgency="HIGH") is True
    assert engine.is_entry_blocked(sentiment_score=10.0, urgency="LOW") is False


def test_hermes_position_instruction() -> None:
    engine = HermesEngine()
    assert engine.position_instruction(sentiment_score=-90.0, urgency="CRITICAL").action == "CLOSE_POSITION"
    assert engine.position_instruction(sentiment_score=-60.0, urgency="HIGH").action == "ADJUST_SL"
    assert engine.position_instruction(sentiment_score=70.0, urgency="MEDIUM").action == "ADJUST_TP"
