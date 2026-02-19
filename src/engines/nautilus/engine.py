"""NAUTILUS engine: mean reversion for RANGING regime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.core.constants import AC_CRYPTO, ENGINE_NAUTILUS, REGIME_RANGING
from src.core.types import EngineSignal, FeatureVector, RegimeState
from src.engines.nautilus.micro_reversion import detect_micro_reversion
from src.engines.nautilus.range_mapper import RangeResult, identify_range


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class NautilusEngine:
    max_adx: float = 22.0
    min_confidence: float = 0.55

    # Candle history for range detection (symbol -> (highs, lows, closes))
    _candle_history: dict[str, tuple[list[float], list[float], list[float]]] = field(
        default_factory=dict, repr=False
    )

    # Cached range results (symbol -> RangeResult | None)
    _cached_ranges: dict[str, Optional[RangeResult]] = field(
        default_factory=dict, repr=False
    )

    def feed_candles(
        self,
        symbol: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> None:
        """Feed candle history for range detection. Call before generate_signal."""
        self._candle_history[symbol] = (highs, lows, closes)

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        if regime.regime != REGIME_RANGING:
            return None
        if features.adx_14 > self.max_adx:
            return None

        bb = self._bb_reversion_signal(features)
        funding = self._funding_reversion_signal(features)
        micro = self._micro_reversion_signal(features)

        candidates = [sig for sig in (bb, funding, micro) if sig is not None]
        if not candidates:
            return None

        best = max(candidates, key=lambda s: s.confidence)
        if best.confidence < self.min_confidence:
            return None
        return best

    def _micro_reversion_signal(self, features: FeatureVector) -> Optional[EngineSignal]:
        """Attempt micro-reversion signal using range detection."""
        history = self._candle_history.get(features.symbol)
        if history is None:
            return None

        highs, lows, closes = history
        atr = features.atr_14
        if atr <= 0:
            return None

        detected = identify_range(highs, lows, closes, atr)
        self._cached_ranges[features.symbol] = detected
        if detected is None:
            return None

        return detect_micro_reversion(
            features,
            range_high=detected.range_high,
            range_low=detected.range_low,
            range_midpoint=detected.midpoint,
        )

    def _bb_reversion_signal(self, features: FeatureVector) -> Optional[EngineSignal]:
        if features.bb_pct_b <= 0.05 and features.rsi_14 <= 30:
            bias = "long"
            stretch = 0.05 - features.bb_pct_b
        elif features.bb_pct_b >= 0.95 and features.rsi_14 >= 70:
            bias = "short"
            stretch = features.bb_pct_b - 0.95
        else:
            return None

        conf = _clamp(0.55 + stretch * 3.0 + abs(features.rsi_14 - 50.0) / 200.0, 0.0, 1.0)
        stop = _stop_distance(features, atr_mult=1.0)
        return EngineSignal(
            engine=ENGINE_NAUTILUS,
            sub_strategy="bb_reversion",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * 1.8,
            atr=features.atr_14,
        )

    def _funding_reversion_signal(self, features: FeatureVector) -> Optional[EngineSignal]:
        if features.asset_class != AC_CRYPTO:
            return None
        if features.funding_pctile_30d is None:
            return None

        if features.funding_pctile_30d >= 90:
            bias = "short"
            ext = (features.funding_pctile_30d - 90) / 10
        elif features.funding_pctile_30d <= 10:
            bias = "long"
            ext = (10 - features.funding_pctile_30d) / 10
        else:
            return None

        conf = _clamp(0.60 + ext * 0.2, 0.0, 1.0)
        stop = _stop_distance(features, atr_mult=3.0)
        return EngineSignal(
            engine=ENGINE_NAUTILUS,
            sub_strategy="funding_reversion",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=conf,
            stop_distance=stop,
            expected_return=stop * 1.6,
            atr=features.atr_14,
        )


def _stop_distance(features: FeatureVector, *, atr_mult: float) -> float:
    approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
    return _clamp((features.atr_14 * atr_mult) / approx_price, 0.001, 0.10)
