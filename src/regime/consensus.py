"""Consensus layer for regime detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from src.core.constants import HERMES_CRITICAL, REGIME_CRISIS, REGIME_RANGING, REGIME_VOLATILE


@dataclass(frozen=True)
class ConsensusResult:
    regime: str
    confidence: float
    votes: dict[str, int]
    reason: str


class RegimeConsensus:
    """Merge classifier outputs with safety-biased consensus rules."""

    def resolve(
        self,
        classifier_votes: Mapping[str, str],
        *,
        hermes_urgency: Optional[str] = None,
        hermes_sentiment_score: Optional[float] = None,
    ) -> ConsensusResult:
        if hermes_urgency == HERMES_CRITICAL and (
            hermes_sentiment_score is None or hermes_sentiment_score < -70.0
        ):
            return ConsensusResult(
                regime=REGIME_CRISIS,
                confidence=1.0,
                votes={REGIME_CRISIS: 1},
                reason="hermes_critical_override",
            )

        vote_count: dict[str, int] = {}
        for vote in classifier_votes.values():
            vote_count[vote] = vote_count.get(vote, 0) + 1

        total = max(len(classifier_votes), 1)
        crisis_votes = vote_count.get(REGIME_CRISIS, 0)
        volatile_votes = vote_count.get(REGIME_VOLATILE, 0)

        if crisis_votes >= 1:
            return ConsensusResult(
                regime=REGIME_CRISIS,
                confidence=crisis_votes / total,
                votes=vote_count,
                reason="safety_any_vote_crisis",
            )
        if volatile_votes >= 1:
            return ConsensusResult(
                regime=REGIME_VOLATILE,
                confidence=volatile_votes / total,
                votes=vote_count,
                reason="safety_any_vote_volatile",
            )

        # TRENDING/RANGING require 3-of-4 agreement
        best_regime = max(vote_count.items(), key=lambda x: x[1])[0] if vote_count else REGIME_RANGING
        best_votes = vote_count.get(best_regime, 0)
        if best_votes >= 3:
            return ConsensusResult(
                regime=best_regime,
                confidence=best_votes / total,
                votes=vote_count,
                reason="majority_3of4",
            )

        return ConsensusResult(
            regime=REGIME_RANGING,
            confidence=0.25,
            votes=vote_count,
            reason="default_ranging_low_consensus",
        )
