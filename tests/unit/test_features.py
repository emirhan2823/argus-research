from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.core.constants import AC_CRYPTO, AC_US_EQUITY
from src.data.features.builder import FeatureBuilder
from src.data.features.crypto_native import compute_crypto_native_features
from src.data.features.technical import compute_technical_features


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _ohlcv(rows: int = 260) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.6, rows))
    high = close + np.abs(rng.normal(0.5, 0.2, rows))
    low = close - np.abs(rng.normal(0.5, 0.2, rows))
    open_ = close + rng.normal(0, 0.15, rows)
    volume = rng.uniform(50_000, 200_000, rows)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


def test_technical_features_return_expected_17_fields() -> None:
    feats = compute_technical_features(_ohlcv(280))
    expected = {
        "atr_14",
        "atr_14_pct",
        "atr_ratio_5_20",
        "realized_vol_20d",
        "parkinson_vol",
        "bb_width",
        "adx_14",
        "price_vs_ma200",
        "ema_21_vs_55",
        "lr_slope_20",
        "supertrend_dir",
        "aroon_osc",
        "rsi_14",
        "bb_pct_b",
        "roc_10",
        "willr_14",
        "cci_20",
    }
    assert set(feats.keys()) == expected
    assert feats["atr_14"] is not None
    assert feats["rsi_14"] is not None


def test_crypto_native_features_are_none_for_non_crypto() -> None:
    feats = compute_crypto_native_features(
        asset_class=AC_US_EQUITY,
        funding_rate=0.001,
        funding_pctile_30d=95.0,
        oi_change_4h_pct=0.1,
    )
    assert all(value is None for value in feats.values())


def test_feature_builder_builds_feature_vector_crypto() -> None:
    builder = FeatureBuilder()
    result = builder.build(
        df=_ohlcv(320),
        symbol="BTCUSDT",
        asset_class=AC_CRYPTO,
        timestamp=NOW,
        spread_pct=0.001,
        funding_rate=0.0002,
        funding_pctile_30d=65.0,
    )
    assert result.halted is False
    assert result.feature_vector is not None
    assert result.feature_vector.symbol == "BTCUSDT"
    assert result.feature_vector.asset_class == AC_CRYPTO


def test_feature_builder_halts_when_tier1_nan_exceeds_threshold(monkeypatch) -> None:
    import src.data.features.builder as builder_module

    def tech_all_none(_df):
        return {
            "atr_14": None,
            "atr_14_pct": None,
            "atr_ratio_5_20": None,
            "realized_vol_20d": None,
            "parkinson_vol": None,
            "bb_width": None,
            "adx_14": None,
            "price_vs_ma200": None,
            "ema_21_vs_55": None,
            "lr_slope_20": None,
            "supertrend_dir": None,
            "aroon_osc": None,
            "rsi_14": None,
            "bb_pct_b": None,
            "roc_10": None,
            "willr_14": None,
            "cci_20": None,
        }

    monkeypatch.setattr(builder_module, "compute_technical_features", tech_all_none)
    monkeypatch.setattr(
        builder_module,
        "compute_volume_features",
        lambda _df: {
            "volume_ratio": 1.0,
            "obv_slope_10": 0.1,
            "vwap_dev_pct": 0.0,
            "cmf_20": 0.1,
            "volume_delta": 0.0,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_microstructure_features",
        lambda **_kwargs: {
            "spread_pct": 0.001,
            "orderbook_imbalance": None,
            "trade_flow_imbalance": None,
            "depth_ratio": None,
            "large_trade_ratio": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_crypto_native_features",
        lambda **_kwargs: {
            "funding_rate": None,
            "funding_pctile_30d": None,
            "oi_change_4h_pct": None,
            "oi_change_24h_pct": None,
            "liquidation_est": None,
            "long_short_ratio": None,
            "basis_pct": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_cross_asset_features",
        lambda **_kwargs: {
            "btc_dominance_delta_24h": None,
            "btc_eth_corr_30d": None,
            "total_mcap_momentum": None,
            "stablecoin_flow": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_statistical_features",
        lambda _df: {
            "return_autocorr_20": 0.0,
            "hurst_exponent": 0.5,
            "entropy_50": 1.0,
            "frac_diff_price": 100.0,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_sentiment_features",
        lambda **_kwargs: {
            "hermes_sentiment_score": None,
            "hermes_sentiment_confidence": None,
            "hermes_urgency": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_ml_features",
        lambda **_kwargs: {
            "chronos_forecast_1h": None,
            "chronos_confidence_width": None,
            "lgbm_direction": None,
            "lgbm_confidence": None,
            "meta_label_score": None,
            "regime_prob_trending": None,
            "regime_prob_ranging": None,
            "regime_prob_volatile": None,
        },
    )

    result = FeatureBuilder().build(
        df=_ohlcv(80),
        symbol="BTCUSDT",
        asset_class=AC_CRYPTO,
        timestamp=NOW,
    )

    assert result.halted is True
    assert result.feature_vector is None
    assert result.tier1_nan_count == 17
    assert result.sentinel_penalty == 1.0


def test_feature_builder_tier2_nan_adds_penalty_without_halt(monkeypatch) -> None:
    import src.data.features.builder as builder_module

    monkeypatch.setattr(
        builder_module,
        "compute_technical_features",
        lambda _df: {
            "atr_14": 1.0,
            "atr_14_pct": 0.01,
            "atr_ratio_5_20": 1.0,
            "realized_vol_20d": 0.2,
            "parkinson_vol": 0.2,
            "bb_width": 0.03,
            "adx_14": 20.0,
            "price_vs_ma200": 0.0,
            "ema_21_vs_55": 0.0,
            "lr_slope_20": 0.0,
            "supertrend_dir": 1,
            "aroon_osc": 10.0,
            "rsi_14": 50.0,
            "bb_pct_b": 0.5,
            "roc_10": 0.0,
            "willr_14": -50.0,
            "cci_20": 20.0,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_volume_features",
        lambda _df: {
            "volume_ratio": None,
            "obv_slope_10": 0.1,
            "vwap_dev_pct": None,
            "cmf_20": 0.1,
            "volume_delta": 0.1,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_microstructure_features",
        lambda **_kwargs: {
            "spread_pct": None,
            "orderbook_imbalance": None,
            "trade_flow_imbalance": None,
            "depth_ratio": None,
            "large_trade_ratio": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_crypto_native_features",
        lambda **_kwargs: {
            "funding_rate": None,
            "funding_pctile_30d": None,
            "oi_change_4h_pct": None,
            "oi_change_24h_pct": None,
            "liquidation_est": None,
            "long_short_ratio": None,
            "basis_pct": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_cross_asset_features",
        lambda **_kwargs: {
            "btc_dominance_delta_24h": None,
            "btc_eth_corr_30d": None,
            "total_mcap_momentum": None,
            "stablecoin_flow": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_statistical_features",
        lambda _df: {
            "return_autocorr_20": 0.1,
            "hurst_exponent": None,
            "entropy_50": 2.0,
            "frac_diff_price": 1.0,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_sentiment_features",
        lambda **_kwargs: {
            "hermes_sentiment_score": None,
            "hermes_sentiment_confidence": None,
            "hermes_urgency": None,
        },
    )
    monkeypatch.setattr(
        builder_module,
        "compute_ml_features",
        lambda **_kwargs: {
            "chronos_forecast_1h": None,
            "chronos_confidence_width": None,
            "lgbm_direction": None,
            "lgbm_confidence": None,
            "meta_label_score": None,
            "regime_prob_trending": None,
            "regime_prob_ranging": None,
            "regime_prob_volatile": None,
        },
    )

    result = FeatureBuilder().build(
        df=_ohlcv(80),
        symbol="AAPL",
        asset_class=AC_US_EQUITY,
        timestamp=NOW,
    )

    assert result.halted is False
    assert result.tier1_nan_count == 0
    assert result.tier2_nan_count == 4  # volume_ratio, vwap_dev_pct, spread_pct, hurst_exponent
    assert result.sentinel_penalty == 0.4
    assert result.feature_vector is not None
    assert result.feature_vector.spread_pct == 0.0  # Tier2 fallback
