from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.execution import (
    ExecutionEngineV2,
    ExecutionIntent,
    ExecutionRealismModel,
    ExchangeOrder,
    OrderSide,
    UrgencyLevel,
)


class DummyExchange:
    def __init__(self) -> None:
        self.position_qty = 0.0
        self.orders = []
        self.stop_orders = []

    def place_order(self, intent: ExecutionIntent) -> ExchangeOrder:
        self.orders.append(intent)
        signed = intent.qty if intent.side == OrderSide.BUY else -intent.qty
        self.position_qty += signed
        return ExchangeOrder(
            order_id="ord-1",
            status="FILLED",
            filled_qty=intent.qty,
            avg_price=float(intent.limit_price or 100.0),
            side=intent.side,
            symbol=intent.symbol,
        )

    def place_stop_loss(self, symbol: str, side: OrderSide, qty: float, stop_price: float) -> str:
        self.stop_orders.append((symbol, side, qty, stop_price))
        return "sl-1"

    def get_position_qty(self, symbol: str) -> float:
        return self.position_qty


def test_execution_v2_enforces_stop_loss_and_reconciles() -> None:
    ex = DummyExchange()
    engine = ExecutionEngineV2(ex)
    intent = ExecutionIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        qty=0.2,
        limit_price=100.0,
        stop_loss=95.0,
        urgency=UrgencyLevel.HIGH,
    )

    result = engine.execute(intent, expected_post_qty=0.2)

    assert result.accepted is True
    assert result.stop_loss_enforced is True
    assert result.reconciliation_delta == 0.0
    assert len(ex.stop_orders) == 1
    assert "lifecycle_state" in result.metadata


def test_execution_v2_reports_reconciliation_delta() -> None:
    ex = DummyExchange()
    engine = ExecutionEngineV2(ex)

    intent = ExecutionIntent(symbol="BTCUSDT", side=OrderSide.BUY, qty=1.0)
    result = engine.execute(intent, expected_post_qty=0.5)

    assert result.accepted is True
    assert result.reconciliation_delta == 0.5
    assert result.metadata.get("lifecycle_terminal") is True


def test_execution_v2_with_realism_can_return_partial() -> None:
    ex = DummyExchange()
    realism = ExecutionRealismModel(depth_caps_usd={"crypto": 50.0})
    engine = ExecutionEngineV2(ex, realism_model=realism)

    intent = ExecutionIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        qty=2.0,  # with market_price=100 => 200 notional > 50 cap
        limit_price=100.0,
        urgency=UrgencyLevel.NORMAL,
        metadata={"market_price": 100.0, "asset_class": "crypto", "regime": "RANGE", "venue_id": "sim"},
    )
    result = engine.execute(intent, expected_post_qty=0.0)

    assert result.accepted is True
    assert result.requested_qty == 2.0
    assert 0.0 < result.filled_qty <= result.requested_qty
    assert result.status in {"FILLED", "PARTIAL"}
    assert "fill_ratio" in result.metadata
