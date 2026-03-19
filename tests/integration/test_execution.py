from __future__ import annotations

from datetime import datetime, timezone

from src.core.types import Decision
from src.execution.executor import Executor
from src.execution.reconciler import reconcile_positions
from src.execution.sl_manager import StopLossManager


class _Broker:
    def __init__(self) -> None:
        self.orders: list[dict] = []
        self.stop_orders: list[dict] = []
        self.closed: list[str] = []

    def place_order(self, *, symbol: str, side: str, size: float, order_type: str, urgency: str) -> dict:
        out = {
            "order_id": "ord-1",
            "fill_price": 100.0,
            "fill_quantity": size,
            "slippage": 0.0003,
            "fees": 0.1,
            "order_type": order_type,
            "urgency": urgency,
        }
        self.orders.append(out)
        return out

    def place_stop_loss(self, *, symbol: str, side: str, size: float, stop_price: float) -> str:
        self.stop_orders.append(
            {"symbol": symbol, "side": side, "size": size, "stop_price": stop_price}
        )
        return "sl-1"

    def close_position(self, *, symbol: str, reason: str) -> None:
        self.closed.append(f"{symbol}:{reason}")


def _decision(execution_mode: str = "auto") -> Decision:
    return Decision(
        action="long",
        asset_class="crypto",
        symbol="BTCUSDT",
        execution_mode=execution_mode,
        position_size=0.05,
        leverage=1.5,
        stop_loss=0.02,
        take_profit=0.04,
        confidence=0.8,
        engine="TITAN",
        reason="integration_test",
        timestamp=datetime.now(timezone.utc),
    )


def test_execution_flow_auto_with_sl_and_reconcile() -> None:
    broker = _Broker()
    result = Executor(broker=broker).execute(decision=_decision("auto"), urgency="HIGH")
    assert result.success is True
    assert broker.orders

    sl_result = StopLossManager(broker=broker).enforce(
        symbol="BTCUSDT",
        side="long",
        size=0.05,
        stop_price=98.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert sl_result.success is True
    assert broker.stop_orders

    diffs = reconcile_positions(
        local_positions={"BTCUSDT": 0.05},
        exchange_positions={"BTCUSDT": 0.05},
    )
    assert diffs == []


def test_execution_flow_advisory() -> None:
    broker = _Broker()
    result = Executor(broker=broker).execute(decision=_decision("advisory"))
    assert result.success is True
    assert result.execution_mode == "advisory"
    assert result.advisory_message is not None
