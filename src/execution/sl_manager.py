"""Stop-loss enforcement manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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
    ) -> StopLossResult:
        try:
            sl_order_id = self.broker.place_stop_loss(
                symbol=symbol,
                side=side,
                size=size,
                stop_price=stop_price,
            )
            return StopLossResult(
                success=True,
                sl_order_id=sl_order_id,
                reason="sl_placed",
                timestamp=timestamp,
            )
        except Exception as exc:
            self.broker.close_position(symbol=symbol, reason=f"sl_failed:{exc}")
            return StopLossResult(
                success=False,
                sl_order_id=None,
                reason="sl_failed_position_closed",
                timestamp=timestamp,
            )
