"""TITAN engine: trend-follow and breakout for TRENDING regime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import ENGINE_TITAN, REGIME_TRENDING
from src.core.types import EngineSignal, FeatureVector, RegimeState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class TitanEngine:
    """Trend engine active only in TRENDING regime."""

    min_adx: float = 25.0
    min_confidence: float = 0.55
    breakout_volume_spike: float = 1.5

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        if regime.regime != REGIME_TRENDING:
            return None
        if features.adx_14 < self.min_adx:
            return None

        trend = self._trend_follow_signal(features)
        breakout = self._breakout_signal(features)

        candidates = [sig for sig in (trend, breakout) if sig is not None]
        if not candidates:
            return None

        best = max(candidates, key=lambda s: s.confidence)
        if best.confidence < self.min_confidence:
            return None
        return best

    def _trend_follow_signal(self, features: FeatureVector) -> Optional[EngineSignal]:
        aligned_long = features.ema_21_vs_55 > 0 and features.price_vs_ma200 > 0
        aligned_short = features.ema_21_vs_55 < 0 and features.price_vs_ma200 < 0
        if not (aligned_long or aligned_short):
            return None

        bias = "long" if aligned_long else "short"
        conf = _clamp(0.45 + (features.adx_14 / 100.0) + abs(features.ema_21_vs_55) * 4.0, 0.0, 1.0)
        stop = _stop_distance(features, atr_mult=2.5)

        return EngineSignal(
            engine=ENGINE_TITAN,
            sub_strategy="trend_follow",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * 2.2,
            atr=features.atr_14,
        )

    def _breakout_signal(self, features: FeatureVector) -> Optional[EngineSignal]:
        # Donchian approximation using BB% and volume spike.
        if features.volume_ratio < self.breakout_volume_spike:
            return None

        if features.bb_pct_b >= 0.95:
            bias = "long"
            impulse = features.bb_pct_b - 0.95
        elif features.bb_pct_b <= 0.05:
            bias = "short"
            impulse = 0.05 - features.bb_pct_b
        else:
            return None

        conf = _clamp(0.55 + impulse * 4.0 + (features.volume_ratio - self.breakout_volume_spike) * 0.1, 0.0, 1.0)
        stop = _stop_distance(features, atr_mult=2.0)

        return EngineSignal(
            engine=ENGINE_TITAN,
            sub_strategy="breakout",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * 2.0,
            atr=features.atr_14,
        )


def _stop_distance(features: FeatureVector, *, atr_mult: float) -> float:
    approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
    return _clamp((features.atr_14 * atr_mult) / approx_price, 0.001, 0.10)
