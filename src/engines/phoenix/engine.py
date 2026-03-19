"""PHOENIX engine: carry/basis opportunities.

DEPRECATED — QUARANTINED as of 2026-03-15.
This engine is never instantiated in the pipeline. It exists only for
reference and potential future reactivation. Do not add new functionality.
See Docs/argus_refactor/phoenix_quarantine.md for full reference inventory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import AC_CRYPTO, ENGINE_PHOENIX, REGIME_CRISIS
from src.core.types import EngineSignal, FeatureVector, RegimeState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class PhoenixEngine:
    min_confidence: float = 0.60

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        if regime.regime == REGIME_CRISIS:
            return None

        funding = self._funding_harvest(features)
        basis = self._basis_trade(features)
        carry = self._non_crypto_carry(features)

        candidates = [sig for sig in (funding, basis, carry) if sig is not None]
        if not candidates:
            return None

        best = max(candidates, key=lambda s: s.confidence)
        if best.confidence < self.min_confidence:
            return None
        return best

    def _funding_harvest(self, features: FeatureVector) -> Optional[EngineSignal]:
        if features.asset_class != AC_CRYPTO or features.funding_pctile_30d is None:
            return None
        pct = features.funding_pctile_30d
        if pct >= 90:
            bias = "short"
            edge = (pct - 90) / 10
        elif pct <= 10:
            bias = "long"
            edge = (10 - pct) / 10
        else:
            return None
        conf = _clamp(0.60 + edge * 0.25, 0.0, 1.0)
        return self._build_signal(features, "funding_harvest", bias, conf, atr_mult=2.5)

    def _basis_trade(self, features: FeatureVector) -> Optional[EngineSignal]:
        if features.asset_class != AC_CRYPTO or features.basis_pct is None:
            return None
        if features.basis_pct >= 0.003:
            bias = "short"
            edge = (features.basis_pct - 0.003) / 0.003
        elif features.basis_pct <= -0.003:
            bias = "long"
            edge = (-0.003 - features.basis_pct) / 0.003
        else:
            return None
        conf = _clamp(0.62 + edge * 0.15, 0.0, 1.0)
        return self._build_signal(features, "basis_trade", bias, conf, atr_mult=3.0)

    def _non_crypto_carry(self, features: FeatureVector) -> Optional[EngineSignal]:
        if features.asset_class == AC_CRYPTO:
            return None
        # Carry-like proxy: strong one-sided flow with low spread and stable vol.
        if abs(features.volume_delta) < 0.25 or features.spread_pct > 0.005:
            return None
        bias = "long" if features.volume_delta > 0 else "short"
        conf = _clamp(0.60 + abs(features.volume_delta) * 0.3, 0.0, 1.0)
        return self._build_signal(features, "carry_proxy", bias, conf, atr_mult=2.0)

    def _build_signal(
        self,
        features: FeatureVector,
        sub_strategy: str,
        bias: str,
        confidence: float,
        *,
        atr_mult: float,
    ) -> EngineSignal:
        approx_price = max(features.atr_14 / max(features.atr_14_pct, 1e-6), 1.0)
        stop = _clamp((features.atr_14 * atr_mult) / approx_price, 0.001, 0.10)
        return EngineSignal(
            engine=ENGINE_PHOENIX,
            sub_strategy=sub_strategy,
            asset_class=features.asset_class,
            symbol=features.symbol,
            bias=bias,
            confidence=confidence,
            stop_distance=stop,
            expected_return=stop * 2.0,
            atr=features.atr_14,
        )
