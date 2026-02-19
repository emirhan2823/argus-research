"""HERMES-driven position management actions."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from src.execution.dynamic_exit import init_dynamic_exit, update_dynamic_exit_with_action
from src.execution.exit_intent_mapper import map_exit_action_to_intent
from src.execution.hyper_precision import compute_trailing_sl
from src.v25.contracts.dynamic_exit import DynamicExitState, ExitActionType
from src.v25.contracts.order_intent import OrderIntent, OrderIntentType

if TYPE_CHECKING:
    from src.v25.config.loader import DynamicExitConfig


_LOG = logging.getLogger(__name__)


class HermesBrokerAdapter(Protocol):
    def close_position(self, *, symbol: str, reason: str) -> None:
        ...

    def modify_stop_loss(self, *, symbol: str, stop_price: float) -> None:
        ...

    def modify_take_profit(self, *, symbol: str, tp_price: float) -> None:
        ...


@dataclass(frozen=True)
class HermesActionResult:
    handled: bool
    action: str
    reason: str
    advisory_message: str | None = None


@dataclass
class HermesPositionManager:
    broker: HermesBrokerAdapter
    shadow_enabled: bool = True
    shadow_noop_debug_sample_n: int = 100
    dynamic_exit_config: DynamicExitConfig | None = None
    _shadow_states: dict[str, DynamicExitState] = field(default_factory=dict, repr=False)
    _shadow_missed_counts: dict[str, int] = field(default_factory=dict, repr=False)
    _shadow_noop_counter: int = field(default=0, repr=False)
    _shadow_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @staticmethod
    def _position_cache_key(position: dict[str, float | str], symbol: str) -> str:
        position_id = position.get("position_id")
        if position_id is None:
            position_id = position.get("id")
        if position_id is not None:
            key = str(position_id).strip()
            if key:
                return key
        return symbol

    @staticmethod
    def _has_position_id(position: dict[str, float | str]) -> bool:
        position_id = position.get("position_id")
        if position_id is None:
            position_id = position.get("id")
        if position_id is None:
            return False
        return bool(str(position_id).strip())

    def handle(
        self,
        *,
        symbol: str,
        action: str,
        execution_mode: str,
        value: float | None = None,
    ) -> HermesActionResult:
        if execution_mode == "advisory":
            msg = f"[ADVISORY_UPDATE] {symbol} action={action} value={value}"
            return HermesActionResult(True, action, "advisory_update_sent", advisory_message=msg)

        if action == "CLOSE_POSITION":
            self.broker.close_position(symbol=symbol, reason="hermes_close_position")
            return HermesActionResult(True, action, "position_closed")
        if action == "ADJUST_SL" and value is not None:
            self.broker.modify_stop_loss(symbol=symbol, stop_price=value)
            return HermesActionResult(True, action, "stop_loss_adjusted")
        if action == "ADJUST_TP" and value is not None:
            self.broker.modify_take_profit(symbol=symbol, tp_price=value)
            return HermesActionResult(True, action, "take_profit_adjusted")
        return HermesActionResult(False, action, "unsupported_action_or_missing_value")

    def shadow_dynamic_exit_intents(
        self,
        *,
        positions: list[dict[str, float | str]],
        ts: datetime,
        default_sl_pct: float = 0.01,
        default_r_value_pct: float = 0.01,
        default_atr_pct: float = 0.005,
    ) -> tuple[OrderIntent, ...]:
        """Shadow-only Dynamic Exit loop.

        Computes intents and logs them, but never sends orders.
        TODO: replace in-memory state cache with persisted state store.
        """
        if not self.shadow_enabled:
            return tuple()

        # Lock protects in-memory shadow state only.
        # If persistence or cross-thread execution is added, locking strategy must be revisited.
        with self._shadow_lock:
            intents: list[OrderIntent] = []
            current_keys: set[str] = set()
            missing_id_symbol_counts: dict[str, int] = {}

            for position in positions:
                raw_symbol = str(position.get("symbol", "")).strip()
                if not raw_symbol:
                    continue
                if not self._has_position_id(position):
                    missing_id_symbol_counts[raw_symbol] = missing_id_symbol_counts.get(raw_symbol, 0) + 1

            duplicate_missing_id_symbols = {
                symbol for symbol, count in missing_id_symbol_counts.items() if count > 1
            }
            warned_duplicate_symbols: set[str] = set()

            for position in positions:
                raw_symbol = str(position.get("symbol", "")).strip()
                if not raw_symbol:
                    continue

                has_position_id = self._has_position_id(position)
                if (not has_position_id) and raw_symbol in duplicate_missing_id_symbols:
                    if raw_symbol not in warned_duplicate_symbols:
                        _LOG.warning(
                            "dynamic_exit_shadow skip symbol=%s reason=duplicate_symbol_missing_position_id",
                            raw_symbol,
                        )
                        warned_duplicate_symbols.add(raw_symbol)
                    continue

                cache_key = self._position_cache_key(position=position, symbol=raw_symbol)
                if not cache_key:
                    continue
                symbol = raw_symbol or cache_key
                current_keys.add(cache_key)

                entry_raw = position.get("entry_price")
                price_raw = position.get("current_price")
                if entry_raw is None or price_raw is None:
                    continue

                entry_price = Decimal(str(entry_raw))
                current_price = Decimal(str(price_raw))
                sl_pct = Decimal(str(position.get("sl_pct", default_sl_pct)))
                r_value_pct = Decimal(str(position.get("r_value_pct", default_r_value_pct)))
                atr_pct = Decimal(str(position.get("atr_pct", default_atr_pct)))

                state = self._shadow_states.get(cache_key)
                if state is None:
                    side = str(position.get("side", "LONG")).upper()
                    if side not in ("LONG", "SHORT"):
                        side = "LONG"
                    state = init_dynamic_exit(
                        entry_price=entry_price,
                        sl_pct=sl_pct,
                        r_value_pct=r_value_pct,
                        atr_pct=atr_pct,
                        ts=ts,
                        side=side,
                        config=self.dynamic_exit_config,
                    )

                next_state, action = update_dynamic_exit_with_action(
                    state=state,
                    current_price=current_price,
                    atr_pct=atr_pct,
                    ts=ts,
                    config=self.dynamic_exit_config,
                )
                self._shadow_states[cache_key] = next_state

                if action.action_type == ExitActionType.NOOP:
                    self._shadow_noop_counter += 1
                    if (
                        self.shadow_noop_debug_sample_n > 0
                        and self._shadow_noop_counter % self.shadow_noop_debug_sample_n == 0
                    ):
                        _LOG.debug(
                            "dynamic_exit_shadow noop_sample symbol=%s key=%s stage=%s counter=%s",
                            symbol,
                            cache_key,
                            next_state.stage.value,
                            self._shadow_noop_counter,
                        )
                    continue

                intent = map_exit_action_to_intent(action=action, symbol=symbol, ts=ts)
                intents.append(intent)
                _LOG.info(
                    "dynamic_exit_shadow symbol=%s key=%s action=%s new_stop=%s tp_fraction=%s reason=%s",
                    symbol,
                    cache_key,
                    intent.action_type.value,
                    intent.new_stop_price,
                    intent.take_profit_fraction,
                    intent.reason,
                )

            for key in current_keys:
                self._shadow_missed_counts[key] = 0

            stale: list[str] = []
            for key in list(self._shadow_states):
                if key in current_keys:
                    continue
                misses = self._shadow_missed_counts.get(key, 0) + 1
                self._shadow_missed_counts[key] = misses
                if misses >= 3:
                    stale.append(key)

            for key in stale:
                del self._shadow_states[key]
                self._shadow_missed_counts.pop(key, None)

            return tuple(intents)

    # ------------------------------------------------------------------
    # PR-J02: Live execution of dynamic exit intents
    # ------------------------------------------------------------------

    def live_dynamic_exit_intents(
        self,
        *,
        positions: list[dict[str, float | str]],
        ts: datetime,
        default_sl_pct: float = 0.01,
        default_r_value_pct: float = 0.01,
        default_atr_pct: float = 0.005,
    ) -> tuple[OrderIntent, ...]:
        """Compute dynamic exit intents AND execute them against the broker.

        This is the "live" counterpart to ``shadow_dynamic_exit_intents``.
        For each non-NOOP intent, the broker is called:
          - UPDATE_STOP  → broker.modify_stop_loss (with hyper-precision trailing)
          - TAKE_PARTIAL → broker.close_position (partial close is logged but
            actual fractional close requires executor — this sends advisory)

        Returns the intents that were processed.
        """
        # First, compute intents using the same shadow logic
        intents = self.shadow_dynamic_exit_intents(
            positions=positions,
            ts=ts,
            default_sl_pct=default_sl_pct,
            default_r_value_pct=default_r_value_pct,
            default_atr_pct=default_atr_pct,
        )

        for intent in intents:
            symbol = intent.symbol
            try:
                if intent.action_type == OrderIntentType.UPDATE_STOP and intent.new_stop_price is not None:
                    # Look up position to get direction + ATR for trailing
                    pos = self._find_position(positions, symbol)
                    if pos is not None:
                        direction = str(pos.get("side", "LONG")).upper()
                        atr_raw = float(pos.get("atr_pct", default_atr_pct))
                        entry_price = float(pos.get("entry_price", 1.0))
                        atr_price_units = atr_raw * entry_price
                        current_price = float(pos.get("current_price", entry_price))

                        # Use hyper-precision trailing SL (3m ATR)
                        trailing_mult = 2.0  # default; could come from config
                        state = self._shadow_states.get(
                            self._position_cache_key(pos, symbol)
                        )
                        if state is not None and state.stage.value == "TREND_RIDER":
                            trailing_mult = 1.2

                        precision_sl = compute_trailing_sl(
                            direction=direction,
                            current_price=current_price,
                            atr=atr_price_units,
                            trailing_mult=trailing_mult,
                            current_sl=float(intent.new_stop_price),
                        )
                        self.broker.modify_stop_loss(symbol=symbol, stop_price=precision_sl)
                    else:
                        self.broker.modify_stop_loss(
                            symbol=symbol, stop_price=float(intent.new_stop_price)
                        )
                    _LOG.info(
                        "live_exit UPDATE_STOP symbol=%s new_sl=%s",
                        symbol, intent.new_stop_price,
                    )

                elif intent.action_type == OrderIntentType.TAKE_PARTIAL:
                    _LOG.info(
                        "live_exit TAKE_PARTIAL symbol=%s fraction=%s reason=%s",
                        symbol, intent.take_profit_fraction, intent.reason,
                    )
                    # Partial close requires the executor (with position quantity).
                    # Here we signal via broker.close_position as advisory.
                    # The pipeline orchestrator should handle actual partial close
                    # via executor.execute_partial_close().

                elif intent.action_type == OrderIntentType.CLOSE_POSITION:
                    self.broker.close_position(symbol=symbol, reason=intent.reason)
                    _LOG.info("live_exit CLOSE_POSITION symbol=%s", symbol)

            except Exception:
                _LOG.warning(
                    "live_exit failed symbol=%s action=%s",
                    symbol, intent.action_type.value, exc_info=True,
                )

        return intents

    @staticmethod
    def _find_position(
        positions: list[dict[str, float | str]], symbol: str
    ) -> dict[str, float | str] | None:
        """Find a position dict by symbol."""
        for pos in positions:
            if str(pos.get("symbol", "")).strip() == symbol:
                return pos
        return None
