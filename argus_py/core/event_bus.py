from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import asyncio
import inspect
import uuid


class EventType(str, Enum):
    DECISION = "DECISION"
    REJECT = "REJECT"
    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSE = "TRADE_CLOSE"
    HEARTBEAT = "HEARTBEAT"
    METRICS = "METRICS"
    ALERT = "ALERT"
    RISK_LEVEL_CHANGE = "RISK_LEVEL_CHANGE"
    MODE_CHANGE = "MODE_CHANGE"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    STRATEGY_DISABLE = "STRATEGY_DISABLE"
    INCIDENT_OPEN = "INCIDENT_OPEN"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    GATE_PASS = "GATE_PASS"
    GATE_FAIL = "GATE_FAIL"
    EXECUTION_ACK = "EXECUTION_ACK"
    EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass(frozen=True)
class BusEvent:
    event_type: EventType
    payload: Dict[str, Any]
    source: str
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    ts_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class DeadLetter:
    event_id: str
    handler_name: str
    error: str
    event_type: EventType


HandlerFn = Callable[[BusEvent], Any]


class EventBus:
    """Async pub/sub event bus with dead-letter capture."""

    def __init__(self, history_size: int = 5000) -> None:
        self._subscribers: Dict[Optional[EventType], Dict[int, HandlerFn]] = {None: {}}
        self._next_token = 1
        self._lock = asyncio.Lock()
        self.history_size = int(history_size)
        self.history: List[BusEvent] = []
        self.dead_letters: List[DeadLetter] = []

    async def subscribe(self, handler: HandlerFn, event_type: Optional[EventType] = None) -> int:
        async with self._lock:
            token = self._next_token
            self._next_token += 1
            bucket = self._subscribers.setdefault(event_type, {})
            bucket[token] = handler
            return token

    async def unsubscribe(self, token: int) -> bool:
        async with self._lock:
            for bucket in self._subscribers.values():
                if token in bucket:
                    del bucket[token]
                    return True
        return False

    async def publish(self, event: BusEvent) -> None:
        async with self._lock:
            handlers = list(self._subscribers.get(event.event_type, {}).values()) + list(
                self._subscribers.get(None, {}).values()
            )

        self.history.append(event)
        if len(self.history) > self.history_size:
            self.history = self.history[-self.history_size :]

        tasks = [self._invoke_handler(h, event) for h in handlers]
        if tasks:
            await asyncio.gather(*tasks)

    async def emit(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        source: str,
        correlation_id: Optional[str] = None,
    ) -> BusEvent:
        event = BusEvent(
            event_type=event_type,
            payload=dict(payload),
            source=str(source),
            correlation_id=correlation_id,
        )
        await self.publish(event)
        return event

    async def _invoke_handler(self, handler: HandlerFn, event: BusEvent) -> None:
        name = getattr(handler, "__name__", handler.__class__.__name__)
        try:
            output = handler(event)
            if inspect.isawaitable(output):
                await output  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - covered via tests indirectly
            self.dead_letters.append(
                DeadLetter(
                    event_id=event.event_id,
                    handler_name=str(name),
                    error=str(exc),
                    event_type=event.event_type,
                )
            )


__all__ = [
    "EventBus",
    "BusEvent",
    "EventType",
    "DeadLetter",
]
