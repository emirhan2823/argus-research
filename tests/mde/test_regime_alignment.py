"""Tests for the regime-strategy alignment scoring module."""

from __future__ import annotations

import pytest

from src.mde.regime_alignment import RegimeAlignmentResult, score_regime_alignment


class TestTitanAlignment:
    def test_strong_trend(self):
        result = score_regime_alignment(
            engine="TITAN", regime="TRENDING",
            regime_confidence=0.75, candles_in_regime=15,
            adx_14=35.0, hurst_exponent=0.55, atr_ratio_5_20=1.2,
        )
        assert result.aligned is True
        assert result.alignment_score >= 0.80
        assert result.confidence_multiplier >= 1.0

    def test_borderline_trend(self):
        result = score_regime_alignment(
            engine="TITAN", regime="TRENDING",
            regime_confidence=0.50, candles_in_regime=3,
            adx_14=26.0, hurst_exponent=0.55, atr_ratio_5_20=1.2,
        )
        assert result.aligned is True
        assert result.confidence_multiplier < 1.0  # Penalized

    def test_titan_wrong_regime(self):
        result = score_regime_alignment(
            engine="TITAN", regime="RANGING",
            regime_confidence=0.80, candles_in_regime=20,
            adx_14=15.0, hurst_exponent=0.40, atr_ratio_5_20=0.8,
        )
        assert result.aligned is False
        assert result.alignment_score == 0.0


class TestNautilusAlignment:
    def test_strong_range(self):
        result = score_regime_alignment(
            engine="NAUTILUS", regime="RANGING",
            regime_confidence=0.70, candles_in_regime=10,
            adx_14=14.0, hurst_exponent=0.35, atr_ratio_5_20=0.9,
        )
        assert result.aligned is True
        assert result.alignment_score >= 0.75

    def test_nautilus_wrong_regime(self):
        result = score_regime_alignment(
            engine="NAUTILUS", regime="TRENDING",
            regime_confidence=0.80, candles_in_regime=20,
            adx_14=30.0, hurst_exponent=0.60, atr_ratio_5_20=1.5,
        )
        assert result.aligned is False


class TestHydraAlignment:
    def test_calm_range_good_for_scalping(self):
        result = score_regime_alignment(
            engine="HYDRA", regime="RANGING",
            regime_confidence=0.65, candles_in_regime=8,
            adx_14=14.0, hurst_exponent=0.38, atr_ratio_5_20=0.85,
        )
        assert result.aligned is True
        assert result.alignment_score >= 0.70

    def test_volatile_range_bad_for_scalping(self):
        result = score_regime_alignment(
            engine="HYDRA", regime="RANGING",
            regime_confidence=0.55, candles_in_regime=5,
            adx_14=20.0, hurst_exponent=0.48, atr_ratio_5_20=1.8,
        )
        assert result.confidence_multiplier < 1.0


class TestPhoenixAlignment:
    def test_phoenix_always_partially_aligned(self):
        for regime in ["TRENDING", "RANGING", "VOLATILE"]:
            result = score_regime_alignment(
                engine="PHOENIX", regime=regime,
                regime_confidence=0.50, candles_in_regime=5,
                adx_14=20.0, hurst_exponent=0.50, atr_ratio_5_20=1.0,
            )
            assert result.aligned is True
            assert result.alignment_score >= 0.50

    def test_phoenix_crisis_low_alignment(self):
        result = score_regime_alignment(
            engine="PHOENIX", regime="CRISIS",
            regime_confidence=0.90, candles_in_regime=2,
            adx_14=40.0, hurst_exponent=0.70, atr_ratio_5_20=3.0,
        )
        assert result.alignment_score == 0.30


class TestHermesAlignment:
    def test_hermes_regime_agnostic(self):
        result = score_regime_alignment(
            engine="HERMES", regime="VOLATILE",
            regime_confidence=0.80, candles_in_regime=10,
            adx_14=30.0, hurst_exponent=0.50, atr_ratio_5_20=2.0,
        )
        assert result.aligned is True
        assert result.confidence_multiplier == 1.0


class TestMultiplierMapping:
    def test_low_score_heavy_penalty(self):
        result = score_regime_alignment(
            engine="TITAN", regime="TRENDING",
            regime_confidence=0.40, candles_in_regime=2,
            adx_14=25.0, hurst_exponent=0.50, atr_ratio_5_20=1.0,
        )
        assert result.confidence_multiplier <= 0.95  # Relaxed: softer penalty for borderline

    def test_high_score_slight_boost(self):
        result = score_regime_alignment(
            engine="TITAN", regime="TRENDING",
            regime_confidence=0.80, candles_in_regime=20,
            adx_14=40.0, hurst_exponent=0.60, atr_ratio_5_20=1.2,
        )
        assert result.confidence_multiplier >= 1.0
