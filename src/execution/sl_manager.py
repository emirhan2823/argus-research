"""Stop-loss enforcement manager.

Supports both static and dynamic-exit-driven trailing stop loss.
When a DynamicExitState is provided, the trailing_stop from the FSM
takes precedence over the static stop_price (GR-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class SLBrokerAdapter(Protocol):
    def place_stop_loss(
        self,
        *,
        symbol: str,
        side: str,
        size: float,
        stop_price: float,
    ) -> str:
        ...

    def close_position(self, *, symbol: str, reason: str) -> None:
        ...


@dataclass(frozen=True)
class StopLossResult:
    success: bool
    sl_order_id: str | None
    reason: str
    timestamp: datetime
    used_trailing: bool = False


def _extract_trailing_stop(dynamic_exit_state: Any) -> float | None:
    """Extract trailing_stop from a DynamicExitState if active.

    The dynamic exit FSM sets trailing_stop to a non-zero value
    once the position reaches PROFIT_CAPTURE stage or beyond.
    Returns None if no trailing stop is active.
    """
    if dynamic_exit_state is None:
        return None
    trailing = getattr(dynamic_exit_state, "trailing_stop", None)
    if trailing is None or trailing == 0.0:
        return None
    return float(trailing)


@dataclass
class StopLossManager:
    broker: SLBrokerAdapter

    def enforce(
        self,
        *,
        symbol: str,
        side: str,
        size: float,
        stop_price: float,
        timestamp: datetime,
        dynamic_exit_state: Any | None = None,
    ) -> StopLossResult:
        """Enforce stop loss, preferring dynamic trailing SL when available.

        Parameters
        ----------
        dynamic_exit_state : DynamicExitState | None
            If provided and has an active trailing_stop, that value
            is used instead of the static stop_price.
        """
        trailing = _extract_trailing_stop(dynamic_exit_state)
        effective_stop = trailing if trailing is not None else stop_price
        used_trailing = trailing is not None

        try:
            sl_order_id = self.broker.place_stop_loss(
                symbol=symbol,
                side=side,
                size=size,
                stop_price=effective_stop,
            )
            reason = "trailing_sl_placed" if used_trailing else "sl_placed"
            return StopLossResult(
                success=True,
                sl_order_id=sl_order_id,
                reason=reason,
                timestamp=timestamp,
                used_trailing=used_trailing,
            )
        except Exception as exc:
            self.broker.close_position(symbol=symbol, reason=f"sl_failed:{exc}")
            return StopLossResult(
                success=False,
                sl_order_id=None,
                reason="sl_failed_position_closed",
                timestamp=timestamp,
                used_trailing=used_trailing,
            )
