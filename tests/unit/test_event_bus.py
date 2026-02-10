from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.core.event_bus import BusEvent, EventBus, EventType


@pytest.mark.anyio
async def test_event_bus_dispatches_specific_and_wildcard_handlers() -> None:
    bus = EventBus()
    got = {"specific": 0, "wildcard": 0}

    async def specific_handler(event: BusEvent) -> None:
        assert event.event_type == EventType.DECISION
        got["specific"] += 1

    def wildcard_handler(event: BusEvent) -> None:
        got["wildcard"] += 1

    await bus.subscribe(specific_handler, EventType.DECISION)
    await bus.subscribe(wildcard_handler, None)

    await bus.emit(EventType.DECISION, {"k": 1}, source="test")

    assert got["specific"] == 1
    assert got["wildcard"] == 1


@pytest.mark.anyio
async def test_event_bus_captures_dead_letter_on_handler_error() -> None:
    bus = EventBus()

    def bad_handler(_: BusEvent) -> None:
        raise RuntimeError("boom")

    await bus.subscribe(bad_handler, EventType.METRICS)
    await bus.emit(EventType.METRICS, {"metric": "x"}, source="test")

    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0].error == "boom"
