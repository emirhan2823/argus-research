"""ARGUS v2.0 — Feature builder: orchestrates all feature modules into FeatureVector.

NaN Policy enforcement:
- Tier 1 NaN (core 17 technical features) -> HALT pipeline, use last valid snapshot
- Tier 2 NaN (derived features: volume, microstructure, statistical) -> Set to None, reduce sentinel score by 0.1
- Tier 3 NaN (crypto-native for non-crypto, ML outputs, sentiment) -> Set to None, no penalty
- If >5 Tier 1 NaN -> sentinel_score = 0.0 -> HALT all trading
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from src.core.constants import AC_CRYPTO, TIER1_NAN_HALT_THRESHOLD
from src.core.types import FeatureVector
from src.data.features.cross_asset import compute_cross_asset_features
from src.data.features.crypto_native import compute_crypto_native_features
from src.data.features.microstructure import compute_microstructure_features
from src.data.features.ml_features import compute_ml_features
from src.data.features.sentiment import compute_sentiment_features
from src.data.features.statistical import compute_statistical_features
from src.data.features.technical import compute_technical_features
from src.data.features.volume import compute_volume_features

logger = logging.getLogger(__name__)

# Tier 1 features: core 17 technical (Volatility 6 + Trend 6 + Momentum 5)
TIER1_FEATURES = frozenset({
    "atr_14", "atr_14_pct", "atr_ratio_5_20", "realized_vol_20d",
    "parkinson_vol", "bb_width",
    "adx_14", "price_vs_ma200", "ema_21_vs_55", "lr_slope_20",
    "supertrend_dir", "aroon_osc",
    "rsi_14", "bb_pct_b", "roc_10", "willr_14", "cci_20",
})

# Tier 2 features: volume, microstructure (spread), statistical
TIER2_FEATURES = frozenset({
    "volume_ratio", "obv_slope_10", "vwap_dev_pct", "cmf_20", "volume_delta",
    "spread_pct",
    "return_autocorr_20", "hurst_exponent", "entropy_50", "frac_diff_price",
})


@dataclass(frozen=True)
class FeatureBuildResult:
    """Result of feature building including NaN audit."""

    feature_vector: Optional[FeatureVector]
    tier1_nan_count: int
    tier2_nan_count: int
    tier3_nan_count: int
    sentinel_penalty: float  # Additional penalty from NaN
    halted: bool  # True if tier1 NaN > threshold
    nan_fields: tuple[str, ...]  # Names of fields that were NaN


class FeatureBuilder:
    """Orchestrates all feature modules and enforces NaN policy."""

    def build(
        self,
        df: pd.DataFrame,
        symbol: str,
        asset_class: str,
        timestamp: datetime,
        # Microstructure inputs
        spread_pct: float = 0.0,
        orderbook_imbalance: Optional[float] = None,
        trade_flow_imbalance: Optional[float] = None,
        depth_ratio: Optional[float] = None,
        large_trade_ratio: Optional[float] = None,
        # Crypto-native inputs
        funding_rate: Optional[float] = None,
        funding_pctile_30d: Optional[float] = None,
        oi_change_4h_pct: Optional[float] = None,
        oi_change_24h_pct: Optional[float] = None,
        liquidation_est: Optional[float] = None,
        long_short_ratio: Optional[float] = None,
        basis_pct: Optional[float] = None,
        # Cross-asset inputs
        btc_dominance_delta_24h: Optional[float] = None,
        btc_eth_corr_30d: Optional[float] = None,
        total_mcap_momentum: Optional[float] = None,
        stablecoin_flow: Optional[float] = None,
        # Sentiment inputs (from HERMES)
        hermes_sentiment_score: Optional[float] = None,
        hermes_sentiment_confidence: Optional[float] = None,
        hermes_urgency: Optional[str] = None,
        # ML inputs
        chronos_forecast_1h: Optional[float] = None,
        chronos_confidence_width: Optional[float] = None,
        lgbm_direction: Optional[int] = None,
        lgbm_confidence: Optional[float] = None,
        meta_label_score: Optional[float] = None,
        regime_prob_trending: Optional[float] = None,
        regime_prob_ranging: Optional[float] = None,
        regime_prob_volatile: Optional[float] = None,
    ) -> FeatureBuildResult:
        """Build a complete FeatureVector from OHLCV data and supplementary inputs.

        Args:
            df: OHLCV DataFrame (columns: open, high, low, close, volume).
            symbol: Trading symbol.
            asset_class: Asset class string.
            timestamp: Timestamp for this feature snapshot.
            ... supplementary inputs for each feature module.

        Returns:
            FeatureBuildResult with the vector (or None if halted) and NaN audit.
        """
        all_features: dict[str, Any] = {}

        # 1. Technical features (17)
        tech = compute_technical_features(df)
        all_features.update(tech)

        # 2. Volume features (5)
        vol = compute_volume_features(df)
        all_features.update(vol)

        # 3. Microstructure features (5)
        micro = compute_microstructure_features(
            spread_pct=spread_pct,
            orderbook_imbalance=orderbook_imbalance,
            trade_flow_imbalance=trade_flow_imbalance,
            depth_ratio=depth_ratio,
            large_trade_ratio=large_trade_ratio,
        )
        all_features.update(micro)

        # 4. Crypto-native features (7)
        crypto = compute_crypto_native_features(
            asset_class=asset_class,
            funding_rate=funding_rate,
            funding_pctile_30d=funding_pctile_30d,
            oi_change_4h_pct=oi_change_4h_pct,
            oi_change_24h_pct=oi_change_24h_pct,
            liquidation_est=liquidation_est,
            long_short_ratio=long_short_ratio,
            basis_pct=basis_pct,
        )
        all_features.update(crypto)

        # 5. Cross-asset features (4)
        cross = compute_cross_asset_features(
            btc_dominance_delta_24h=btc_dominance_delta_24h,
            btc_eth_corr_30d=btc_eth_corr_30d,
            total_mcap_momentum=total_mcap_momentum,
            stablecoin_flow=stablecoin_flow,
        )
        all_features.update(cross)

        # 6. Statistical features (4)
        stat = compute_statistical_features(df)
        all_features.update(stat)

        # 7. Sentiment features (3)
        sent = compute_sentiment_features(
            hermes_sentiment_score=hermes_sentiment_score,
            hermes_sentiment_confidence=hermes_sentiment_confidence,
            hermes_urgency=hermes_urgency,
        )
        all_features.update(sent)

        # 8. ML features (8)
        ml = compute_ml_features(
            chronos_forecast_1h=chronos_forecast_1h,
            chronos_confidence_width=chronos_confidence_width,
            lgbm_direction=lgbm_direction,
            lgbm_confidence=lgbm_confidence,
            meta_label_score=meta_label_score,
            regime_prob_trending=regime_prob_trending,
            regime_prob_ranging=regime_prob_ranging,
            regime_prob_volatile=regime_prob_volatile,
        )
        all_features.update(ml)

        # ── NaN Policy Enforcement ─────────────────────────────────
        nan_fields: list[str] = []
        tier1_nan = 0
        tier2_nan = 0
        tier3_nan = 0

        for field_name, value in all_features.items():
            if value is None:
                if field_name in TIER1_FEATURES:
                    tier1_nan += 1
                    nan_fields.append(field_name)
                elif field_name in TIER2_FEATURES:
                    tier2_nan += 1
                    nan_fields.append(field_name)
                else:
                    tier3_nan += 1
                    # Tier 3: no penalty, None is acceptable

        # Sentinel penalty from NaN
        sentinel_penalty = tier2_nan * 0.1

        # Check halt condition
        halted = tier1_nan > TIER1_NAN_HALT_THRESHOLD

        if halted:
            logger.error(
                "HALT: %d Tier 1 NaN for %s %s (threshold=%d): %s",
                tier1_nan,
                asset_class,
                symbol,
                TIER1_NAN_HALT_THRESHOLD,
                nan_fields,
            )
            return FeatureBuildResult(
                feature_vector=None,
                tier1_nan_count=tier1_nan,
                tier2_nan_count=tier2_nan,
                tier3_nan_count=tier3_nan,
                sentinel_penalty=1.0,  # Full penalty
                halted=True,
                nan_fields=tuple(nan_fields),
            )

        # For Tier 1 NaN <= threshold: replace with 0.0 default (safe fallback)
        # This allows the pipeline to continue with degraded quality
        for field_name in TIER1_FEATURES:
            if all_features.get(field_name) is None:
                if field_name == "supertrend_dir":
                    all_features[field_name] = 1  # Default bullish
                else:
                    all_features[field_name] = 0.0

        # For Tier 2 NaN: replace with 0.0 default
        for field_name in TIER2_FEATURES:
            if all_features.get(field_name) is None:
                all_features[field_name] = 0.0

        # Build the FeatureVector
        fv = FeatureVector(
            timestamp=timestamp,
            symbol=symbol,
            asset_class=asset_class,
            **{k: v for k, v in all_features.items()},
        )

        return FeatureBuildResult(
            feature_vector=fv,
            tier1_nan_count=tier1_nan,
            tier2_nan_count=tier2_nan,
            tier3_nan_count=tier3_nan,
            sentinel_penalty=sentinel_penalty,
            halted=False,
            nan_fields=tuple(nan_fields),
        )
