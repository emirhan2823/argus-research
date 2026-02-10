from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from argus_py.data.market_state import Bar

from .data_sources import RegimeFeatureSet, RegimeFeatureSource


class MarketRegime(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    HIGH_VOL_CHOP = "HIGH_VOL_CHOP"
    LOW_VOL_CALM = "LOW_VOL_CALM"


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: MarketRegime
    confidence: float
    features: RegimeFeatureSet
    reason: str
    bar_ts: Optional[float]


class MarketRegimeClassifier:
    """Production classifier for Year-2 market-state routing."""

    def __init__(
        self,
        feature_source: Optional[RegimeFeatureSource] = None,
        adx_trend_min: float = 25.0,
        high_vol_threshold: float = 0.07,
        low_vol_threshold: float = 0.025,
        slope_bps_threshold: float = 4.0,
    ) -> None:
        self.feature_source = feature_source or RegimeFeatureSource()
        self.adx_trend_min = float(adx_trend_min)
        self.high_vol_threshold = float(high_vol_threshold)
        self.low_vol_threshold = float(low_vol_threshold)
        self.slope_bps_threshold = float(slope_bps_threshold)

    def classify(self, bars: Sequence[Bar]) -> RegimeSnapshot:
        if len(bars) < 30:
            raise ValueError("at least 30 bars required")

        features = self.feature_source.from_bars(bars)
        bar_ts = float(bars[-1].timestamp)

        is_trend = features.adx >= self.adx_trend_min and abs(features.slope_bps) >= self.slope_bps_threshold
        is_high_vol = features.realized_vol >= self.high_vol_threshold or features.atr_ratio >= 0.018
        is_low_vol = features.realized_vol <= self.low_vol_threshold and features.bb_width <= 0.08

        if is_high_vol:
            conf = min(1.0, 0.45 + (features.realized_vol / max(self.high_vol_threshold, 1e-6)))
            return RegimeSnapshot(
                regime=MarketRegime.HIGH_VOL_CHOP,
                confidence=conf,
                features=features,
                reason=(
                    f"high volatility: realized_vol={features.realized_vol:.4f}, "
                    f"atr_ratio={features.atr_ratio:.4f}"
                ),
                bar_ts=bar_ts,
            )

        if is_trend and features.slope_bps > 0:
            conf = self._trend_confidence(features)
            return RegimeSnapshot(
                regime=MarketRegime.BULL_TREND,
                confidence=conf,
                features=features,
                reason=(
                    f"ADX {features.adx:.1f} >= {self.adx_trend_min:.1f}, "
                    f"slope_bps {features.slope_bps:.1f} > 0"
                ),
                bar_ts=bar_ts,
            )

        if is_trend and features.slope_bps < 0:
            conf = self._trend_confidence(features)
            return RegimeSnapshot(
                regime=MarketRegime.BEAR_TREND,
                confidence=conf,
                features=features,
                reason=(
                    f"ADX {features.adx:.1f} >= {self.adx_trend_min:.1f}, "
                    f"slope_bps {features.slope_bps:.1f} < 0"
                ),
                bar_ts=bar_ts,
            )

        conf = 0.65 if is_low_vol else 0.52
        return RegimeSnapshot(
            regime=MarketRegime.LOW_VOL_CALM,
            confidence=min(1.0, conf + max(0.0, (20.0 - features.adx) / 100.0)),
            features=features,
            reason=(
                f"calm market: realized_vol={features.realized_vol:.4f}, "
                f"bb_width={features.bb_width:.4f}, adx={features.adx:.1f}"
            ),
            bar_ts=bar_ts,
        )

    def _trend_confidence(self, features: RegimeFeatureSet) -> float:
        adx_term = max(0.0, features.adx - self.adx_trend_min) / 25.0
        slope_term = min(1.0, abs(features.slope_bps) / 30.0)
        conf = 0.55 + (0.3 * adx_term) + (0.25 * slope_term)
        return float(min(1.0, conf))
