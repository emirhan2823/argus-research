"""Pure mapper from dynamic-exit actions to order intents."""

from __future__ import annotations

from datetime import datetime

from src.v25.contracts.dynamic_exit import ExitAction, ExitActionType
from src.v25.contracts.order_intent import OrderIntent, OrderIntentType


def map_exit_action_to_intent(action: ExitAction, symbol: str, ts: datetime) -> OrderIntent:
    """Map FSM ExitAction into an execution-agnostic OrderIntent.

    CLOSE_POSITION is reserved for future use and is not emitted here yet.
    """
    if action.action_type == ExitActionType.UPDATE_STOP:
        intent_type = OrderIntentType.UPDATE_STOP
    elif action.action_type == ExitActionType.TAKE_PARTIAL:
        intent_type = OrderIntentType.TAKE_PARTIAL
    elif action.action_type == ExitActionType.NOOP:
        intent_type = OrderIntentType.NOOP
    else:
        raise ValueError(f"Unsupported ExitActionType: {action.action_type}")

    reason = action.reason
    if action.stage_before != action.stage_after:
        reason = f"{reason} [{action.stage_before.value}->{action.stage_after.value}]"

    return OrderIntent(
        action_type=intent_type,
        symbol=symbol,
        new_stop_price=action.new_stop_price,
        take_profit_fraction=action.take_profit_fraction,
        reason=reason,
        source="dynamic_exit",
        ts=ts,
    )
