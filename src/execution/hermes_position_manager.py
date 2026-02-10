"""HERMES-driven position management actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
