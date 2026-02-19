from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.execution.hermes_position_manager import HermesPositionManager
from src.v25.contracts.order_intent import OrderIntentType


class _Broker:
    def __init__(self) -> None:
        self.closed: list[str] = []
        self.sl: list[tuple[str, float]] = []
        self.tp: list[tuple[str, float]] = []

    def close_position(self, *, symbol: str, reason: str) -> None:
        self.closed.append(f"{symbol}:{reason}")

    def modify_stop_loss(self, *, symbol: str, stop_price: float) -> None:
        self.sl.append((symbol, stop_price))

    def modify_take_profit(self, *, symbol: str, tp_price: float) -> None:
        self.tp.append((symbol, tp_price))


def test_hermes_position_manager_auto_actions() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)

    r1 = pm.handle(symbol="BTCUSDT", action="CLOSE_POSITION", execution_mode="auto")
    r2 = pm.handle(symbol="BTCUSDT", action="ADJUST_SL", execution_mode="auto", value=98000.0)
    r3 = pm.handle(symbol="BTCUSDT", action="ADJUST_TP", execution_mode="auto", value=105000.0)

    assert r1.handled and r2.handled and r3.handled
    assert broker.closed
    assert broker.sl == [("BTCUSDT", 98000.0)]
    assert broker.tp == [("BTCUSDT", 105000.0)]


def test_hermes_position_manager_advisory_mode() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    out = pm.handle(symbol="THYAO", action="CLOSE_POSITION", execution_mode="advisory", value=None)
    assert out.handled is True
    assert out.advisory_message is not None


def test_dynamic_exit_shadow_emits_intents_without_order_calls() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    ts = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)

    intents_1 = pm.shadow_dynamic_exit_intents(
        positions=[
            {
                "symbol": "BTCUSDT",
                "entry_price": 100.0,
                "current_price": 100.5,
                "atr_pct": 0.005,
            }
        ],
        ts=ts,
    )
    assert intents_1
    assert intents_1[0].action_type == OrderIntentType.UPDATE_STOP

    intents_2 = pm.shadow_dynamic_exit_intents(
        positions=[
            {
                "symbol": "BTCUSDT",
                "entry_price": 100.0,
                "current_price": 101.5,
                "atr_pct": 0.005,
            }
        ],
        ts=ts,
    )
    assert intents_2
    assert intents_2[0].action_type == OrderIntentType.TAKE_PARTIAL

    assert broker.closed == []
    assert broker.sl == []
    assert broker.tp == []


def test_dynamic_exit_shadow_suppresses_noop_on_repeat_profit_capture_stage() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    ts = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)

    pm.shadow_dynamic_exit_intents(
        positions=[{"symbol": "BTCUSDT", "entry_price": 100.0, "current_price": 100.5, "atr_pct": 0.005}],
        ts=ts,
    )
    intents_tp = pm.shadow_dynamic_exit_intents(
        positions=[{"symbol": "BTCUSDT", "entry_price": 100.0, "current_price": 101.5, "atr_pct": 0.005}],
        ts=ts,
    )
    assert intents_tp
    assert intents_tp[0].action_type == OrderIntentType.TAKE_PARTIAL

    intents_noop = pm.shadow_dynamic_exit_intents(
        positions=[{"symbol": "BTCUSDT", "entry_price": 100.0, "current_price": 101.5, "atr_pct": 0.005}],
        ts=ts,
    )
    assert intents_noop == tuple()
    assert broker.closed == []
    assert broker.sl == []
    assert broker.tp == []


def test_dynamic_exit_shadow_cleans_stale_states() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    ts = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)

    pm.shadow_dynamic_exit_intents(
        positions=[
            {
                "position_id": "p1",
                "symbol": "BTCUSDT",
                "entry_price": 100.0,
                "current_price": 100.5,
                "atr_pct": 0.005,
            }
        ],
        ts=ts,
    )
    assert "p1" in pm._shadow_states

    pm.shadow_dynamic_exit_intents(positions=[], ts=ts)
    assert "p1" in pm._shadow_states

    pm.shadow_dynamic_exit_intents(positions=[], ts=ts)
    assert "p1" in pm._shadow_states

    pm.shadow_dynamic_exit_intents(positions=[], ts=ts)
    assert pm._shadow_states == {}
    assert pm._shadow_missed_counts == {}


def test_dynamic_exit_shadow_uses_position_id_cache_key() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    ts = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)

    intents = pm.shadow_dynamic_exit_intents(
        positions=[
            {
                "position_id": "p1",
                "symbol": "BTCUSDT",
                "entry_price": 100.0,
                "current_price": 100.5,
                "atr_pct": 0.005,
            },
            {
                "position_id": "p2",
                "symbol": "BTCUSDT",
                "entry_price": 100.0,
                "current_price": 100.5,
                "atr_pct": 0.005,
            },
        ],
        ts=ts,
    )

    assert len(intents) == 2
    assert intents[0].action_type == OrderIntentType.UPDATE_STOP
    assert intents[1].action_type == OrderIntentType.UPDATE_STOP
    assert "p1" in pm._shadow_states
    assert "p2" in pm._shadow_states
    assert len(pm._shadow_states) == 2
    assert broker.closed == []
    assert broker.sl == []
    assert broker.tp == []


def test_dynamic_exit_shadow_skips_duplicate_symbol_without_ids_and_warns(caplog) -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    ts = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)

    with caplog.at_level(logging.WARNING):
        intents = pm.shadow_dynamic_exit_intents(
            positions=[
                {"symbol": "BTCUSDT", "entry_price": 100.0, "current_price": 100.5, "atr_pct": 0.005},
                {"symbol": "BTCUSDT", "entry_price": 100.0, "current_price": 100.5, "atr_pct": 0.005},
            ],
            ts=ts,
        )

    assert intents == tuple()
    assert "duplicate_symbol_missing_position_id" in caplog.text
    assert pm._shadow_states == {}
    assert pm._shadow_missed_counts == {}
    assert broker.closed == []
    assert broker.sl == []
    assert broker.tp == []
