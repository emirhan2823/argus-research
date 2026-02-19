"""Execution layer with auto/advisory dual-mode behavior.

Extended by PR-J02 with:
  - ``execute_with_precision`` — uses hyper-precision entry to pick order type.
  - ``execute_partial_close`` — partial position close via hyper-precision exit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from src.core.types import Decision, ExecutionResult
from src.execution.hyper_precision import (
    PrecisionEntryResult,
    PrecisionExitResult,
    snipe_entry,
    snipe_partial_exit,
)

_LOG = logging.getLogger(__name__)


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

    # ------------------------------------------------------------------
    # PR-J02: Hyper-precision entry integration
    # ------------------------------------------------------------------

    def execute_with_precision(
        self,
        *,
        decision: Decision,
        urgency: str = "NORMAL",
        obi: float | None = None,
        vwap_dev_pct: float = 0.0,
        spread_pct: float = 0.001,
        median_spread_pct: float = 0.001,
        atr_pct: float = 0.01,
    ) -> tuple[ExecutionResult, PrecisionEntryResult]:
        """Execute a trade using hyper-precision entry to pick order type.

        If hyper-precision returns "skip", the trade is NOT placed and an
        advisory-like result is returned.  Otherwise the precision-computed
        order type and price are forwarded to the broker.

        Returns ``(execution_result, precision_result)`` so the caller can
        log precision metadata.
        """
        if decision.execution_mode == "advisory":
            pr = PrecisionEntryResult(
                order_type="skip", price=None, timeout_bars=0, reason="advisory_mode"
            )
            return self.execute(decision=decision, urgency=urgency), pr

        direction = "LONG" if decision.action in ("long", "LONG") else "SHORT"
        current_price = decision.suggested_entry_price or 0.0

        pr = snipe_entry(
            direction=direction,
            target_price=current_price,
            current_price=current_price,
            obi=obi,
            vwap_dev_pct=vwap_dev_pct,
            spread_pct=spread_pct,
            median_spread_pct=median_spread_pct,
            atr_pct=atr_pct,
            urgency=urgency,
        )

        if pr.order_type == "skip":
            _LOG.info("precision_skip symbol=%s reason=%s", decision.symbol, pr.reason)
            return ExecutionResult(
                success=False,
                execution_mode="auto",
                reason=f"precision_skip:{pr.reason}",
                timestamp=decision.timestamp,
            ), pr

        order_type = pr.order_type  # "limit" or "market"
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
            ), pr

        return ExecutionResult(
            success=True,
            execution_mode="auto",
            order_id=str(order.get("order_id", "")),
            fill_price=float(order.get("fill_price", 0.0)) if order.get("fill_price") is not None else None,
            fill_quantity=float(order.get("fill_quantity", 0.0)) if order.get("fill_quantity") is not None else None,
            slippage=float(order.get("slippage", 0.0)) if order.get("slippage") is not None else None,
            fees=float(order.get("fees", 0.0)) if order.get("fees") is not None else None,
            reason="order_filled_with_precision",
            timestamp=decision.timestamp,
        ), pr

    # ------------------------------------------------------------------
    # PR-J02: Partial close via hyper-precision exit
    # ------------------------------------------------------------------

    def execute_partial_close(
        self,
        *,
        symbol: str,
        direction: str,
        pct_to_close: float,
        current_price: float,
        obi: float | None = None,
        vwap_dev_pct: float = 0.0,
        spread_pct: float = 0.001,
        median_spread_pct: float = 0.001,
        urgency: str = "NORMAL",
        total_quantity: float = 0.0,
    ) -> tuple[ExecutionResult | None, PrecisionExitResult]:
        """Execute a partial position close using hyper-precision exit.

        Returns ``(execution_result, precision_exit_result)``.
        ``execution_result`` is ``None`` if the broker call is skipped
        (e.g. when total_quantity is zero).
        """
        from datetime import datetime, timezone

        pr = snipe_partial_exit(
            direction=direction,
            pct_to_close=pct_to_close,
            current_price=current_price,
            obi=obi,
            vwap_dev_pct=vwap_dev_pct,
            spread_pct=spread_pct,
            median_spread_pct=median_spread_pct,
            urgency=urgency,
        )

        close_qty = total_quantity * pct_to_close
        if close_qty <= 0:
            return None, pr

        side = "short" if direction == "LONG" else "long"  # closing side
        try:
            order = self.broker.place_order(
                symbol=symbol,
                side=side,
                size=close_qty,
                order_type=pr.order_type,
                urgency=urgency,
            )
        except Exception as exc:
            now = datetime.now(timezone.utc)
            return ExecutionResult(
                success=False,
                execution_mode="auto",
                reason=f"partial_close_failed:{exc}",
                timestamp=now,
            ), pr

        now = datetime.now(timezone.utc)
        return ExecutionResult(
            success=True,
            execution_mode="auto",
            order_id=str(order.get("order_id", "")),
            fill_price=float(order.get("fill_price", 0.0)) if order.get("fill_price") is not None else None,
            fill_quantity=float(order.get("fill_quantity", 0.0)) if order.get("fill_quantity") is not None else None,
            reason="partial_close_filled",
            timestamp=now,
        ), pr
