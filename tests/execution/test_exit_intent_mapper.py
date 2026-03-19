from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.execution.exit_intent_mapper import map_exit_action_to_intent
from src.v25.contracts.dynamic_exit import ExitAction, ExitActionType, ExitStage
from src.v25.contracts.order_intent import OrderIntentType


def _ts() -> datetime:
    return datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)


def test_map_update_stop_to_intent() -> None:
    action = ExitAction(
        action_type=ExitActionType.UPDATE_STOP,
        new_stop_price=Decimal("100.25"),
        take_profit_fraction=None,
        stage_before=ExitStage.ENTRY,
        stage_after=ExitStage.BREAKEVEN_LOCK,
        reason="to_breakeven_lock",
    )
    intent = map_exit_action_to_intent(action=action, symbol="BTC-USDT", ts=_ts())
    assert intent.action_type == OrderIntentType.UPDATE_STOP
    assert intent.symbol == "BTC-USDT"
    assert intent.new_stop_price == Decimal("100.25")
    assert intent.take_profit_fraction is None
    assert intent.source == "dynamic_exit"
    assert "to_breakeven_lock" in intent.reason


def test_map_take_partial_to_intent() -> None:
    action = ExitAction(
        action_type=ExitActionType.TAKE_PARTIAL,
        new_stop_price=None,
        take_profit_fraction=Decimal("0.30"),
        stage_before=ExitStage.BREAKEVEN_LOCK,
        stage_after=ExitStage.PROFIT_CAPTURE,
        reason="to_profit_capture",
    )
    intent = map_exit_action_to_intent(action=action, symbol="ETH-USDT", ts=_ts())
    assert intent.action_type == OrderIntentType.TAKE_PARTIAL
    assert intent.symbol == "ETH-USDT"
    assert intent.new_stop_price is None
    assert intent.take_profit_fraction == Decimal("0.30")
    assert intent.source == "dynamic_exit"
    assert "BREAKEVEN_LOCK->PROFIT_CAPTURE" in intent.reason


def test_map_noop_to_intent() -> None:
    action = ExitAction(
        action_type=ExitActionType.NOOP,
        new_stop_price=None,
        take_profit_fraction=None,
        stage_before=ExitStage.PROFIT_CAPTURE,
        stage_after=ExitStage.PROFIT_CAPTURE,
        reason="noop",
    )
    intent = map_exit_action_to_intent(action=action, symbol="SOL-USDT", ts=_ts())
    assert intent.action_type == OrderIntentType.NOOP
    assert intent.symbol == "SOL-USDT"
    assert intent.new_stop_price is None
    assert intent.take_profit_fraction is None
    assert intent.reason == "noop"
    assert intent.source == "dynamic_exit"
