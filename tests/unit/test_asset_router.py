from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.asset_router import AssetRouter


@dataclass
class _DummyPosition:
    quantity: float
    side: str
    entry_price: float


class _DummyBroker:
    def __init__(self) -> None:
        self.details: Dict[str, _DummyPosition] = {}
        self.trades = []

    def execute_strategy(
        self,
        *,
        symbol: str,
        decision: str,
        direction: str,
        price: float,
        timestamp: float,
        risk_pct: float,
        leverage: float,
        custom_sl_price=None,
        custom_tp_price=None,
    ):
        if str(decision).upper() != "GO":
            return False, "decision_not_go"
        side = "BUY" if str(direction).upper() == "BUY" else "SELL"
        self.details[symbol] = _DummyPosition(quantity=max(1e-6, float(risk_pct)), side=side, entry_price=float(price))
        self.trades.append({"symbol": symbol, "side": side, "price": float(price), "ts": float(timestamp)})
        return True, "ok"


def test_router_defaults_to_crypto():
    router = AssetRouter(broker=_DummyBroker(), asset_class="crypto", venue_id="auto")
    tags = router.telemetry_tags()
    assert tags["asset_class"] == "crypto"
    assert tags["venue_id"] == "binance_spot_paper"


def test_stock_backend_is_deterministic_for_same_now():
    router = AssetRouter(broker=_DummyBroker(), asset_class="stock", venue_id="auto")
    bars_a = router.fetch_klines(symbol="AAPL", interval="1m", limit=12, now_ts=1_700_000_000.0)
    bars_b = router.fetch_klines(symbol="AAPL", interval="1m", limit=12, now_ts=1_700_000_000.0)
    assert [b.close for b in bars_a] == [b.close for b in bars_b]
    assert [b.timestamp for b in bars_a] == [b.timestamp for b in bars_b]
    tags = router.telemetry_tags()
    assert tags["asset_class"] == "stock"
    assert tags["venue_id"] == "stock_sim_paper"


def test_defi_backend_is_deterministic_for_same_now():
    router = AssetRouter(broker=_DummyBroker(), asset_class="defi", venue_id="auto")
    bars_a = router.fetch_klines(symbol="UNIUSDT", interval="1m", limit=12, now_ts=1_700_000_000.0)
    bars_b = router.fetch_klines(symbol="UNIUSDT", interval="1m", limit=12, now_ts=1_700_000_000.0)
    assert [b.close for b in bars_a] == [b.close for b in bars_b]
    assert [b.timestamp for b in bars_a] == [b.timestamp for b in bars_b]
    tags = router.telemetry_tags()
    assert tags["asset_class"] == "defi"
    assert tags["venue_id"] == "defi_sim_paper"


def test_backend_failure_does_not_raise_and_returns_empty_series():
    router = AssetRouter(broker=_DummyBroker(), asset_class="stock", venue_id="auto", allow_fallback=False)
    router._adapters["stock"].fetch_klines = lambda _req: (_ for _ in ()).throw(RuntimeError("simulated backend failure"))  # type: ignore[attr-defined]
    bars = router.fetch_klines(symbol="AAPL", interval="1m", limit=3, now_ts=1_700_000_000.0)
    assert bars == []
    assert router.route.error is not None


def test_order_and_position_interfaces_are_wired():
    broker = _DummyBroker()
    router = AssetRouter(broker=broker, asset_class="stock", venue_id="auto")
    result = router.submit_order(
        symbol="AAPL",
        decision="GO",
        direction="BUY",
        price=190.0,
        timestamp=1_700_000_000.0,
        risk_pct=0.01,
        leverage=1.0,
    )
    assert result.accepted is True
    pos = router.get_position("AAPL")
    assert pos.qty > 0.0
    assert pos.side == "BUY"
