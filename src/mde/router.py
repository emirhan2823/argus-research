"""Regime-to-engine router with PHOENIX fallback and HERMES override support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol

from src.core.constants import (
    ENGINE_HERMES,
    ENGINE_PHOENIX,
    REGIME_CRISIS,
    REGIME_TO_ENGINE,
    REGIME_TO_SECONDARY_ENGINES,
)
from src.core.types import EngineSignal, FeatureVector, RegimeState


class EngineProtocol(Protocol):
    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        ...


@dataclass
class RegimeRouter:
    engines: Mapping[str, EngineProtocol]

    def route(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
        allow_crisis_override: bool = False,
    ) -> Optional[EngineSignal]:
        if regime.regime == REGIME_CRISIS and not allow_crisis_override:
            return None

        # Run primary engine
        lead_name = REGIME_TO_ENGINE.get(regime.regime)
        lead_signal = self._run_engine(lead_name, regime, features) if lead_name else None

        # Run secondary engines (e.g., Hydra in RANGING)
        secondary_names = REGIME_TO_SECONDARY_ENGINES.get(regime.regime, [])
        secondary_signals = []
        for sec_name in secondary_names:
            sig = self._run_engine(sec_name, regime, features)
            if sig is not None:
                secondary_signals.append(sig)

        # Pick the best signal from all candidates
        all_candidates = [s for s in [lead_signal] + secondary_signals if s is not None]
        if all_candidates:
            best = max(all_candidates, key=lambda s: s.confidence)
            return self._apply_hermes_override(regime, features, best)

        # Fallback to PHOENIX when no engine has a signal.
        fallback_signal = self._run_engine(ENGINE_PHOENIX, regime, features)
        if fallback_signal is None:
            return None
        return self._apply_hermes_override(regime, features, fallback_signal)

    def _run_engine(
        self,
        engine_name: Optional[str],
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        if engine_name is None:
            return None
        engine = self.engines.get(engine_name)
        if engine is None:
            return None
        return engine.generate_signal(regime=regime, features=features)

    def _apply_hermes_override(
        self,
        regime: RegimeState,
        features: FeatureVector,
        base_signal: EngineSignal,
    ) -> EngineSignal:
        hermes = self.engines.get(ENGINE_HERMES)
        if hermes is None:
            return base_signal

        hermes_signal = hermes.generate_signal(regime=regime, features=features)
        if hermes_signal is None:
            return base_signal

        # HERMES veto/boost policy:
        # - If opposite side and confidence is materially higher, override base.
        # - Otherwise keep base and boost confidence slightly.
        if hermes_signal.bias != base_signal.bias and hermes_signal.confidence >= base_signal.confidence + 0.15:
            return hermes_signal

        boosted_conf = min(1.0, base_signal.confidence + 0.05)
        return base_signal.model_copy(update={"confidence": boosted_conf})
