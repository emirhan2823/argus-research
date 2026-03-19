"""HERMES engine: sentiment-driven signals and veto actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import ENGINE_HERMES, HERMES_CRITICAL, HERMES_HIGH
from src.core.types import EngineSignal, FeatureVector, RegimeState


@dataclass(frozen=True)
class HermesPositionInstruction:
    action: str  # NONE|BLOCK_ENTRY|CLOSE_POSITION|ADJUST_SL|ADJUST_TP
    reason: str


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class HermesEngine:
    """News/sentiment engine with veto and position-management hints."""

    def __init__(self, *, min_confidence: float = 0.65) -> None:
        self.min_confidence = min_confidence

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        score = features.hermes_sentiment_score
        urgency = features.hermes_urgency
        confidence = features.hermes_sentiment_confidence or 0.0
        if score is None:
            return None

        if urgency == HERMES_CRITICAL and score < -70:
            return self._signal(features, bias="short", score=score, conf=max(confidence, 0.9))
        if score <= -50:
            return self._signal(features, bias="short", score=score, conf=max(confidence, 0.75))
        if score >= 50:
            return self._signal(features, bias="long", score=score, conf=max(confidence, 0.75))
        return None

    def is_entry_blocked(self, *, sentiment_score: Optional[float], urgency: Optional[str]) -> bool:
        if urgency == HERMES_CRITICAL and (sentiment_score is None or sentiment_score < -70):
            return True
        if sentiment_score is not None and sentiment_score < -50:
            return True
        return False

    def position_instruction(
        self,
        *,
        sentiment_score: Optional[float],
        urgency: Optional[str],
    ) -> HermesPositionInstruction:
        if urgency == HERMES_CRITICAL and (sentiment_score is None or sentiment_score < -70):
            return HermesPositionInstruction("CLOSE_POSITION", "critical_negative_news")
        if urgency == HERMES_HIGH and sentiment_score is not None and sentiment_score < -50:
            return HermesPositionInstruction("ADJUST_SL", "high_negative_news")
        if sentiment_score is not None and sentiment_score > 50:
            return HermesPositionInstruction("ADJUST_TP", "positive_news")
        return HermesPositionInstruction("NONE", "no_action")

    def _signal(self, features: FeatureVector, *, bias: str, score: float, conf: float) -> EngineSignal:
        sent_mag = abs(score) / 100.0
        confidence = _clamp(0.60 + sent_mag * 0.35 + conf * 0.1, 0.0, 1.0)
        stop = _clamp(max(features.atr_14_pct, 0.01) * 1.5, 0.005, 0.10)
        return EngineSignal(
            engine=ENGINE_HERMES,
            sub_strategy="news_sentiment",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=confidence,
            stop_distance=stop,
            expected_return=stop * 2.0,
            atr=features.atr_14,
        )
