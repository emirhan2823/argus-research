"""Tests for EventBus."""

from src.core.events import EventBus, EventType


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.CANDLE_CLOSE, lambda data: received.append(data))
        bus.publish(EventType.CANDLE_CLOSE, {"price": 42000})
        assert len(received) == 1
        assert received[0]["price"] == 42000

    def test_multiple_subscribers(self):
        bus = EventBus()
        results = []
        bus.subscribe(EventType.ALERT, lambda d: results.append("a"))
        bus.subscribe(EventType.ALERT, lambda d: results.append("b"))
        bus.publish(EventType.ALERT, {})
        assert results == ["a", "b"]

    def test_no_cross_talk(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.CANDLE_CLOSE, lambda d: received.append("candle"))
        bus.publish(EventType.HEARTBEAT, {})
        assert len(received) == 0

    def test_hermes_events_exist(self):
        assert EventType.HERMES_ALERT.value == "hermes_alert"
        assert EventType.HERMES_CLOSE_POSITION.value == "hermes_close_position"
        assert EventType.HERMES_ADJUST_SL.value == "hermes_adjust_sl"
        assert EventType.ADVISORY_SIGNAL.value == "advisory_signal"

    def test_clear(self):
        bus = EventBus()
        bus.subscribe(EventType.ERROR, lambda d: None)
        assert bus.subscriber_count == 1
        bus.clear()
        assert bus.subscriber_count == 0

    def test_publish_hermes_block(self):
        bus = EventBus()
        blocked = []
        bus.subscribe(EventType.HERMES_BLOCK, lambda d: blocked.append(d))
        bus.publish(EventType.HERMES_BLOCK, {"symbol": "BTCUSDT", "reason": "hack news"})
        assert len(blocked) == 1
        assert blocked[0]["symbol"] == "BTCUSDT"
