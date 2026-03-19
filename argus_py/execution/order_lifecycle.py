from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class OrderLifecycleState(str, Enum):
    NEW = "NEW"
    ROUTED = "ROUTED"
    ACCEPTED = "ACCEPTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


TERMINAL_STATES = {
    OrderLifecycleState.FILLED,
    OrderLifecycleState.CANCELED,
    OrderLifecycleState.REJECTED,
    OrderLifecycleState.ERROR,
}


@dataclass(frozen=True)
class OrderLifecycleEvent:
    ts_utc: str
    state: OrderLifecycleState
    detail: str


@dataclass
class OrderLifecycleRecord:
    order_id: str
    symbol: str
    requested_qty: float
    state: OrderLifecycleState = OrderLifecycleState.NEW
    filled_qty: float = 0.0
    avg_price: float = 0.0
    events: List[OrderLifecycleEvent] = field(default_factory=list)

    def to_json(self) -> Dict[str, object]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "requested_qty": self.requested_qty,
            "state": self.state.value,
            "filled_qty": self.filled_qty,
            "avg_price": self.avg_price,
            "events": [asdict(e) | {"state": e.state.value} for e in self.events],
        }


class OrderLifecycleStateMachine:
    """Idempotent order lifecycle tracker."""

    def __init__(self) -> None:
        self._orders: Dict[str, OrderLifecycleRecord] = {}

    def ensure(self, order_id: str, symbol: str, requested_qty: float) -> OrderLifecycleRecord:
        oid = str(order_id)
        if oid not in self._orders:
            rec = OrderLifecycleRecord(order_id=oid, symbol=str(symbol), requested_qty=float(requested_qty))
            rec.events.append(self._event(OrderLifecycleState.NEW, "order created"))
            rec.events.append(self._event(OrderLifecycleState.ROUTED, "order routed to exchange"))
            rec.state = OrderLifecycleState.ROUTED
            self._orders[oid] = rec
        return self._orders[oid]

    def transition(
        self,
        order_id: str,
        *,
        exchange_status: str,
        filled_qty: float,
        avg_price: float,
        reason: str = "",
    ) -> OrderLifecycleRecord:
        oid = str(order_id)
        if oid not in self._orders:
            raise KeyError(f"Unknown order_id: {oid}")
        rec = self._orders[oid]
        incoming = self._map_exchange_status(exchange_status=exchange_status, filled_qty=filled_qty, requested_qty=rec.requested_qty)
        if rec.state in TERMINAL_STATES:
            return rec
        if incoming == rec.state:
            return rec

        rec.filled_qty = float(max(0.0, filled_qty))
        rec.avg_price = float(max(0.0, avg_price))
        rec.state = incoming
        detail = reason or f"exchange_status={exchange_status}"
        rec.events.append(self._event(incoming, detail))
        return rec

    def get(self, order_id: str) -> Optional[OrderLifecycleRecord]:
        return self._orders.get(str(order_id))

    @staticmethod
    def is_terminal(state: OrderLifecycleState) -> bool:
        return state in TERMINAL_STATES

    def _map_exchange_status(self, *, exchange_status: str, filled_qty: float, requested_qty: float) -> OrderLifecycleState:
        st = str(exchange_status or "").strip().upper()
        f = max(0.0, float(filled_qty))
        req = max(1e-12, float(requested_qty))
        if st in {"REJECTED", "ERROR"}:
            return OrderLifecycleState.REJECTED if st == "REJECTED" else OrderLifecycleState.ERROR
        if st in {"CANCELED", "CANCELLED"}:
            return OrderLifecycleState.CANCELED
        if st in {"ACCEPTED", "NEW"}:
            return OrderLifecycleState.ACCEPTED
        if st in {"PARTIAL"}:
            return OrderLifecycleState.PARTIAL
        if st in {"FILLED"}:
            if f >= (req - 1e-9):
                return OrderLifecycleState.FILLED
            return OrderLifecycleState.PARTIAL
        if f <= 0:
            return OrderLifecycleState.ACCEPTED
        if f >= (req - 1e-9):
            return OrderLifecycleState.FILLED
        return OrderLifecycleState.PARTIAL

    @staticmethod
    def _event(state: OrderLifecycleState, detail: str) -> OrderLifecycleEvent:
        return OrderLifecycleEvent(ts_utc=datetime.now(timezone.utc).isoformat(), state=state, detail=str(detail))


__all__ = [
    "OrderLifecycleStateMachine",
    "OrderLifecycleState",
    "OrderLifecycleRecord",
    "OrderLifecycleEvent",
]
