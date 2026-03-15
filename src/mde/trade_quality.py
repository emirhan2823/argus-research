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


@dataclass(frozen=True)
class TradeQualityConfig:
    """Configurable thresholds and pass rules for trade quality grading."""

    grade_a_threshold: float = 0.80
    grade_b_threshold: float = 0.65
    grade_c_threshold: float = 0.50
    grade_c_min_confidence: float = 0.85
    allow_grade_c_in_crypto: bool = False


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def classify_trade_quality(
    inp: TradeQualityInput,
    *,
    engine: str = "",
    crypto_fee_mode: bool = False,
    config: TradeQualityConfig | None = None,
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
    cfg = config or TradeQualityConfig()
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
    if composite >= cfg.grade_a_threshold:
        grade = "A"
    elif composite >= cfg.grade_b_threshold:
        grade = "B"
    elif composite >= cfg.grade_c_threshold:
        grade = "C"
    else:
        grade = "D"

    # Crypto fee mode: A/B pass; C can be conditionally allowed by config.
    if crypto_fee_mode:
        if grade in ("A", "B"):
            passed = True
            reason = f"trade_quality_{grade} composite={composite:.3f} [crypto]"
        elif (
            grade == "C"
            and bool(cfg.allow_grade_c_in_crypto)
            and inp.final_confidence >= cfg.grade_c_min_confidence
        ):
            passed = True
            reason = (
                "trade_quality_C_exception_crypto "
                f"composite={composite:.3f} conf={inp.final_confidence:.3f}>={cfg.grade_c_min_confidence:.2f}"
            )
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
    elif grade == "C" and inp.final_confidence >= cfg.grade_c_min_confidence:
        passed = True
        reason = (
            f"trade_quality_C_exception composite={composite:.3f} "
            f"conf={inp.final_confidence:.3f}>={cfg.grade_c_min_confidence:.2f}"
        )
    else:
        passed = False
        if grade == "C":
            reason = (
                f"trade_quality_C_reject composite={composite:.3f} "
                f"conf={inp.final_confidence:.3f}<{cfg.grade_c_min_confidence:.2f}"
            )
        else:
            reason = f"trade_quality_D_reject composite={composite:.3f}"

    return TradeQualityResult(
        grade=grade,
        composite_score=round(composite, 4),
        passed=passed,
        reason=reason,
    )
