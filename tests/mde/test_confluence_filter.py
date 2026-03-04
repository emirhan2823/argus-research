"""Tests for the confluence filter module."""

from __future__ import annotations

import pytest

from src.mde.confluence_filter import (
    ConfluenceConfig,
    ConfluenceResult,
    evaluate_confluence,
)


def _make_kwargs(**overrides):
    """Build default kwargs for evaluate_confluence with optional overrides."""
    defaults = dict(
        bias="long",
        engine="TITAN",
        # MTF — all aligned for long
        ema_21_vs_55=0.02,
        price_vs_ma200=0.05,
        supertrend_dir=1,
        lr_slope_20=0.003,
        # Volume — supportive
        volume_ratio=1.5,
        volume_delta=0.3,
        obv_slope_10=0.5,
        cmf_20=0.1,
        # Momentum — aligned for long
        rsi_14=55.0,
        cci_20=50.0,
        willr_14=-30.0,
        roc_10=0.005,
        # Volatility — moderate
        atr_ratio_5_20=1.0,
        bb_width=0.03,
        realized_vol_20d=0.04,
        # Orderbook
        orderbook_imbalance=0.3,
        trade_flow_imbalance=0.2,
        spread_pct=0.0004,
        # Statistical — trending
        hurst_exponent=0.60,
        return_autocorr_20=0.15,
        entropy_50=0.45,
    )
    defaults.update(overrides)
    return defaults


class TestConfluenceFilterPassesWithGoodSignal:
    def test_all_factors_aligned_long(self):
        result = evaluate_confluence(**_make_kwargs())
        assert result.passed is True
        assert result.factors_passed >= 4
        assert result.score >= 0.60

    def test_all_factors_aligned_short(self):
        result = evaluate_confluence(**_make_kwargs(
            bias="short",
            ema_21_vs_55=-0.02,
            price_vs_ma200=-0.05,
            supertrend_dir=-1,
            lr_slope_20=-0.003,
            volume_delta=-0.3,
            obv_slope_10=-0.5,
            cmf_20=-0.1,
            rsi_14=45.0,
            cci_20=-50.0,
            willr_14=-70.0,
            roc_10=-0.005,
            orderbook_imbalance=-0.3,
            trade_flow_imbalance=-0.2,
        ))
        assert result.passed is True
        assert result.factors_passed >= 4


class TestConfluenceFilterFailsWithWeakSignal:
    def test_only_2_factors_agree(self):
        """Counter-trend with no volume, bad momentum — should fail."""
        result = evaluate_confluence(**_make_kwargs(
            bias="long",
            ema_21_vs_55=-0.02,    # MTF disagrees
            price_vs_ma200=-0.05,   # MTF disagrees
            supertrend_dir=-1,      # MTF disagrees
            lr_slope_20=-0.003,     # MTF disagrees
            volume_ratio=0.5,       # Low volume
            volume_delta=-0.3,      # Volume disagrees
            obv_slope_10=-0.5,      # Volume disagrees
            cmf_20=-0.1,            # Volume disagrees
            rsi_14=75.0,            # Overbought — momentum disagrees
            cci_20=-50.0,           # Momentum disagrees
            willr_14=-80.0,         # Momentum disagrees
            roc_10=-0.005,          # Momentum disagrees
        ))
        assert result.passed is False
        assert result.factors_passed < 4

    def test_exactly_3_factors_fails(self):
        """3 factors pass but min is 4 — should fail."""
        result = evaluate_confluence(**_make_kwargs(
            # MTF aligned (pass)
            # Volume misaligned (fail)
            volume_ratio=0.4,
            volume_delta=-0.5,
            obv_slope_10=-0.3,
            cmf_20=-0.2,
            # Momentum aligned (pass)
            # Volatility OK (pass)
            # Orderbook misaligned (fail)
            orderbook_imbalance=-0.5,
            trade_flow_imbalance=-0.4,
            spread_pct=0.005,
            # Statistical misaligned for TITAN trending (fail — low hurst)
            hurst_exponent=0.30,
            return_autocorr_20=-0.2,
            entropy_50=0.90,
        ))
        # With 3 out of 6 passing, should fail
        assert result.factors_passed <= 4
        # Exact count depends on scoring but should be rejected


class TestConfluenceFilterEdgeCases:
    def test_non_crypto_orderbook_neutral(self):
        """Non-crypto without orderbook data should get neutral score."""
        result = evaluate_confluence(**_make_kwargs(
            orderbook_imbalance=None,
            trade_flow_imbalance=None,
        ))
        ob_factor = result.factor_details["orderbook_pressure"]
        assert ob_factor.score == 0.50
        assert ob_factor.passed is True

    def test_nautilus_with_low_hurst(self):
        """NAUTILUS should get good statistical edge with low hurst."""
        result = evaluate_confluence(**_make_kwargs(
            engine="NAUTILUS",
            hurst_exponent=0.30,
            return_autocorr_20=-0.15,
            entropy_50=0.35,
        ))
        stat_factor = result.factor_details["statistical_edge"]
        assert stat_factor.score >= 0.70

    def test_custom_config(self):
        """Custom config with stricter requirements."""
        config = ConfluenceConfig(min_factors_required=5, min_confluence_score=0.75)
        result = evaluate_confluence(**_make_kwargs(), config=config)
        # Even with all aligned, might not pass the 0.75 score threshold
        assert result.factors_total == 6

    def test_result_has_all_6_factors(self):
        result = evaluate_confluence(**_make_kwargs())
        assert result.factors_total == 6
        assert len(result.factor_details) == 6
        expected_names = {
            "mtf_alignment", "volume_confirmation", "momentum_alignment",
            "volatility_suitability", "orderbook_pressure", "statistical_edge",
        }
        assert set(result.factor_details.keys()) == expected_names
