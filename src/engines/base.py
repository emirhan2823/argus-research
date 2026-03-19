"""Base engine protocol for ARGUS v2.0 engines."""

from __future__ import annotations

from typing import Optional, Protocol

from src.core.types import EngineSignal, FeatureVector, RegimeState


class AbstractEngine(Protocol):
    """Protocol every engine implementation must satisfy."""

    def generate_signal(
        self,
        *,
        regime: RegimeState,
        features: FeatureVector,
    ) -> Optional[EngineSignal]:
        ...
