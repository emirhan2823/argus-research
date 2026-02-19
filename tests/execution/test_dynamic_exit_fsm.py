from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.execution.dynamic_exit import init_dynamic_exit, update_dynamic_exit, update_dynamic_exit_with_action
from src.v25.contracts.dynamic_exit import ExitActionType, ExitStage


def _ts(offset_seconds: int) -> datetime:
    return datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)


def test_stage_transitions_at_exact_thresholds() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )
    assert state.stage == ExitStage.ENTRY
    assert state.stop_price == Decimal("99.00")

    state = update_dynamic_exit(state, current_price=Decimal("100.5"), atr_pct=Decimal("0.005"), ts=_ts(1))
    assert state.stage == ExitStage.BREAKEVEN_LOCK
    assert state.stop_price == Decimal("100")

    state = update_dynamic_exit(state, current_price=Decimal("101.5"), atr_pct=Decimal("0.005"), ts=_ts(2))
    assert state.stage == ExitStage.PROFIT_CAPTURE

    state = update_dynamic_exit(state, current_price=Decimal("103.0"), atr_pct=Decimal("0.005"), ts=_ts(3))
    assert state.stage == ExitStage.TREND_RIDER


def test_stop_monotonic_tightening() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )

    prices = [Decimal("100.5"), Decimal("101.0"), Decimal("101.5"), Decimal("102.0"), Decimal("103.0")]
    last_stop = state.stop_price
    for i, price in enumerate(prices, start=1):
        state = update_dynamic_exit(state, current_price=price, atr_pct=Decimal("0.005"), ts=_ts(i))
        assert state.stop_price >= last_stop
        last_stop = state.stop_price


def test_stop_not_above_current_price_during_uptrend_updates() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )

    prices = [Decimal("100.5"), Decimal("101.5"), Decimal("103.0")]
    for i, price in enumerate(prices, start=1):
        state = update_dynamic_exit(state, current_price=price, atr_pct=Decimal("0.005"), ts=_ts(i))
        assert state.stop_price <= price


def test_action_update_stop_on_breakeven_transition() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )
    next_state, action = update_dynamic_exit_with_action(
        state=state,
        current_price=Decimal("100.5"),
        atr_pct=Decimal("0.005"),
        ts=_ts(1),
    )
    assert next_state.stage == ExitStage.BREAKEVEN_LOCK
    assert action.action_type == ExitActionType.UPDATE_STOP
    assert action.new_stop_price == Decimal("100")


def test_action_take_partial_on_profit_capture_transition() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )
    state = update_dynamic_exit(state, current_price=Decimal("100.5"), atr_pct=Decimal("0.005"), ts=_ts(1))
    next_state, action = update_dynamic_exit_with_action(
        state=state,
        current_price=Decimal("101.5"),
        atr_pct=Decimal("0.005"),
        ts=_ts(2),
    )
    assert next_state.stage == ExitStage.PROFIT_CAPTURE
    assert action.action_type == ExitActionType.TAKE_PARTIAL
    assert action.take_profit_fraction == Decimal("0.30")


def test_action_update_stop_when_trailing_tightens_without_stage_change() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )
    state = update_dynamic_exit(state, current_price=Decimal("100.5"), atr_pct=Decimal("0.005"), ts=_ts(1))
    state = update_dynamic_exit(state, current_price=Decimal("101.5"), atr_pct=Decimal("0.005"), ts=_ts(2))
    next_state, action = update_dynamic_exit_with_action(
        state=state,
        current_price=Decimal("102.0"),
        atr_pct=Decimal("0.005"),
        ts=_ts(3),
    )
    assert next_state.stage == ExitStage.PROFIT_CAPTURE
    assert action.action_type == ExitActionType.UPDATE_STOP
    assert action.new_stop_price is not None
    assert action.new_stop_price > state.stop_price


def test_action_noop_when_nothing_changes() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
    )
    next_state, action = update_dynamic_exit_with_action(
        state=state,
        current_price=Decimal("100.2"),
        atr_pct=Decimal("0.005"),
        ts=_ts(1),
    )
    assert next_state.stage == ExitStage.ENTRY
    assert action.action_type == ExitActionType.NOOP


# ========================= SHORT-SIDE TESTS =========================


def test_short_init_stop_above_entry() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
        side="SHORT",
    )
    assert state.side == "SHORT"
    assert state.stop_price == Decimal("101.00")  # entry * (1 + sl_pct)
    assert state.tp1_price < state.entry_price    # target below entry for short


def test_short_stage_transitions() -> None:
    """SHORT: price going DOWN = profitable."""
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
        side="SHORT",
    )
    assert state.stage == ExitStage.ENTRY

    # +0.5R: price drops to 99.50
    state = update_dynamic_exit(state, current_price=Decimal("99.50"), atr_pct=Decimal("0.005"), ts=_ts(1))
    assert state.stage == ExitStage.BREAKEVEN_LOCK
    assert state.stop_price == Decimal("100")  # moved to breakeven (entry)

    # +1.5R: price drops to 98.50
    state = update_dynamic_exit(state, current_price=Decimal("98.50"), atr_pct=Decimal("0.005"), ts=_ts(2))
    assert state.stage == ExitStage.PROFIT_CAPTURE

    # +3.0R: price drops to 97.00
    state = update_dynamic_exit(state, current_price=Decimal("97.00"), atr_pct=Decimal("0.005"), ts=_ts(3))
    assert state.stage == ExitStage.TREND_RIDER


def test_short_stop_monotonic_tightening() -> None:
    """SHORT: stop should only move DOWN (never up)."""
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
        side="SHORT",
    )
    prices = [Decimal("99.50"), Decimal("99.00"), Decimal("98.50"), Decimal("98.00"), Decimal("97.00")]
    last_stop = state.stop_price
    for i, price in enumerate(prices, start=1):
        state = update_dynamic_exit(state, current_price=price, atr_pct=Decimal("0.005"), ts=_ts(i))
        assert state.stop_price <= last_stop, f"Stop moved UP at step {i}: {last_stop} -> {state.stop_price}"
        last_stop = state.stop_price


def test_short_stop_not_below_current_price() -> None:
    """SHORT: trailing stop should always be ABOVE current price."""
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
        side="SHORT",
    )
    prices = [Decimal("99.50"), Decimal("98.50"), Decimal("97.00")]
    for i, price in enumerate(prices, start=1):
        state = update_dynamic_exit(state, current_price=price, atr_pct=Decimal("0.005"), ts=_ts(i))
        assert state.stop_price >= price, f"Stop below price at step {i}"


def test_short_action_take_partial() -> None:
    state = init_dynamic_exit(
        entry_price=Decimal("100"),
        sl_pct=Decimal("0.01"),
        r_value_pct=Decimal("0.01"),
        atr_pct=Decimal("0.005"),
        ts=_ts(0),
        side="SHORT",
    )
    state = update_dynamic_exit(state, current_price=Decimal("99.50"), atr_pct=Decimal("0.005"), ts=_ts(1))
    next_state, action = update_dynamic_exit_with_action(
        state=state,
        current_price=Decimal("98.50"),
        atr_pct=Decimal("0.005"),
        ts=_ts(2),
    )
    assert next_state.stage == ExitStage.PROFIT_CAPTURE
    assert action.action_type == ExitActionType.TAKE_PARTIAL
    assert action.take_profit_fraction == Decimal("0.30")
