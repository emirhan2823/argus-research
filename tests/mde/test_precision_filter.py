"""Tests for Phase E — Precision Entry Filter.

Covers:
- E-01: assess_entry_precision() grading logic
- E-02: Grade threshold configuration
- E-03: Pipeline integration (precision filter wired at step 6.7)
- Factor scoring: OBI, spread, VWAP, volume, ATR
"""

from __future__ import annotations

from src.mde.precision_filter import (
    PrecisionConfig,
    PrecisionGrade,
    assess_entry_precision,
    _score_obi,
    _score_spread,
    _score_vwap,
    _score_volume,
    _score_atr,
    _assign_grade,
    _grade_passes,
    _confidence_adjustment,
)


# ============================================================
# Helper
# ============================================================

def _assess(
    direction: str = "long",
    current_price: float = 20000.0,
    obi: float | None = 0.50,
    spread_pct: float = 0.0005,
    median_spread_pct: float = 0.0005,
    vwap_dev_pct: float = -0.001,
    volume_ratio: float = 1.2,
    atr_pct: float = 0.01,
    config: PrecisionConfig | None = None,
) -> PrecisionGrade:
    return assess_entry_precision(
        direction=direction,
        current_price=current_price,
        obi=obi,
        spread_pct=spread_pct,
        median_spread_pct=median_spread_pct,
        vwap_dev_pct=vwap_dev_pct,
        volume_ratio=volume_ratio,
        atr_pct=atr_pct,
        config=config,
    )


# ============================================================
# Grade A: Excellent microstructure
# ============================================================


class TestGradeA:
    """Grade A: strong OBI, tight spread, favourable VWAP, high volume."""

    def test_grade_a_long(self) -> None:
        """Perfect long setup: strong buy OBI, tight spread, below VWAP, high volume."""
        result = _assess(
            direction="long",
            obi=0.70,
            spread_pct=0.0003,
            median_spread_pct=0.0005,
            vwap_dev_pct=-0.004,
            volume_ratio=2.0,
            atr_pct=0.01,
        )
        assert result.grade == "A"
        assert result.passed is True
        assert result.score >= 0.80
        assert result.confidence_adjustment > 0

    def test_grade_a_short(self) -> None:
        """Perfect short setup: strong sell OBI, tight spread, above VWAP."""
        result = _assess(
            direction="short",
            obi=-0.70,
            spread_pct=0.0003,
            median_spread_pct=0.0005,
            vwap_dev_pct=0.004,
            volume_ratio=2.0,
            atr_pct=0.01,
        )
        assert result.grade == "A"
        assert result.passed is True
        assert result.confidence_adjustment == 0.05


# ============================================================
# Grade B: Good microstructure
# ============================================================


class TestGradeB:
    """Grade B: decent OBI, reasonable spread, OK VWAP."""

    def test_grade_b_long(self) -> None:
        result = _assess(
            direction="long",
            obi=0.40,
            spread_pct=0.0005,
            median_spread_pct=0.0005,
            vwap_dev_pct=-0.002,
            volume_ratio=1.5,
            atr_pct=0.01,
        )
        assert result.grade == "B"
        assert result.passed is True
        assert result.confidence_adjustment == 0.02


# ============================================================
# Grade C: Marginal
# ============================================================


class TestGradeC:
    """Grade C: neutral OBI, normal spread."""

    def test_grade_c_neutral_obi(self) -> None:
        result = _assess(
            direction="long",
            obi=0.05,
            spread_pct=0.0007,
            median_spread_pct=0.0005,
            vwap_dev_pct=0.002,
            volume_ratio=0.8,
            atr_pct=0.01,
        )
        assert result.grade == "C"
        assert result.passed is True
        assert result.confidence_adjustment == 0.0


# ============================================================
# Grade D: Poor but passing
# ============================================================


class TestGradeD:
    """Grade D: adverse OBI or wide spread, still passes."""

    def test_grade_d_adverse_conditions(self) -> None:
        result = _assess(
            direction="long",
            obi=-0.10,
            spread_pct=0.0008,
            median_spread_pct=0.0005,
            vwap_dev_pct=0.004,
            volume_ratio=0.6,
            atr_pct=0.03,
        )
        assert result.grade == "D"
        assert result.passed is True
        assert result.confidence_adjustment < 0


# ============================================================
# Grade F: Rejected
# ============================================================


class TestGradeF:
    """Grade F: terrible microstructure, rejected."""

    def test_grade_f_terrible_conditions(self) -> None:
        result = _assess(
            direction="long",
            obi=-0.60,         # Strong sell pressure, wrong for long
            spread_pct=0.005,   # 10x median spread
            median_spread_pct=0.0005,
            vwap_dev_pct=0.01,  # Far above VWAP for a long
            volume_ratio=0.3,   # Dead market
            atr_pct=0.06,       # Extreme volatility
        )
        assert result.grade == "F"
        assert result.passed is False
        assert result.confidence_adjustment == -0.10
        assert "REJECTED" in result.reason

    def test_grade_f_blocks_entry(self) -> None:
        """Grade F should not pass the grade check."""
        result = _assess(
            direction="short",
            obi=0.70,            # Strong buy pressure, wrong for short
            spread_pct=0.003,
            median_spread_pct=0.0005,
            vwap_dev_pct=-0.01,  # Far below VWAP for a short
            volume_ratio=0.4,
            atr_pct=0.06,
        )
        assert result.passed is False


# ============================================================
# Factor scoring unit tests
# ============================================================


class TestOBIScoring:
    """OBI alignment scoring."""

    def test_strong_buy_for_long(self) -> None:
        assert _score_obi(0.70, "long") == 1.0

    def test_strong_sell_for_short(self) -> None:
        assert _score_obi(-0.70, "short") == 1.0

    def test_adverse_obi_long(self) -> None:
        assert _score_obi(-0.50, "long") == 0.10

    def test_adverse_obi_short(self) -> None:
        assert _score_obi(0.50, "short") == 0.10

    def test_none_obi(self) -> None:
        assert _score_obi(None, "long") == 0.40

    def test_moderate_buy_for_long(self) -> None:
        assert _score_obi(0.40, "long") == 0.70

    def test_neutral_obi(self) -> None:
        score = _score_obi(0.0, "long")
        assert score == 0.50


class TestSpreadScoring:
    """Spread tightness scoring."""

    def test_tight_spread(self) -> None:
        assert _score_spread(0.3) == 1.0

    def test_normal_spread(self) -> None:
        assert _score_spread(1.0) == 0.85

    def test_wide_spread(self) -> None:
        assert _score_spread(2.0) == 0.35

    def test_very_wide_spread(self) -> None:
        assert _score_spread(3.0) == 0.10


class TestVWAPScoring:
    """VWAP proximity scoring."""

    def test_below_vwap_long(self) -> None:
        """Below VWAP is good for longs."""
        assert _score_vwap(-0.005, "long") == 0.90

    def test_above_vwap_short(self) -> None:
        """Above VWAP is good for shorts."""
        assert _score_vwap(0.005, "short") == 0.90

    def test_at_vwap_long(self) -> None:
        score = _score_vwap(0.0, "long")
        assert 0.50 < score < 1.0

    def test_wrong_side_long(self) -> None:
        """Above VWAP for a long is less ideal."""
        score = _score_vwap(0.01, "long")
        assert score < 0.55


class TestVolumeScoring:
    """Volume support scoring."""

    def test_high_volume(self) -> None:
        assert _score_volume(2.5) == 1.0

    def test_average_volume(self) -> None:
        assert _score_volume(1.0) == 0.65

    def test_dead_market(self) -> None:
        assert _score_volume(0.3) == 0.15


class TestATRScoring:
    """ATR reasonableness scoring."""

    def test_sweet_spot(self) -> None:
        assert _score_atr(0.01) == 0.90

    def test_too_low(self) -> None:
        assert _score_atr(0.0005) == 0.20

    def test_too_high(self) -> None:
        assert _score_atr(0.08) == 0.20


# ============================================================
# Grade assignment and config
# ============================================================


class TestGradeAssignment:
    """Grade assignment from score."""

    def test_assign_grade_a(self) -> None:
        assert _assign_grade(0.85, PrecisionConfig()) == "A"

    def test_assign_grade_b(self) -> None:
        assert _assign_grade(0.70, PrecisionConfig()) == "B"

    def test_assign_grade_c(self) -> None:
        assert _assign_grade(0.55, PrecisionConfig()) == "C"

    def test_assign_grade_d(self) -> None:
        assert _assign_grade(0.40, PrecisionConfig()) == "D"

    def test_assign_grade_f(self) -> None:
        assert _assign_grade(0.20, PrecisionConfig()) == "F"

    def test_custom_thresholds(self) -> None:
        """Custom config shifts grade boundaries."""
        cfg = PrecisionConfig(
            grade_a_threshold=0.90,
            grade_b_threshold=0.75,
            grade_c_threshold=0.60,
            grade_d_threshold=0.45,
        )
        assert _assign_grade(0.85, cfg) == "B"  # Was A with default thresholds
        assert _assign_grade(0.50, cfg) == "D"  # Below C threshold (0.60) with custom config

    def test_grade_passes_a(self) -> None:
        assert _grade_passes("A", "D") is True

    def test_grade_passes_d(self) -> None:
        assert _grade_passes("D", "D") is True

    def test_grade_fails_f(self) -> None:
        assert _grade_passes("F", "D") is False


# ============================================================
# Confidence adjustment
# ============================================================


class TestConfidenceAdjustment:
    """Grade-based confidence adjustments."""

    def test_grade_a_boosts(self) -> None:
        assert _confidence_adjustment("A", PrecisionConfig()) == 0.05

    def test_grade_b_boosts(self) -> None:
        assert _confidence_adjustment("B", PrecisionConfig()) == 0.02

    def test_grade_c_neutral(self) -> None:
        assert _confidence_adjustment("C", PrecisionConfig()) == 0.0

    def test_grade_d_penalizes(self) -> None:
        assert _confidence_adjustment("D", PrecisionConfig()) == -0.05

    def test_grade_f_penalizes(self) -> None:
        assert _confidence_adjustment("F", PrecisionConfig()) == -0.10


# ============================================================
# Order type recommendation
# ============================================================


class TestOrderTypeRecommendation:
    """Recommended order type based on OBI and spread."""

    def test_limit_when_good_obi_tight_spread(self) -> None:
        result = _assess(
            obi=0.70,
            spread_pct=0.0003,
            median_spread_pct=0.0005,
        )
        assert result.recommended_order_type == "limit"

    def test_market_when_no_obi(self) -> None:
        result = _assess(
            obi=None,
            spread_pct=0.0005,
            median_spread_pct=0.0005,
        )
        assert result.recommended_order_type == "market"


# ============================================================
# Output structure
# ============================================================


class TestOutputStructure:
    """PrecisionGrade output contract."""

    def test_frozen_dataclass(self) -> None:
        result = _assess()
        assert isinstance(result, PrecisionGrade)
        # Verify frozen
        try:
            result.grade = "X"  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_all_fields_present(self) -> None:
        result = _assess()
        assert result.grade in ("A", "B", "C", "D", "F")
        assert 0.0 <= result.score <= 1.0
        assert result.spread_ratio > 0
        assert isinstance(result.reason, str)
        assert isinstance(result.passed, bool)
        assert isinstance(result.confidence_adjustment, float)
        assert result.recommended_entry > 0
        assert result.recommended_order_type in ("limit", "market")

    def test_reason_contains_grade(self) -> None:
        result = _assess()
        assert f"grade={result.grade}" in result.reason
