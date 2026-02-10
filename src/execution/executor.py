"""Execution layer with auto/advisory dual-mode behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.core.types import Decision, ExecutionResult


class BrokerAdapter(Protocol):
    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        size: float,
        order_type: str,
        urgency: str,
    ) -> dict[str, Any]:
        ...


@dataclass
class Executor:
    broker: BrokerAdapter

    def execute(self, *, decision: Decision, urgency: str = "NORMAL") -> ExecutionResult:
        if decision.execution_mode == "advisory":
            return ExecutionResult(
                success=True,
                execution_mode="advisory",
                advisory_message=self._format_advisory(decision),
                reason="advisory_signal_sent",
                timestamp=decision.timestamp,
            )

        order_type = self._order_type(urgency, decision.confidence)
        try:
            order = self.broker.place_order(
                symbol=decision.symbol,
                side=decision.action,
                size=decision.position_size,
                order_type=order_type,
                urgency=urgency,
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                execution_mode="auto",
                reason=f"execution_failed:{exc}",
                timestamp=decision.timestamp,
            )

        return ExecutionResult(
            success=True,
            execution_mode="auto",
            order_id=str(order.get("order_id", "")),
            fill_price=float(order.get("fill_price", 0.0)) if order.get("fill_price") is not None else None,
            fill_quantity=float(order.get("fill_quantity", 0.0)) if order.get("fill_quantity") is not None else None,
            slippage=float(order.get("slippage", 0.0)) if order.get("slippage") is not None else None,
            fees=float(order.get("fees", 0.0)) if order.get("fees") is not None else None,
            reason="order_filled",
            timestamp=decision.timestamp,
        )

    def _order_type(self, urgency: str, confidence: float) -> str:
        if urgency == "EMERGENCY":
            return "market"
        if urgency == "HIGH" or confidence > 0.8:
            return "aggressive_limit"
        if urgency == "LOW":
            return "passive_limit"
        return "limit"

    def _format_advisory(self, decision: Decision) -> str:
        tp = ", ".join([f"{x:.4f}" for x in (decision.tp_levels or [])]) or f"{decision.take_profit:.4f}"
        suggested_zone = getattr(decision, "suggested_entry_zone", None)
        if suggested_zone:
            zone = f"{suggested_zone[0]:.4f}-{suggested_zone[1]:.4f}"
        elif decision.suggested_entry_price is not None:
            zone = f"{decision.suggested_entry_price:.4f}"
        else:
            zone = "n/a"
        return (
            f"[ADVISORY] {decision.symbol} {decision.action.upper()} "
            f"size={decision.position_size:.4f} SL={decision.stop_loss:.4f} TP={tp} "
            f"entry_zone={zone} conf={decision.confidence:.2f} reason={decision.reason}"
        )
