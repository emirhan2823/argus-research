"""Master signal aggregator for the Consortium system.

Combines results from all four consortiums (MR, Volume, Trend, Structure)
into a single MasterSignal using:

1. External consortium weights (how much each consortium matters overall)
2. Internal-external correlation (α coefficient) — a consortium's internal
   confidence boosts its external weight
3. Agreement bonuses — when multiple consortiums agree, confidence increases
4. Disagreement penalties — conflicting consortiums reduce confidence

The α coefficient controls how tightly internal and external weights are
correlated:
- α = 0.0 → fully independent (internal confidence doesn't affect external weight)
- α = 1.0 → fully dependent (internal confidence 100% determines external weight)
- α = 0.3 → moderate correlation (default)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.engines.poseidon.consortium import ConsortiumResult
from src.engines.poseidon.profiles import (
    ALL_CONSORTIUMS,
    CONSORTIUM_MR,
    CONSORTIUM_STRUCTURE,
    CONSORTIUM_TREND,
    CONSORTIUM_VOLUME,
)


# ── Default consortium weights ───────────────────────────────────

CONSORTIUM_WEIGHTS: dict[str, float] = {
    CONSORTIUM_MR: 0.40,        # MR indicators = primary signal source
    CONSORTIUM_VOLUME: 0.25,    # Volume confirmation
    CONSORTIUM_TREND: 0.20,     # Trend direction (inverted logic for MR)
    CONSORTIUM_STRUCTURE: 0.15, # Price structure and bands
}

# Internal-external correlation coefficient
DEFAULT_ALPHA = 0.3


# ── Master Signal ────────────────────────────────────────────────


@dataclass
class MasterSignal:
    """Final aggregated signal from all consortiums."""
    bias: Optional[str]           # "long", "short", or None
    score: float                  # -1.0 to +1.0
    confidence: float             # 0.0 to 1.0
    agreement_count: int          # How many consortiums agree on the bias
    disagreement_count: int       # How many disagree
    consortium_scores: dict[str, float]  # Individual consortium scores
    agreement_bonus: float        # Applied bonus for agreement
    disagreement_penalty: float   # Applied penalty for disagreement


def compute_master_signal(
    consortium_results: dict[str, ConsortiumResult],
    regime: str,
    *,
    weights: dict[str, float] | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> MasterSignal:
    """Aggregate consortium results into a master signal.

    Parameters
    ----------
    consortium_results : dict[str, ConsortiumResult]
        Results from each consortium, keyed by consortium name.
    regime : str
        Current market regime.
    weights : dict[str, float] | None
        External consortium weights.  Defaults to CONSORTIUM_WEIGHTS.
    alpha : float
        Internal-external correlation coefficient (0.0 to 1.0).
    """
    ext_weights = dict(weights or CONSORTIUM_WEIGHTS)
    alpha = max(0.0, min(1.0, alpha))

    # ── Step 1: Compute effective external weights ───────────
    # Each consortium's external weight is boosted by its internal confidence
    effective_weights: dict[str, float] = {}
    for c_name in ALL_CONSORTIUMS:
        base_w = ext_weights.get(c_name, 0.0)
        result = consortium_results.get(c_name)
        if result is None:
            effective_weights[c_name] = base_w
            continue
        # α-correlated boost: higher internal confidence → higher external weight
        effective_weights[c_name] = base_w * (1.0 + alpha * result.confidence)

    # ── Step 2: Weighted aggregation of consortium scores ────
    total_eff_weight = sum(effective_weights.values())
    if total_eff_weight < 1e-9:
        return MasterSignal(
            bias=None, score=0.0, confidence=0.0,
            agreement_count=0, disagreement_count=0,
            consortium_scores={}, agreement_bonus=0.0,
            disagreement_penalty=0.0,
        )

    # For MR engine: trend consortium acts as CONTRARY indicator
    # If trend says "long" (trending up), MR actually wants to SHORT the top
    # So we invert the trend consortium's score contribution
    weighted_sum = 0.0
    consortium_scores: dict[str, float] = {}
    for c_name in ALL_CONSORTIUMS:
        result = consortium_results.get(c_name)
        if result is None:
            consortium_scores[c_name] = 0.0
            continue
        score = result.score
        # Invert trend for MR: strong trend up = MR should short (counter-trend)
        if c_name == CONSORTIUM_TREND:
            score = -score
        consortium_scores[c_name] = score
        weighted_sum += effective_weights[c_name] * score

    raw_score = weighted_sum / total_eff_weight
    raw_score = max(-1.0, min(1.0, raw_score))

    # ── Step 3: Determine primary bias ───────────────────────
    if raw_score > 0.01:
        primary_bias: str | None = "long"
    elif raw_score < -0.01:
        primary_bias = "short"
    else:
        primary_bias = None

    # ── Step 4: Agreement / Disagreement ─────────────────────
    agree_count = 0
    disagree_count = 0
    for c_name in ALL_CONSORTIUMS:
        result = consortium_results.get(c_name)
        if result is None or result.bias is None:
            continue
        # For trend: compare inverted bias (since trend is contra for MR)
        effective_bias = result.bias
        if c_name == CONSORTIUM_TREND:
            effective_bias = "short" if result.bias == "long" else "long"
        if primary_bias is not None:
            if effective_bias == primary_bias:
                agree_count += 1
            else:
                disagree_count += 1

    # Agreement bonus
    agreement_bonus = 0.0
    if agree_count >= 4:
        agreement_bonus = 0.25   # Full agreement: 4/4
    elif agree_count >= 3:
        agreement_bonus = 0.15   # Strong agreement: 3/4

    # Disagreement penalty
    disagreement_penalty = 0.0
    # Volume disagreeing with signal = strong penalty (flow against us)
    vol_result = consortium_results.get(CONSORTIUM_VOLUME)
    if vol_result is not None and vol_result.bias is not None and primary_bias is not None:
        if vol_result.bias != primary_bias:
            disagreement_penalty += 0.20

    # General disagreement
    if disagree_count >= 2:
        disagreement_penalty += 0.15
    elif disagree_count >= 1:
        disagreement_penalty += 0.05

    # ── Step 5: Final confidence ─────────────────────────────
    base_confidence = abs(raw_score)
    confidence = base_confidence * (1.0 + agreement_bonus) * (1.0 - disagreement_penalty)
    confidence = max(0.0, min(1.0, confidence))

    return MasterSignal(
        bias=primary_bias,
        score=round(raw_score, 6),
        confidence=round(confidence, 6),
        agreement_count=agree_count,
        disagreement_count=disagree_count,
        consortium_scores=consortium_scores,
        agreement_bonus=round(agreement_bonus, 4),
        disagreement_penalty=round(disagreement_penalty, 4),
    )
