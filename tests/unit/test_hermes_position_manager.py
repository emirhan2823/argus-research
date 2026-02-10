from __future__ import annotations

from src.execution.hermes_position_manager import HermesPositionManager


class _Broker:
    def __init__(self) -> None:
        self.closed: list[str] = []
        self.sl: list[tuple[str, float]] = []
        self.tp: list[tuple[str, float]] = []

    def close_position(self, *, symbol: str, reason: str) -> None:
        self.closed.append(f"{symbol}:{reason}")

    def modify_stop_loss(self, *, symbol: str, stop_price: float) -> None:
        self.sl.append((symbol, stop_price))

    def modify_take_profit(self, *, symbol: str, tp_price: float) -> None:
        self.tp.append((symbol, tp_price))


def test_hermes_position_manager_auto_actions() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)

    r1 = pm.handle(symbol="BTCUSDT", action="CLOSE_POSITION", execution_mode="auto")
    r2 = pm.handle(symbol="BTCUSDT", action="ADJUST_SL", execution_mode="auto", value=98000.0)
    r3 = pm.handle(symbol="BTCUSDT", action="ADJUST_TP", execution_mode="auto", value=105000.0)

    assert r1.handled and r2.handled and r3.handled
    assert broker.closed
    assert broker.sl == [("BTCUSDT", 98000.0)]
    assert broker.tp == [("BTCUSDT", 105000.0)]


def test_hermes_position_manager_advisory_mode() -> None:
    broker = _Broker()
    pm = HermesPositionManager(broker=broker)
    out = pm.handle(symbol="THYAO", action="CLOSE_POSITION", execution_mode="advisory", value=None)
    assert out.handled is True
    assert out.advisory_message is not None
