from __future__ import annotations

from datetime import datetime, timezone

from src.core.types import FeatureVector, RegimeState


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_feature_vector(**overrides) -> FeatureVector:
    base = dict(
        timestamp=NOW,
        symbol="BTCUSDT",
        asset_class="crypto",
        atr_14=200.0,
        atr_14_pct=0.01,
        atr_ratio_5_20=1.1,
        atr_pctl=0.5,
        realized_vol_20d=0.25,
        parkinson_vol=0.2,
        bb_width=0.03,
        adx_14=30.0,
        price_vs_ma200=0.02,
        ema_21_vs_55=0.01,
        lr_slope_20=0.001,
        supertrend_dir=1,
        aroon_osc=35.0,
        rsi_14=55.0,
        bb_pct_b=0.6,
        roc_10=0.02,
        willr_14=-40.0,
        cci_20=50.0,
        volume_ratio=1.3,
        obv_slope_10=0.2,
        vwap_dev_pct=0.002,
        cmf_20=0.1,
        volume_delta=0.2,
        spread_pct=0.001,
        orderbook_imbalance=0.1,
        trade_flow_imbalance=0.05,
        depth_ratio=1.0,
        large_trade_ratio=0.12,
        funding_rate=0.0001,
        funding_pctile_30d=50.0,
        oi_change_4h_pct=0.02,
        oi_change_24h_pct=0.03,
        liquidation_est=0.1,
        long_short_ratio=1.05,
        basis_pct=0.001,
        btc_dominance_delta_24h=0.1,
        btc_eth_corr_30d=0.8,
        total_mcap_momentum=0.02,
        stablecoin_flow=500000.0,
        return_autocorr_20=0.1,
        hurst_exponent=0.5,
        entropy_50=2.0,
        frac_diff_price=123.0,
        hermes_sentiment_score=None,
        hermes_sentiment_confidence=None,
        hermes_urgency=None,
        chronos_forecast_1h=None,
        chronos_confidence_width=None,
        lgbm_direction=None,
        lgbm_confidence=None,
        meta_label_score=None,
        regime_prob_trending=None,
        regime_prob_ranging=None,
        regime_prob_volatile=None,
    )
    base.update(overrides)
    return FeatureVector(**base)


def make_regime_state(regime: str) -> RegimeState:
    return RegimeState(
        regime=regime,
        confidence=0.7,
        stability=0.6,
        direction=1,
        pending_transition=None,
        candles_in_regime=12,
        rule_regime=regime,
        ml_regime=regime,
        timestamp=NOW,
    )
