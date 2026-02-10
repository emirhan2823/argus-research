from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Protocol

from .models import ExecutionIntent, ExecutionResult, ExchangeOrder, OrderSide, UrgencyLevel


class ExchangeGateway(Protocol):
    def place_order(self, intent: ExecutionIntent) -> ExchangeOrder:
        ...

    def place_stop_loss(self, symbol: str, side: OrderSide, qty: float, stop_price: float) -> str:
        ...

    def get_position_qty(self, symbol: str) -> float:
        ...


@dataclass(frozen=True)
class ReconciliationReport:
    symbol: str
    expected_qty: float
    exchange_qty: float
    delta_qty: float


class ReconciliationEngine:
    def compare(self, symbol: str, expected_qty: float, exchange_qty: float) -> ReconciliationReport:
        return ReconciliationReport(
            symbol=symbol,
            expected_qty=float(expected_qty),
            exchange_qty=float(exchange_qty),
            delta_qty=float(exchange_qty - expected_qty),
        )


class ExecutionEngineV2:
    """
    Execution v2 with urgency policy, reconciliation and stop-loss enforcement.
    """

    def __init__(
        self,
        exchange: ExchangeGateway,
        *,
        reconciliation: Optional[ReconciliationEngine] = None,
        urgency_slippage_bps: Optional[Dict[UrgencyLevel, float]] = None,
    ) -> None:
        self.exchange = exchange
        self.reconciliation = reconciliation or ReconciliationEngine()
        self.urgency_slippage_bps = urgency_slippage_bps or {
            UrgencyLevel.LOW: 3.0,
            UrgencyLevel.NORMAL: 8.0,
            UrgencyLevel.HIGH: 16.0,
            UrgencyLevel.CRITICAL: 28.0,
        }

    def execute(self, intent: ExecutionIntent, expected_post_qty: float) -> ExecutionResult:
        if intent.qty <= 0:
            return ExecutionResult(
                accepted=False,
                order_id=None,
                status="REJECTED",
                reason="qty must be > 0",
                stop_loss_enforced=False,
                reconciliation_delta=0.0,
            )

        normalized = self._normalize_intent(intent)
        order = self.exchange.place_order(normalized)
        if order.status.upper() not in {"FILLED", "PARTIAL", "ACCEPTED"}:
            return ExecutionResult(
                accepted=False,
                order_id=order.order_id,
                status=order.status,
                reason="exchange rejected order",
                stop_loss_enforced=False,
                reconciliation_delta=0.0,
            )

        sl_enforced = self._enforce_stop_loss(normalized, order)
        exchange_qty = float(self.exchange.get_position_qty(intent.symbol))
        recon = self.reconciliation.compare(intent.symbol, float(expected_post_qty), exchange_qty)

        return ExecutionResult(
            accepted=True,
            order_id=order.order_id,
            status=order.status,
            reason="ok",
            stop_loss_enforced=sl_enforced,
            reconciliation_delta=recon.delta_qty,
        )

    def _normalize_intent(self, intent: ExecutionIntent) -> ExecutionIntent:
        # Convert urgency into slippage envelope only when limit is provided.
        if intent.limit_price is None:
            return intent

        bps = self.urgency_slippage_bps.get(intent.urgency, 8.0)
        slip = intent.limit_price * (bps / 10000.0)
        if intent.side == OrderSide.BUY:
            limit = intent.limit_price + slip
        else:
            limit = max(0.0, intent.limit_price - slip)

        return ExecutionIntent(
            symbol=intent.symbol,
            side=intent.side,
            qty=intent.qty,
            order_type=intent.order_type,
            limit_price=limit,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            urgency=intent.urgency,
            client_order_id=intent.client_order_id,
            reduce_only=intent.reduce_only,
            metadata=dict(intent.metadata),
        )

    def _enforce_stop_loss(self, intent: ExecutionIntent, order: ExchangeOrder) -> bool:
        if intent.reduce_only:
            return False
        if intent.stop_loss is None:
            return False
        if order.filled_qty <= 0:
            return False

        sl_side = OrderSide.SELL if intent.side == OrderSide.BUY else OrderSide.BUY
        self.exchange.place_stop_loss(
            symbol=intent.symbol,
            side=sl_side,
            qty=float(order.filled_qty),
            stop_price=float(intent.stop_loss),
        )
        return True


__all__ = [
    "ExecutionEngineV2",
    "ReconciliationEngine",
    "ReconciliationReport",
    "ExchangeGateway",
]
