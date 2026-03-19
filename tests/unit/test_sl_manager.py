from __future__ import annotations

from datetime import datetime, timezone

from src.execution.sl_manager import StopLossManager


class _Broker:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.closed: list[str] = []
        self.stop_orders: list[tuple[str, str, float, float]] = []

    def place_stop_loss(self, *, symbol: str, side: str, size: float, stop_price: float) -> str:
        if self.fail:
            raise RuntimeError("place_stop_failed")
        self.stop_orders.append((symbol, side, size, stop_price))
        return "sl-1"

    def close_position(self, *, symbol: str, reason: str) -> None:
        self.closed.append(f"{symbol}:{reason}")


def test_sl_manager_success() -> None:
    broker = _Broker(fail=False)
    out = StopLossManager(broker=broker).enforce(
        symbol="BTCUSDT",
        side="long",
        size=0.1,
        stop_price=99000.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert out.success is True
    assert out.sl_order_id == "sl-1"
    assert len(broker.stop_orders) == 1


def test_sl_manager_failure_closes_position() -> None:
    broker = _Broker(fail=True)
    out = StopLossManager(broker=broker).enforce(
        symbol="BTCUSDT",
        side="long",
        size=0.1,
        stop_price=99000.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert out.success is False
    assert broker.closed
