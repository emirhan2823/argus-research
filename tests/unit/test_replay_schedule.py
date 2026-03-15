from __future__ import annotations

from datetime import timezone

import pytest

from src.main import resolve_replay_schedule


def test_resolve_replay_schedule_from_now_only() -> None:
    ts, dt, cycles = resolve_replay_schedule(
        replay_now="2026-02-24T00:00:00Z",
        replay_start=None,
        replay_end=None,
        cycle_step_minutes=5,
    )
    assert ts is not None
    assert dt is not None
    assert cycles is None
    assert dt.tzinfo == timezone.utc


def test_resolve_replay_schedule_from_window() -> None:
    ts, dt, cycles = resolve_replay_schedule(
        replay_now=None,
        replay_start="2026-02-24T00:00:00Z",
        replay_end="2026-02-24T00:30:00Z",
        cycle_step_minutes=5,
    )
    assert ts is not None
    assert dt is not None
    assert cycles == 7  # inclusive: 00:00,00:05,...,00:30
    assert dt.tzinfo == timezone.utc


def test_resolve_replay_schedule_requires_start_end_pair() -> None:
    with pytest.raises(ValueError):
        resolve_replay_schedule(
            replay_now=None,
            replay_start="2026-02-24T00:00:00Z",
            replay_end=None,
            cycle_step_minutes=5,
        )


def test_resolve_replay_schedule_rejects_inverted_window() -> None:
    with pytest.raises(ValueError):
        resolve_replay_schedule(
            replay_now=None,
            replay_start="2026-03-01T00:00:00Z",
            replay_end="2026-02-24T00:00:00Z",
            cycle_step_minutes=5,
        )

