"""Tests for the trade quality classifier module."""

from __future__ import annotations

import pytest

from src.mde.trade_quality import TradeQualityInput, TradeQualityResult, classify_trade_quality


class TestTradeQualityGradeA:
    def test_excellent_trade(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=0.85,
            precision_grade_score=0.90,
            confluence_score=0.85,
            regime_alignment_score=0.90,
            final_confidence=0.80,
            reward_risk_ratio=3.0,
        ))
        assert result.grade == "A"
        assert result.passed is True
        assert result.composite_score >= 0.80


class TestTradeQualityGradeB:
    def test_good_trade(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=0.70,
            precision_grade_score=0.70,
            confluence_score=0.70,
            regime_alignment_score=0.65,
            final_confidence=0.70,
            reward_risk_ratio=2.5,
        ))
        assert result.grade == "B"
        assert result.passed is True


class TestTradeQualityGradeC:
    def test_mediocre_trade_high_confidence_passes(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=0.55,
            precision_grade_score=0.55,
            confluence_score=0.55,
            regime_alignment_score=0.50,
            final_confidence=0.90,
            reward_risk_ratio=2.0,
        ))
        assert result.grade == "C"
        assert result.passed is True  # confidence >= 0.85 exception

    def test_mediocre_trade_low_confidence_rejected(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=0.55,
            precision_grade_score=0.55,
            confluence_score=0.55,
            regime_alignment_score=0.50,
            final_confidence=0.70,
            reward_risk_ratio=2.0,
        ))
        assert result.grade == "C"
        assert result.passed is False


class TestTradeQualityGradeD:
    def test_poor_trade_always_rejected(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=0.30,
            precision_grade_score=0.35,
            confluence_score=0.40,
            regime_alignment_score=0.30,
            final_confidence=0.95,
            reward_risk_ratio=1.5,
        ))
        assert result.grade == "D"
        assert result.passed is False


class TestTradeQualityScoring:
    def test_composite_score_bounded(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=1.0,
            precision_grade_score=1.0,
            confluence_score=1.0,
            regime_alignment_score=1.0,
            final_confidence=1.0,
            reward_risk_ratio=10.0,
        ))
        assert 0.0 <= result.composite_score <= 1.0

    def test_composite_zero_inputs(self):
        result = classify_trade_quality(TradeQualityInput(
            signal_quality_score=0.0,
            precision_grade_score=0.0,
            confluence_score=0.0,
            regime_alignment_score=0.0,
            final_confidence=0.0,
            reward_risk_ratio=0.0,
        ))
        assert result.grade == "D"
        assert result.passed is False
        assert result.composite_score == 0.0

    def test_confluence_weight_is_highest(self):
        """Confluence has the heaviest weight (0.30), so changing it should have the largest effect."""
        base = TradeQualityInput(
            signal_quality_score=0.50,
            precision_grade_score=0.50,
            confluence_score=0.50,
            regime_alignment_score=0.50,
            final_confidence=0.50,
            reward_risk_ratio=2.0,
        )
        high_confluence = TradeQualityInput(
            signal_quality_score=0.50,
            precision_grade_score=0.50,
            confluence_score=0.90,
            regime_alignment_score=0.50,
            final_confidence=0.50,
            reward_risk_ratio=2.0,
        )
        high_precision = TradeQualityInput(
            signal_quality_score=0.50,
            precision_grade_score=0.90,
            confluence_score=0.50,
            regime_alignment_score=0.50,
            final_confidence=0.50,
            reward_risk_ratio=2.0,
        )
        r_base = classify_trade_quality(base)
        r_confluence = classify_trade_quality(high_confluence)
        r_precision = classify_trade_quality(high_precision)
        # Confluence change should have more impact than precision change
        confluence_delta = r_confluence.composite_score - r_base.composite_score
        precision_delta = r_precision.composite_score - r_base.composite_score
        assert confluence_delta > precision_delta
