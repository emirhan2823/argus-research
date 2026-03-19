from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from argus_py.council.defs import Vote
from argus_py.models.aether.aether import AetherResult
from argus_py.models.hermes.hermes import HermesResult
from argus_py.models.orion.orion import OrionVote

from .weights import CouncilWeights


class CouncilAction(Enum):
    AGGRESSIVE_BUY = "AGGRESSIVE_BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    TRIM = "TRIM"
    LIQUIDATE = "LIQUIDATE"


class SignalStrength(Enum):
    STRONG = "STRONG"
    NORMAL = "NORMAL"
    WEAK = "WEAK"
    VETOED = "VETOED"


@dataclass
class ModuleVote:
    module: str
    score: float
    direction: str
    confidence: float
    reasons: List[str]


@dataclass
class CouncilDecision:
    action: CouncilAction
    strength: SignalStrength
    confidence: float
    reasoning: str
    votes: List[ModuleVote]
    weights_used: Dict[str, float]


class GrandCouncil:
    """Aggregates all engine votes into final decision."""

    def convene(
        self,
        orion_vote: Optional[OrionVote],
        aether_result: Optional[AetherResult],
        hermes_result: Optional[HermesResult],
        phoenix_score: Optional[float],
        aegean_vote: Optional[ModuleVote],
        regime: str = "TREND",
    ) -> CouncilDecision:
        weights = CouncilWeights.get_for_regime(regime)
        votes = self._collect_votes(orion_vote, aether_result, hermes_result, phoenix_score, aegean_vote)

        weighted_score = self._calculate_weighted_score(votes, weights)
        action = self._determine_action(weighted_score, votes)
        strength = self._check_vetoes(votes, action)

        if strength == SignalStrength.VETOED and action in {CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE}:
            # Apply explicit veto override.
            action = CouncilAction.HOLD

        return CouncilDecision(
            action=action,
            strength=strength,
            confidence=weighted_score,
            reasoning=self._generate_reasoning(votes, action),
            votes=votes,
            weights_used=weights,
        )

    def _collect_votes(
        self,
        orion_vote: Optional[OrionVote],
        aether_result: Optional[AetherResult],
        hermes_result: Optional[HermesResult],
        phoenix_score: Optional[float],
        aegean_vote: Optional[ModuleVote],
    ) -> List[ModuleVote]:
        votes: List[ModuleVote] = []

        normalized_orion = self._normalize_vote(orion_vote, module_name="orion")
        if normalized_orion is not None:
            votes.append(normalized_orion)

        if aether_result is not None:
            votes.append(
                ModuleVote(
                    module="aether",
                    score=float(aether_result.score),
                    direction=self._direction_from_score(float(aether_result.score)),
                    confidence=self._confidence_from_score(float(aether_result.score)),
                    reasons=[aether_result.reasoning],
                )
            )

        if hermes_result is not None:
            score_0_100 = (float(hermes_result.sentiment_score) + 100.0) / 2.0
            votes.append(
                ModuleVote(
                    module="hermes",
                    score=score_0_100,
                    direction=self._direction_from_score(score_0_100),
                    confidence=self._confidence_from_score(score_0_100),
                    reasons=[hermes_result.reasoning],
                )
            )

        if phoenix_score is not None:
            ps = float(phoenix_score)
            votes.append(
                ModuleVote(
                    module="phoenix",
                    score=ps,
                    direction=self._direction_from_score(ps),
                    confidence=self._confidence_from_score(ps),
                    reasons=[f"phoenix_score={ps:.1f}"],
                )
            )

        normalized_aegean = self._normalize_vote(aegean_vote, module_name="aegean")
        if normalized_aegean is not None:
            votes.append(normalized_aegean)

        return votes

    def _normalize_vote(self, vote: Optional[object], module_name: str) -> Optional[ModuleVote]:
        if vote is None:
            return None

        if isinstance(vote, ModuleVote):
            return ModuleVote(
                module=module_name,
                score=float(vote.score),
                direction=vote.direction,
                confidence=max(0.0, min(1.0, float(vote.confidence))),
                reasons=list(vote.reasons),
            )

        if isinstance(vote, Vote):
            return ModuleVote(
                module=module_name,
                score=float(vote.score),
                direction=vote.direction,
                confidence=max(0.0, min(1.0, float(vote.confidence))),
                reasons=list(vote.reasons),
            )

        if all(hasattr(vote, attr) for attr in ("score", "direction", "confidence", "reasons")):
            return ModuleVote(
                module=module_name,
                score=float(getattr(vote, "score")),
                direction=str(getattr(vote, "direction")),
                confidence=max(0.0, min(1.0, float(getattr(vote, "confidence")))),
                reasons=list(getattr(vote, "reasons")),
            )

        return None

    def _calculate_weighted_score(self, votes: List[ModuleVote], weights: Dict[str, float]) -> float:
        total_weight = 0.0
        weighted_sum = 0.0

        for vote in votes:
            w = float(weights.get(vote.module, 0.0))
            if w <= 0:
                continue
            weighted_sum += float(vote.score) * w
            total_weight += w

        if total_weight <= 0:
            return 50.0
        return weighted_sum / total_weight

    def _determine_action(self, score: float, votes: List[ModuleVote]) -> CouncilAction:
        long_count = sum(1 for v in votes if v.direction == "LONG")
        short_count = sum(1 for v in votes if v.direction == "SHORT")

        if score >= 75 and long_count >= 3:
            return CouncilAction.AGGRESSIVE_BUY
        if score >= 60 and long_count >= 2:
            return CouncilAction.ACCUMULATE
        if score <= 35 and short_count >= 3:
            return CouncilAction.LIQUIDATE
        if score <= 45 and short_count >= 2:
            return CouncilAction.TRIM
        return CouncilAction.HOLD

    def _check_vetoes(self, votes: List[ModuleVote], action: CouncilAction) -> SignalStrength:
        aether = next((v for v in votes if v.module == "aether"), None)
        if aether and aether.score < 30 and action in {CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE}:
            return SignalStrength.VETOED

        hermes = next((v for v in votes if v.module == "hermes"), None)
        if hermes and hermes.score < 20 and action in {CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE}:
            return SignalStrength.VETOED

        if not votes or len(votes) < 2:
            return SignalStrength.WEAK

        active = [v.confidence for v in votes if v.confidence > 0]
        if not active:
            return SignalStrength.WEAK

        avg_conf = sum(active) / len(active)
        if all(v > 0.7 for v in active):
            return SignalStrength.STRONG
        if avg_conf < 0.45:
            return SignalStrength.WEAK
        return SignalStrength.NORMAL

    def _generate_reasoning(self, votes: List[ModuleVote], action: CouncilAction) -> str:
        if not votes:
            return f"No module votes available. Action={action.value}."

        parts = [f"{v.module}:{v.direction}@{v.score:.1f}" for v in votes]
        return f"Action={action.value}; " + ", ".join(parts)

    def _direction_from_score(self, score: float) -> str:
        if score >= 55:
            return "LONG"
        if score <= 45:
            return "SHORT"
        return "FLAT"

    def _confidence_from_score(self, score: float) -> float:
        return max(0.0, min(1.0, abs(score - 50.0) / 50.0))
