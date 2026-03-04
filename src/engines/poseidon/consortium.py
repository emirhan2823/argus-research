"""Consortium internal scoring engine.

Each consortium groups related indicators and computes an internal
weighted score.  Indicator weights are dynamically adjusted based on
their IndicatorProfile optimal/adverse conditions.

The output is a ConsortiumResult with:
- score: -1.0 (strong short) to +1.0 (strong long)
- confidence: |score|, how certain the consortium is
- bias: "long" / "short" / None
- active/total indicator counts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.engines.poseidon.profiles import IndicatorProfile


@dataclass
class IndicatorVote:
    """One indicator's vote within a consortium."""
    profile: IndicatorProfile
    bias: Optional[str]   # "long", "short", or None (neutral/abstain)
    strength: float       # 0.0-1.0, how extreme the reading is


@dataclass
class ConsortiumResult:
    """Aggregated result from one consortium."""
    consortium: str
    score: float               # -1.0 to +1.0
    confidence: float          # 0.0 to 1.0 (= |score|)
    bias: Optional[str]        # "long", "short", or None
    active_indicators: int     # How many voted (non-None bias)
    total_indicators: int      # Total indicators in this consortium


def compute_consortium_score(
    consortium: str,
    votes: list[IndicatorVote],
    features: dict[str, Any],
    regime: str,
) -> ConsortiumResult:
    """Compute the internal weighted score for one consortium.

    Each vote's weight is dynamically adjusted via its profile's
    optimal/adverse conditions.  Votes are aggregated as:

        score = Σ(effective_weight × direction × strength) / Σ(effective_weight)

    where direction = +1 for long, -1 for short, 0 for neutral.
    """
    total_weight = 0.0
    weighted_signal = 0.0
    active_count = 0

    for vote in votes:
        eff_w = vote.profile.effective_weight(features, regime)
        total_weight += eff_w

        if vote.bias is not None:
            active_count += 1
            direction = 1.0 if vote.bias == "long" else -1.0
            weighted_signal += eff_w * direction * vote.strength

    if total_weight < 1e-9:
        return ConsortiumResult(
            consortium=consortium,
            score=0.0,
            confidence=0.0,
            bias=None,
            active_indicators=0,
            total_indicators=len(votes),
        )

    score = weighted_signal / total_weight
    score = max(-1.0, min(1.0, score))
    confidence = abs(score)
    bias: str | None = None
    if score > 0.01:
        bias = "long"
    elif score < -0.01:
        bias = "short"

    return ConsortiumResult(
        consortium=consortium,
        score=round(score, 6),
        confidence=round(confidence, 6),
        bias=bias,
        active_indicators=active_count,
        total_indicators=len(votes),
    )
