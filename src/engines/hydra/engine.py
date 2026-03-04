"""HYDRA engine: high-frequency scalping for RANGING/low-vol regimes.

Hydra is the cash-flow generator. It scalps small, frequent profits using
Bollinger Band mean reversion + RSI oversold/overbought + orderbook
imbalance + volume delta confirmation. Active only when ADX is low
(no strong trend) — the "calm waters" where wicks snap back.

Key design:
  - Limit orders only (maker rebates, less slippage)
  - Tight stops (1.5x ATR or 0.3% fixed)
  - Quick targets (band midpoint or +0.4% fixed)
  - High frequency: 5-15 signals/day per symbol in ranging markets
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import ENGINE_HYDRA, REGIME_RANGING
from src.core.types import EngineSignal, FeatureVector, RegimeState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class HydraEngine:
    """Scalp engine active in RANGING regime (low ADX, calm markets)."""

    # --- From config/engines.yaml hydra section ---
    min_confidence: float = 0.55
    max_concurrent: int = 5
    adx_max: float = 25.0
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    bb_std: float = 2.0
    bb_entry_long: float = 0.20
    bb_entry_short: float = 0.80
    obi_threshold: float = 0.15
    volume_delta_periods: int = 3
    min_volume_ratio: float = 0.8
    sl_atr_mult: float = 1.5
    sl_fixed_pct: float = 0.003
    tp_fixed_pct: float = 0.006

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        """Generate a scalp signal if conditions are met."""
        # ── Gate 1: Regime check ──
        if regime.regime not in (REGIME_RANGING,):
            return None

        # ── Gate 2: ADX must be low (no trend) ──
        if features.adx_14 > self.adx_max:
            return None

        # Try both long and short scalp setups
        long_sig = self._long_scalp(features)
        short_sig = self._short_scalp(features)

        candidates = [s for s in (long_sig, short_sig) if s is not None]
        if not candidates:
            return None

        best = max(candidates, key=lambda s: s.confidence)
        if best.confidence < self.min_confidence:
            return None
        return best

    def _long_scalp(self, features: FeatureVector) -> Optional[EngineSignal]:
        """Long scalp: price near lower BB with RSI/volume confirmation."""
        # Price must be near lower Bollinger Band (primary trigger)
        if features.bb_pct_b > self.bb_entry_long:
            return None

        # Build confidence score — BB position is primary, RSI/volume are bonuses
        conf = 0.48
        # Deeper into lower band = more confident
        conf += (self.bb_entry_long - features.bb_pct_b) * 2.0
        # RSI bonus (not required, but adds confidence)
        if features.rsi_14 <= self.rsi_oversold:
            conf += (self.rsi_oversold - features.rsi_14) / 80.0
        # Volume bonus
        if features.volume_ratio >= self.min_volume_ratio:
            conf += 0.05
        # Orderbook imbalance bonus (if available)
        if features.orderbook_imbalance is not None:
            if features.orderbook_imbalance > self.obi_threshold:
                conf += features.orderbook_imbalance * 0.3
            else:
                # Negative OBI = headwind for longs
                conf -= 0.05
        # Volume delta bonus
        if features.volume_delta > 0:
            conf += min(features.volume_delta * 0.1, 0.10)

        conf = _clamp(conf, 0.0, 1.0)
        stop = self._stop_distance(features)

        return EngineSignal(
            engine=ENGINE_HYDRA,
            sub_strategy="scalp_long",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="long",
            confidence=conf,
            stop_distance=stop,
            expected_return=max(stop * 2.0, self.tp_fixed_pct),
            atr=features.atr_14,
        )

    def _short_scalp(self, features: FeatureVector) -> Optional[EngineSignal]:
        """Short scalp: price near upper BB with RSI/volume confirmation."""
        # Price must be near upper Bollinger Band (primary trigger)
        if features.bb_pct_b < self.bb_entry_short:
            return None

        # Build confidence score — BB position is primary, RSI/volume are bonuses
        conf = 0.48
        # Further into upper band = more confident
        conf += (features.bb_pct_b - self.bb_entry_short) * 2.0
        # RSI bonus (not required, adds confidence when overbought)
        if features.rsi_14 >= self.rsi_overbought:
            conf += (features.rsi_14 - self.rsi_overbought) / 80.0
        # Volume bonus
        if features.volume_ratio >= self.min_volume_ratio:
            conf += 0.05
        # Orderbook imbalance bonus (negative = selling pressure = good for shorts)
        if features.orderbook_imbalance is not None:
            if features.orderbook_imbalance < -self.obi_threshold:
                conf += abs(features.orderbook_imbalance) * 0.3
            else:
                conf -= 0.05
        # Volume delta bonus (negative = selling)
        if features.volume_delta < 0:
            conf += min(abs(features.volume_delta) * 0.1, 0.10)

        conf = _clamp(conf, 0.0, 1.0)
        stop = self._stop_distance(features)

        return EngineSignal(
            engine=ENGINE_HYDRA,
            sub_strategy="scalp_short",
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias="short",
            confidence=conf,
            stop_distance=stop,
            expected_return=max(stop * 2.0, self.tp_fixed_pct),
            atr=features.atr_14,
        )

    def _stop_distance(self, features: FeatureVector) -> float:
        """ATR-based stop, clamped to tight scalping range."""
        approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
        atr_stop = (features.atr_14 * self.sl_atr_mult) / approx_price
        # Use the tighter of ATR-based or fixed stop (scalping = tight stops)
        return _clamp(min(atr_stop, self.sl_fixed_pct * 2), 0.001, 0.01)
