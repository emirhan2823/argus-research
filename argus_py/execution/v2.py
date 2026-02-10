from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Dict, Optional, Protocol

from .models import ExecutionIntent, ExecutionResult, ExchangeOrder, OrderSide, UrgencyLevel
from .order_lifecycle import OrderLifecycleStateMachine
from .realism import ExecutionRealismModel, RealismContext


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
        realism_model: Optional[ExecutionRealismModel] = None,
        lifecycle_machine: Optional[OrderLifecycleStateMachine] = None,
    ) -> None:
        self.exchange = exchange
        self.reconciliation = reconciliation or ReconciliationEngine()
        self.urgency_slippage_bps = urgency_slippage_bps or {
            UrgencyLevel.LOW: 3.0,
            UrgencyLevel.NORMAL: 8.0,
            UrgencyLevel.HIGH: 16.0,
            UrgencyLevel.CRITICAL: 28.0,
        }
        self.realism_model = realism_model
        self.lifecycle_machine = lifecycle_machine or OrderLifecycleStateMachine()

    def execute(self, intent: ExecutionIntent, expected_post_qty: float) -> ExecutionResult:
        local_order_id = str(intent.client_order_id or f"local_{uuid.uuid4().hex[:10]}")
        lifecycle = self.lifecycle_machine.ensure(local_order_id, intent.symbol, float(intent.qty))
        if intent.qty <= 0:
            lifecycle = self.lifecycle_machine.transition(
                local_order_id,
                exchange_status="REJECTED",
                filled_qty=0.0,
                avg_price=0.0,
                reason="qty must be > 0",
            )
            return ExecutionResult(
                accepted=False,
                order_id=None,
                status="REJECTED",
                reason="qty must be > 0",
                stop_loss_enforced=False,
                reconciliation_delta=0.0,
                requested_qty=float(intent.qty),
                filled_qty=0.0,
                avg_price=0.0,
                metadata={
                    "lifecycle_state": lifecycle.state.value,
                    "lifecycle_terminal": self.lifecycle_machine.is_terminal(lifecycle.state),
                    "lifecycle_events": len(lifecycle.events),
                },
            )

        normalized = self._normalize_intent(intent)
        placed_intent = normalized
        realism_meta: Dict[str, object] = {}
        status_hint = None
        if self.realism_model is not None:
            plan = self.realism_model.plan(self._build_realism_context(normalized))
            realism_meta = {
                "fill_ratio": float(plan.fill_ratio),
                "slippage_bps": float(plan.slippage_bps),
                "latency_ms": int(plan.latency_ms),
                "depth_cap_notional": float(plan.depth_cap_notional),
                "realism_reason": str(plan.reason),
                "status_hint": str(plan.status_hint),
            }
            status_hint = plan.status_hint
            if plan.adjusted_qty <= 0.0:
                lifecycle = self.lifecycle_machine.transition(
                    local_order_id,
                    exchange_status="REJECTED",
                    filled_qty=0.0,
                    avg_price=float(intent.limit_price or 0.0),
                    reason="liquidity too thin",
                )
                realism_meta["lifecycle_state"] = lifecycle.state.value
                realism_meta["lifecycle_terminal"] = self.lifecycle_machine.is_terminal(lifecycle.state)
                realism_meta["lifecycle_events"] = len(lifecycle.events)
                return ExecutionResult(
                    accepted=False,
                    order_id=None,
                    status="REJECTED",
                    reason="liquidity too thin",
                    stop_loss_enforced=False,
                    reconciliation_delta=0.0,
                    requested_qty=float(intent.qty),
                    filled_qty=0.0,
                    avg_price=float(intent.limit_price or 0.0),
                    metadata=realism_meta,
                )
            meta = dict(normalized.metadata)
            meta["market_price"] = float(plan.adjusted_price)
            meta["realism"] = dict(realism_meta)
            placed_intent = ExecutionIntent(
                symbol=normalized.symbol,
                side=normalized.side,
                qty=float(plan.adjusted_qty),
                order_type=normalized.order_type,
                limit_price=float(plan.adjusted_price),
                stop_loss=normalized.stop_loss,
                take_profit=normalized.take_profit,
                urgency=normalized.urgency,
                client_order_id=normalized.client_order_id,
                reduce_only=normalized.reduce_only,
                metadata=meta,
            )

        order = self.exchange.place_order(placed_intent)
        lifecycle_id = str(order.order_id or local_order_id)
        if lifecycle_id != local_order_id:
            self.lifecycle_machine.ensure(lifecycle_id, intent.symbol, float(intent.qty))
        lifecycle = self.lifecycle_machine.transition(
            lifecycle_id,
            exchange_status=str(order.status),
            filled_qty=float(order.filled_qty),
            avg_price=float(order.avg_price),
            reason="exchange_ack",
        )
        realism_meta["lifecycle_state"] = lifecycle.state.value
        realism_meta["lifecycle_terminal"] = self.lifecycle_machine.is_terminal(lifecycle.state)
        realism_meta["lifecycle_events"] = len(lifecycle.events)
        if order.status.upper() not in {"FILLED", "PARTIAL", "ACCEPTED"}:
            return ExecutionResult(
                accepted=False,
                order_id=order.order_id,
                status=order.status,
                reason="exchange rejected order",
                stop_loss_enforced=False,
                reconciliation_delta=0.0,
                requested_qty=float(intent.qty),
                filled_qty=float(order.filled_qty),
                avg_price=float(order.avg_price),
                metadata=realism_meta,
            )

        sl_enforced = self._enforce_stop_loss(placed_intent, order)
        exchange_qty = float(self.exchange.get_position_qty(intent.symbol))
        recon = self.reconciliation.compare(intent.symbol, float(expected_post_qty), exchange_qty)
        status = str(order.status)
        if status_hint == "PARTIAL" and status.upper() == "FILLED":
            status = "PARTIAL"

        return ExecutionResult(
            accepted=True,
            order_id=order.order_id,
            status=status,
            reason="ok",
            stop_loss_enforced=sl_enforced,
            reconciliation_delta=recon.delta_qty,
            requested_qty=float(intent.qty),
            filled_qty=float(order.filled_qty),
            avg_price=float(order.avg_price),
            metadata=realism_meta,
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
        metadata = dict(intent.metadata)
        if "market_price" in metadata:
            try:
                metadata["market_price"] = float(limit)
            except Exception:
                pass

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
            metadata=metadata,
        )

    def _build_realism_context(self, intent: ExecutionIntent) -> RealismContext:
        metadata = dict(intent.metadata or {})
        regime = str(metadata.get("regime", "RANGE"))
        asset_class = str(metadata.get("asset_class", "crypto"))
        venue_id = str(metadata.get("venue_id", "auto"))
        market_price = float(metadata.get("market_price") or intent.limit_price or 0.0)
        return RealismContext(
            symbol=intent.symbol,
            asset_class=asset_class,
            venue_id=venue_id,
            side=intent.side,
            urgency=intent.urgency,
            regime=regime,
            market_price=market_price,
            requested_qty=float(intent.qty),
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
