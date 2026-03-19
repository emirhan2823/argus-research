"""Tests for trade quality classifier with crypto_fee_mode."""

from __future__ import annotations

import pytest

from src.mde.trade_quality import TradeQualityInput, classify_trade_quality


def _make_input(
    signal_quality: float = 0.70,
    precision: float = 0.70,
    confluence: float = 0.70,
    regime_align: float = 0.70,
    confidence: float = 0.70,
    rr: float = 2.5,
) -> TradeQualityInput:
    return TradeQualityInput(
        signal_quality_score=signal_quality,
        precision_grade_score=precision,
        confluence_score=confluence,
        regime_alignment_score=regime_align,
        final_confidence=confidence,
        reward_risk_ratio=rr,
    )


class TestTradeQualityCrypto:
    """Trade quality classifier with crypto_fee_mode flag."""

    def test_grade_a_passes_crypto(self):
        """Grade A trade passes in crypto fee mode."""
        inp = _make_input(
            signal_quality=0.90, precision=0.90, confluence=0.90,
            regime_align=0.90, confidence=0.90, rr=3.0,
        )
        result = classify_trade_quality(inp, crypto_fee_mode=True)
        assert result.grade == "A"
        assert result.passed is True
        assert "[crypto]" in result.reason

    def test_grade_b_passes_crypto(self):
        """Grade B trade passes in crypto fee mode."""
        inp = _make_input(
            signal_quality=0.70, precision=0.70, confluence=0.70,
            regime_align=0.70, confidence=0.70, rr=2.5,
        )
        result = classify_trade_quality(inp, crypto_fee_mode=True)
        assert result.grade == "B"
        assert result.passed is True
        assert "[crypto]" in result.reason

    def test_grade_c_rejected_crypto(self):
        """Grade C trade always rejected in crypto fee mode (even with high confidence)."""
        inp = _make_input(
            signal_quality=0.55, precision=0.55, confluence=0.55,
            regime_align=0.55, confidence=0.95,  # High confidence would normally allow C
            rr=2.0,
        )
        result = classify_trade_quality(inp, crypto_fee_mode=True)
        assert result.grade == "C"
        assert result.passed is False
        assert "reject_crypto" in result.reason

    def test_grade_c_passes_without_crypto(self):
        """Same Grade C trade passes without crypto mode (high confidence exception)."""
        inp = _make_input(
            signal_quality=0.55, precision=0.55, confluence=0.55,
            regime_align=0.55, confidence=0.95,
            rr=2.0,
        )
        result = classify_trade_quality(inp, crypto_fee_mode=False)
        assert result.grade == "C"
        assert result.passed is True
        assert "C_exception" in result.reason

    def test_grade_d_rejected_crypto(self):
        """Grade D trade rejected in crypto fee mode."""
        inp = _make_input(
            signal_quality=0.20, precision=0.20, confluence=0.20,
            regime_align=0.20, confidence=0.30, rr=0.5,
        )
        result = classify_trade_quality(inp, crypto_fee_mode=True)
        assert result.grade == "D"
        assert result.passed is False
        assert "reject_crypto" in result.reason
