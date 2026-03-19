"""Regime state machine with confirmation and hysteresis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.core.constants import REGIME_CRISIS
from src.core.types import RegimeState


@dataclass(frozen=True)
class TransitionConfig:
    trending_to_ranging: int = 3
    ranging_to_trending: int = 3
    to_volatile: int = 2
    to_crisis: int = 0
    crisis_to_volatile: int = 12
    min_candles_before_transition: int = 6
    crisis_exempt: bool = True


class RegimeStateMachine:
    """Finite state machine for regime transitions."""

    def __init__(
        self,
        *,
        initial_regime: str,
        config: Optional[TransitionConfig] = None,
    ) -> None:
        self.config = config or TransitionConfig()
        self.current_regime = initial_regime
        self.candles_in_regime = 0
        self._pending_target: Optional[str] = None
        self._pending_count: int = 0

    def step(
        self,
        *,
        candidate_regime: str,
        confidence: float,
        stability: float,
        direction: Optional[int],
        rule_regime: str,
        ml_regime: str,
        timestamp: datetime,
        hermes_override: Optional[str] = None,
    ) -> RegimeState:
        """Advance state machine by one candle and return current snapshot."""
        self.candles_in_regime += 1

        if candidate_regime == self.current_regime:
            self._pending_target = None
            self._pending_count = 0
        elif self._hysteresis_blocks(candidate_regime, hermes_override):
            # Ignore early transitions before stability window completes.
            self._pending_target = None
            self._pending_count = 0
        elif self._should_transition(candidate_regime, hermes_override):
            self.current_regime = candidate_regime
            self.candles_in_regime = 0
            self._pending_target = None
            self._pending_count = 0
        else:
            if self._pending_target == candidate_regime:
                self._pending_count += 1
            else:
                self._pending_target = candidate_regime
                self._pending_count = 1

            required = self._required_confirmation(candidate_regime)
            if self._pending_count >= required:
                self.current_regime = candidate_regime
                self.candles_in_regime = 0
                self._pending_target = None
                self._pending_count = 0

        return RegimeState(
            regime=self.current_regime,
            confidence=confidence,
            stability=stability,
            direction=direction,
            pending_transition=self._pending_target,
            candles_in_regime=self.candles_in_regime,
            rule_regime=rule_regime,
            ml_regime=ml_regime,
            hermes_override=hermes_override,
            timestamp=timestamp,
        )

    def _should_transition(self, candidate_regime: str, hermes_override: Optional[str]) -> bool:
        forced_crisis = hermes_override == REGIME_CRISIS and candidate_regime == REGIME_CRISIS
        if forced_crisis:
            return True

        if candidate_regime == REGIME_CRISIS and self.config.to_crisis == 0:
            return True

        return False

    def _hysteresis_blocks(self, candidate_regime: str, hermes_override: Optional[str]) -> bool:
        forced_crisis = hermes_override == REGIME_CRISIS and candidate_regime == REGIME_CRISIS
        if forced_crisis:
            return False
        crisis_exempt = self.config.crisis_exempt and candidate_regime == REGIME_CRISIS
        return self.candles_in_regime < self.config.min_candles_before_transition and not crisis_exempt

    def _required_confirmation(self, candidate_regime: str) -> int:
        if candidate_regime == REGIME_CRISIS:
            return max(self.config.to_crisis, 1)
        if candidate_regime == "VOLATILE":
            if self.current_regime == REGIME_CRISIS:
                return self.config.crisis_to_volatile
            return self.config.to_volatile
        if candidate_regime == "RANGING" and self.current_regime == "TRENDING":
            return self.config.trending_to_ranging
        if candidate_regime == "TRENDING" and self.current_regime == "RANGING":
            return self.config.ranging_to_trending
        return 3
