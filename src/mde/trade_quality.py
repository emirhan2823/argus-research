"""Trade Quality Classifier — meta-scoring system.

Aggregates all filter outputs into a single A/B/C/D grade.
Acts as the final gatekeeper before MDE gates.

- Grade A/B: trade taken
- Grade C: only if confidence > 0.85
- Grade D: always rejected

Integration point: Step 6.9 (after confluence filter, before gates).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeQualityInput:
    """All filter scores aggregated for final classification."""

    signal_quality_score: float        # from signal_quality.py (0-1)
    precision_grade_score: float       # from precision_filter.py (0-1)
    confluence_score: float            # from confluence_filter.py (0-1)
    regime_alignment_score: float      # from regime_alignment.py (0-1)
    final_confidence: float            # adjusted confidence at this point
    reward_risk_ratio: float           # from signal


@dataclass(frozen=True)
class TradeQualityResult:
    """Result of the trade quality classification."""

    grade: str           # "A" | "B" | "C" | "D"
    composite_score: float  # 0.0-1.0
    passed: bool
    reason: str


# Grade thresholds
_GRADE_A = 0.80
_GRADE_B = 0.65
_GRADE_C = 0.50
# Below C → Grade D

# Confidence required for Grade C exception
_GRADE_C_MIN_CONFIDENCE = 0.85


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def classify_trade_quality(
    inp: TradeQualityInput, *, engine: str = "", crypto_fee_mode: bool = False,
) -> TradeQualityResult:
    """Classify trade into A/B/C/D based on weighted composite of all filter scores.

    Weights:
    - Confluence score: 0.30 (heaviest — multi-factor confirmation matters most)
    - Signal quality score: 0.20
    - Precision grade score: 0.15
    - Regime alignment score: 0.15
    - Final confidence: 0.10
    - Reward/risk ratio: 0.10 (normalized to 0-1 by dividing by 4.0)
    """
    rr_normalized = _clamp(inp.reward_risk_ratio / 4.0, 0.0, 1.0)

    composite = (
        inp.signal_quality_score * 0.20
        + inp.precision_grade_score * 0.15
        + inp.confluence_score * 0.30
        + inp.regime_alignment_score * 0.15
        + _clamp(inp.final_confidence, 0.0, 1.0) * 0.10
        + rr_normalized * 0.10
    )
    composite = _clamp(composite, 0.0, 1.0)

    # Assign grade
    if composite >= _GRADE_A:
        grade = "A"
    elif composite >= _GRADE_B:
        grade = "B"
    elif composite >= _GRADE_C:
        grade = "C"
    else:
        grade = "D"

    # Crypto fee mode: only A/B pass, C always rejected
    if crypto_fee_mode:
        if grade in ("A", "B"):
            passed = True
            reason = f"trade_quality_{grade} composite={composite:.3f} [crypto]"
        else:
            passed = False
            reason = f"trade_quality_{grade}_reject_crypto composite={composite:.3f}"
        return TradeQualityResult(
            grade=grade,
            composite_score=round(composite, 4),
            passed=passed,
            reason=reason,
        )

    # Pass logic
    if grade in ("A", "B"):
        passed = True
        reason = f"trade_quality_{grade} composite={composite:.3f}"
    elif grade == "C" and inp.final_confidence >= _GRADE_C_MIN_CONFIDENCE:
        passed = True
        reason = f"trade_quality_C_exception composite={composite:.3f} conf={inp.final_confidence:.3f}>=0.85"
    else:
        passed = False
        if grade == "C":
            reason = f"trade_quality_C_reject composite={composite:.3f} conf={inp.final_confidence:.3f}<0.85"
        else:
            reason = f"trade_quality_D_reject composite={composite:.3f}"

    return TradeQualityResult(
        grade=grade,
        composite_score=round(composite, 4),
        passed=passed,
        reason=reason,
    )
