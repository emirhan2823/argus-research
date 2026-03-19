from __future__ import annotations

from datetime import datetime, timezone

from src.core.constants import REGIME_CRISIS, REGIME_RANGING, REGIME_TRENDING, REGIME_VOLATILE
from src.regime.state_machine import RegimeStateMachine, TransitionConfig


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _step(
    sm: RegimeStateMachine,
    candidate: str,
    *,
    ts_offset: int = 0,
    hermes_override: str | None = None,
):
    return sm.step(
        candidate_regime=candidate,
        confidence=0.7,
        stability=0.6,
        direction=1,
        rule_regime=candidate,
        ml_regime=candidate,
        timestamp=NOW.replace(minute=min(59, ts_offset)),
        hermes_override=hermes_override,
    )


def test_state_machine_requires_confirmation_for_ranging_to_trending() -> None:
    sm = RegimeStateMachine(
        initial_regime=REGIME_RANGING,
        config=TransitionConfig(ranging_to_trending=3, min_candles_before_transition=0),
    )
    _step(sm, REGIME_TRENDING, ts_offset=1)
    assert sm.current_regime == REGIME_RANGING
    _step(sm, REGIME_TRENDING, ts_offset=2)
    assert sm.current_regime == REGIME_RANGING
    _step(sm, REGIME_TRENDING, ts_offset=3)
    assert sm.current_regime == REGIME_TRENDING


def test_state_machine_min_candles_hysteresis_blocks_early_flip() -> None:
    sm = RegimeStateMachine(
        initial_regime=REGIME_TRENDING,
        config=TransitionConfig(trending_to_ranging=1, min_candles_before_transition=6),
    )
    _step(sm, REGIME_RANGING, ts_offset=1)
    assert sm.current_regime == REGIME_TRENDING


def test_state_machine_hermes_forces_crisis_immediately() -> None:
    sm = RegimeStateMachine(
        initial_regime=REGIME_RANGING,
        config=TransitionConfig(min_candles_before_transition=999),
    )
    _step(sm, REGIME_CRISIS, ts_offset=1, hermes_override=REGIME_CRISIS)
    assert sm.current_regime == REGIME_CRISIS


def test_state_machine_crisis_to_volatile_needs_long_confirmation() -> None:
    sm = RegimeStateMachine(
        initial_regime=REGIME_CRISIS,
        config=TransitionConfig(crisis_to_volatile=3, min_candles_before_transition=0),
    )
    _step(sm, REGIME_VOLATILE, ts_offset=1)
    assert sm.current_regime == REGIME_CRISIS
    _step(sm, REGIME_VOLATILE, ts_offset=2)
    assert sm.current_regime == REGIME_CRISIS
    _step(sm, REGIME_VOLATILE, ts_offset=3)
    assert sm.current_regime == REGIME_VOLATILE
