"""Pure dynamic-exit FSM helpers (no exchange integration)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from src.v25.contracts.dynamic_exit import DynamicExitState, ExitAction, ExitActionType, ExitStage

if TYPE_CHECKING:
    from src.v25.config.loader import DynamicExitConfig

_ONE = Decimal("1")

# Default constants (used when no DynamicExitConfig is provided)
_R_HALF = Decimal("0.5")
_R_ONE_HALF = Decimal("1.5")
_R_THREE = Decimal("3.0")
_ATR_MULT_PROFIT = Decimal("2.0")
_ATR_MULT_TREND = Decimal("1.2")
_PARTIAL_PROFIT = Decimal("0.30")
_PARTIAL_TREND = Decimal("0.20")


def _require_positive(name: str, value: Decimal) -> None:
    if value <= Decimal("0"):
        raise ValueError(f"{name} must be > 0")


def _price_at_r(entry_price: Decimal, r_value_pct: Decimal, r_multiple: Decimal) -> Decimal:
    return entry_price * (_ONE + (r_value_pct * r_multiple))


def _infer_r_value_pct(state: DynamicExitState, r1: Decimal = _R_HALF) -> Decimal:
    if state.tp1_price is None:
        raise ValueError("state.tp1_price is required")
    if state.side == "SHORT":
        return ((_ONE - (state.tp1_price / state.entry_price))) / r1
    return ((state.tp1_price / state.entry_price) - _ONE) / r1


def _price_at_r_short(entry_price: Decimal, r_value_pct: Decimal, r_multiple: Decimal) -> Decimal:
    return entry_price * (_ONE - (r_value_pct * r_multiple))


def init_dynamic_exit(
    entry_price: Decimal,
    sl_pct: Decimal,
    r_value_pct: Decimal,
    atr_pct: Decimal,
    ts: datetime,
    side: str = "LONG",
    config: DynamicExitConfig | None = None,
) -> DynamicExitState:
    """Initialize FSM state for LONG or SHORT positions.

    When *config* is None, uses built-in defaults (+0.5R, +1.5R, +3.0R).
    """
    _require_positive("entry_price", entry_price)
    _require_positive("sl_pct", sl_pct)
    _require_positive("r_value_pct", r_value_pct)
    _require_positive("atr_pct", atr_pct)
    if side not in ("LONG", "SHORT"):
        raise ValueError(f"side must be LONG or SHORT, got {side}")

    r1 = Decimal(str(config.r_breakeven)) if config else _R_HALF
    r2 = Decimal(str(config.r_profit_capture)) if config else _R_ONE_HALF
    r3 = Decimal(str(config.r_trend_rider)) if config else _R_THREE

    if side == "LONG":
        stop_price = entry_price * (_ONE - sl_pct)
        tp1 = _price_at_r(entry_price, r_value_pct, r1)
        tp2 = _price_at_r(entry_price, r_value_pct, r2)
        tp3 = _price_at_r(entry_price, r_value_pct, r3)
    else:
        stop_price = entry_price * (_ONE + sl_pct)
        tp1 = _price_at_r_short(entry_price, r_value_pct, r1)
        tp2 = _price_at_r_short(entry_price, r_value_pct, r2)
        tp3 = _price_at_r_short(entry_price, r_value_pct, r3)

    _require_positive("stop_price", stop_price)

    return DynamicExitState(
        stage=ExitStage.ENTRY,
        side=side,
        entry_price=entry_price,
        stop_price=stop_price,
        tp1_price=tp1,
        tp2_price=tp2,
        tp3_price=tp3,
        last_update_ts=ts,
        reason="initialized",
    )


def update_dynamic_exit(
    state: DynamicExitState,
    current_price: Decimal,
    atr_pct: Decimal,
    ts: datetime,
    config: DynamicExitConfig | None = None,
) -> DynamicExitState:
    """Update FSM state only (action-agnostic helper)."""
    next_state, _ = update_dynamic_exit_with_action(
        state=state,
        current_price=current_price,
        atr_pct=atr_pct,
        ts=ts,
        config=config,
    )
    return next_state


def update_dynamic_exit_with_action(
    state: DynamicExitState,
    current_price: Decimal,
    atr_pct: Decimal,
    ts: datetime,
    config: DynamicExitConfig | None = None,
) -> tuple[DynamicExitState, ExitAction]:
    """Update FSM and propose one action.

    When *config* is None, uses built-in defaults.
    This module proposes actions only; actual execution is handled elsewhere.
    """
    _require_positive("current_price", current_price)
    _require_positive("atr_pct", atr_pct)

    # Resolve config values or use defaults
    r1 = Decimal(str(config.r_breakeven)) if config else _R_HALF
    r2 = Decimal(str(config.r_profit_capture)) if config else _R_ONE_HALF
    r3 = Decimal(str(config.r_trend_rider)) if config else _R_THREE
    atr_m_profit = Decimal(str(config.atr_mult_profit_capture)) if config else _ATR_MULT_PROFIT
    atr_m_trend = Decimal(str(config.atr_mult_trend_rider)) if config else _ATR_MULT_TREND
    partial_profit = Decimal(str(config.partial_fraction_profit_capture)) if config else _PARTIAL_PROFIT
    partial_trend = Decimal(str(config.partial_fraction_trend_rider)) if config else _PARTIAL_TREND

    r_value_pct = _infer_r_value_pct(state, r1)
    _require_positive("r_value_pct", r_value_pct)

    is_short = state.side == "SHORT"
    risk_abs = state.entry_price * r_value_pct
    if is_short:
        pnl_r = (state.entry_price - current_price) / risk_abs
    else:
        pnl_r = (current_price - state.entry_price) / risk_abs

    next_stage = state.stage
    reason = "no_transition"
    if state.stage == ExitStage.ENTRY and pnl_r >= r1:
        next_stage = ExitStage.BREAKEVEN_LOCK
        reason = "to_breakeven_lock"
    elif state.stage == ExitStage.BREAKEVEN_LOCK and pnl_r >= r2:
        next_stage = ExitStage.PROFIT_CAPTURE
        reason = "to_profit_capture"
    elif state.stage == ExitStage.PROFIT_CAPTURE and pnl_r >= r3:
        next_stage = ExitStage.TREND_RIDER
        reason = "to_trend_rider"

    next_stop = state.stop_price
    if is_short:
        # SHORT: stop is ABOVE entry, trailing moves DOWN (min)
        if next_stage == ExitStage.BREAKEVEN_LOCK:
            next_stop = min(next_stop, state.entry_price)
        elif next_stage == ExitStage.PROFIT_CAPTURE:
            candidate = current_price * (_ONE + (atr_pct * atr_m_profit))
            next_stop = min(next_stop, candidate)
        elif next_stage == ExitStage.TREND_RIDER:
            candidate = current_price * (_ONE + (atr_pct * atr_m_trend))
            next_stop = min(next_stop, candidate)
    else:
        # LONG: stop is BELOW entry, trailing moves UP (max)
        if next_stage == ExitStage.BREAKEVEN_LOCK:
            next_stop = max(next_stop, state.entry_price)
        elif next_stage == ExitStage.PROFIT_CAPTURE:
            candidate = current_price * (_ONE - (atr_pct * atr_m_profit))
            next_stop = max(next_stop, candidate)
        elif next_stage == ExitStage.TREND_RIDER:
            candidate = current_price * (_ONE - (atr_pct * atr_m_trend))
            next_stop = max(next_stop, candidate)

    next_state = state.model_copy(
        update={
            "stage": next_stage,
            "stop_price": next_stop,
            "last_update_ts": ts,
            "reason": reason,
        }
    )

    stage_before = state.stage
    stage_after = next_stage
    if stage_before != stage_after:
        if stage_before == ExitStage.ENTRY and stage_after == ExitStage.BREAKEVEN_LOCK:
            action = ExitAction(
                action_type=ExitActionType.UPDATE_STOP,
                new_stop_price=next_stop,
                take_profit_fraction=None,
                stage_before=stage_before,
                stage_after=stage_after,
                reason=reason,
            )
        elif stage_before == ExitStage.BREAKEVEN_LOCK and stage_after == ExitStage.PROFIT_CAPTURE:
            action = ExitAction(
                action_type=ExitActionType.TAKE_PARTIAL,
                new_stop_price=None,
                take_profit_fraction=partial_profit,
                stage_before=stage_before,
                stage_after=stage_after,
                reason=reason,
            )
        else:
            action = ExitAction(
                action_type=ExitActionType.TAKE_PARTIAL,
                new_stop_price=None,
                take_profit_fraction=partial_trend,
                stage_before=stage_before,
                stage_after=stage_after,
                reason=reason,
            )
    elif (not is_short and next_stop > state.stop_price) or (is_short and next_stop < state.stop_price):
        action = ExitAction(
            action_type=ExitActionType.UPDATE_STOP,
            new_stop_price=next_stop,
            take_profit_fraction=None,
            stage_before=stage_before,
            stage_after=stage_after,
            reason="trail_tightened",
        )
    else:
        action = ExitAction(
            action_type=ExitActionType.NOOP,
            new_stop_price=None,
            take_profit_fraction=None,
            stage_before=stage_before,
            stage_after=stage_after,
            reason="noop",
        )

    return next_state, action
