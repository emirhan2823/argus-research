"""ARGUS v2.0 — Event bus for decoupled component communication."""

from enum import Enum
from typing import Any, Callable


class EventType(str, Enum):
    CANDLE_CLOSE = "candle_close"
    SENTINEL_CHECK = "sentinel_check"
    FEATURES_READY = "features_ready"
    REGIME_SNAPSHOT = "regime_snapshot"
    REGIME_CHANGED = "regime_changed"
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_REJECTED = "signal_rejected"
    DECISION_MADE = "decision_made"
    RISK_CHECK = "risk_check"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    SL_PLACED = "sl_placed"
    SL_FAILED = "sl_failed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    KILL_SWITCH_CHANGE = "kill_switch_change"
    HEARTBEAT = "heartbeat"
    ALERT = "alert"
    DAILY_REPORT = "daily_report"
    ERROR = "error"
    # HERMES events
    HERMES_NEWS_RECEIVED = "hermes_news_received"
    HERMES_ALERT = "hermes_alert"
    HERMES_BLOCK = "hermes_block"
    HERMES_CLOSE_POSITION = "hermes_close_position"
    HERMES_ADJUST_SL = "hermes_adjust_sl"
    HERMES_ADJUST_TP = "hermes_adjust_tp"
    # Advisory events
    ADVISORY_SIGNAL = "advisory_signal"
    ADVISORY_UPDATE = "advisory_update"
    # Learning / Evolution events (v2.5)
    REFLECTION_COMPLETE = "reflection_complete"
    CORRECTION_EMITTED = "correction_emitted"
    DARWIN_FULL_EVOLUTION = "darwin_full_evolution"
    DARWIN_MICRO_EVOLUTION = "darwin_micro_evolution"
    GENOME_PROMOTED = "genome_promoted"
    MICRO_EVOLUTION_TRIGGERED = "micro_evolution_triggered"


class EventBus:
    """Simple synchronous pub/sub event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """Register a callback for a given event type."""
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(callback)

    def publish(self, event_type: EventType, data: Any) -> None:
        """Publish an event to all registered subscribers."""
        key = event_type.value
        for callback in self._subscribers.get(key, []):
            callback(data)

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        """Total number of registered callbacks."""
        return sum(len(cbs) for cbs in self._subscribers.values())
