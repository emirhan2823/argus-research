import asyncio
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.exchanges import BinanceAdapter, BybitAdapter, OKXAdapter


class _DummyClient:
    async def get(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("network access is disabled in unit tests")

    async def post(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("network access is disabled in unit tests")

    async def aclose(self):
        return None


def _run(coro):
    return asyncio.run(coro)


def test_binance_ticker_balance_positions_and_market_order(monkeypatch):
    adapter = BinanceAdapter("k", "s", client=_DummyClient())

    async def fake_request(method, path, params=None, signed=False):
        if path == "/fapi/v1/ticker/24hr":
            return {
                "symbol": "BTCUSDT",
                "bidPrice": "50000",
                "askPrice": "50010",
                "lastPrice": "50005",
                "volume": "1234",
            }
        if path == "/fapi/v2/balance":
            return [{"asset": "USDT", "availableBalance": "345.67"}]
        if path == "/fapi/v2/account":
            return {"positions": [{"symbol": "BTCUSDT", "positionAmt": "0.05"}]}
        if path == "/fapi/v1/order":
            return {
                "orderId": 101,
                "avgPrice": "50007",
                "executedQty": "0.05",
                "commission": "0.11",
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(adapter, "_request", fake_request)

    ticker = _run(adapter.get_ticker("BTCUSDT"))
    assert ticker.symbol == "BTCUSDT"
    assert ticker.bid == 50000.0
    assert ticker.ask == 50010.0
    assert ticker.last == 50005.0
    assert ticker.volume_24h == 1234.0

    balance = _run(adapter.get_balance("USDT"))
    assert balance == 345.67

    positions = _run(adapter.get_positions())
    assert positions == {"BTCUSDT": 0.05}

    close_fill = _run(adapter.close_position("BTCUSDT"))
    assert close_fill.order_id == "101"
    assert close_fill.side == "SELL"
    assert close_fill.quantity == 0.05


def test_binance_close_position_when_flat(monkeypatch):
    adapter = BinanceAdapter("k", "s", client=_DummyClient())

    async def fake_positions():
        return {"ETHUSDT": 0.1}

    monkeypatch.setattr(adapter, "get_positions", fake_positions)

    out = _run(adapter.close_position("BTCUSDT"))
    assert out.order_id == "NO_POSITION"
    assert out.side == "FLAT"
    assert out.quantity == 0.0


def test_bybit_ticker_balance_positions_and_close(monkeypatch):
    adapter = BybitAdapter("k", "s", client=_DummyClient())

    async def fake_request(method, path, params=None, signed=False):
        if path == "/v5/market/tickers":
            return {
                "result": {
                    "list": [
                        {
                            "symbol": "ETHUSDT",
                            "bid1Price": "2600",
                            "ask1Price": "2601",
                            "lastPrice": "2600.5",
                            "volume24h": "99999",
                        }
                    ]
                }
            }
        if path == "/v5/account/wallet-balance":
            return {
                "result": {
                    "list": [
                        {
                            "coin": [
                                {
                                    "coin": "USDT",
                                    "availableToWithdraw": "120.5",
                                }
                            ]
                        }
                    ]
                }
            }
        if path == "/v5/position/list":
            return {
                "result": {
                    "list": [
                        {"symbol": "ETHUSDT", "size": "0.2", "side": "Sell"}
                    ]
                }
            }
        if path == "/v5/order/create":
            assert params["side"] == "Buy"
            return {"result": {"orderId": "byb-55"}}
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(adapter, "_request", fake_request)

    ticker = _run(adapter.get_ticker("ETHUSDT"))
    assert ticker.last == 2600.5

    balance = _run(adapter.get_balance("USDT"))
    assert balance == 120.5

    positions = _run(adapter.get_positions())
    assert positions == {"ETHUSDT": -0.2}

    close_fill = _run(adapter.close_position("ETHUSDT"))
    assert close_fill.side == "BUY"
    assert close_fill.order_id == "byb-55"
    assert close_fill.quantity == 0.2


def test_bybit_close_position_when_flat(monkeypatch):
    adapter = BybitAdapter("k", "s", client=_DummyClient())

    async def fake_positions():
        return {}

    monkeypatch.setattr(adapter, "get_positions", fake_positions)

    out = _run(adapter.close_position("ETHUSDT"))
    assert out.order_id == "NO_POSITION"
    assert out.quantity == 0.0


def test_okx_ticker_balance_positions_and_close(monkeypatch):
    adapter = OKXAdapter("k", "s", "p", client=_DummyClient())

    async def fake_request(method, path, params=None, signed=False):
        if path == "/api/v5/market/ticker":
            return {
                "data": [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "bidPx": "50000",
                        "askPx": "50005",
                        "last": "50002",
                        "vol24h": "777777",
                    }
                ]
            }
        if path == "/api/v5/account/balance":
            return {
                "data": [
                    {
                        "details": [
                            {"ccy": "USDT", "availEq": "88.8"},
                        ]
                    }
                ]
            }
        if path == "/api/v5/account/positions":
            return {
                "data": [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "pos": "1.5",
                        "posSide": "long",
                    }
                ]
            }
        if path == "/api/v5/trade/order":
            assert params["side"] == "sell"
            return {
                "data": [
                    {
                        "ordId": "okx-9",
                        "fillPx": "50001",
                        "fillSz": "1.5",
                        "fee": "0.2",
                    }
                ]
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(adapter, "_request", fake_request)

    ticker = _run(adapter.get_ticker("BTC-USDT-SWAP"))
    assert ticker.bid == 50000.0
    assert ticker.ask == 50005.0

    balance = _run(adapter.get_balance("USDT"))
    assert balance == 88.8

    positions = _run(adapter.get_positions())
    assert positions == {"BTC-USDT-SWAP": 1.5}

    close_fill = _run(adapter.close_position("BTC-USDT-SWAP"))
    assert close_fill.side == "SELL"
    assert close_fill.order_id == "okx-9"


def test_okx_close_position_when_flat(monkeypatch):
    adapter = OKXAdapter("k", "s", "p", client=_DummyClient())

    async def fake_positions():
        return {"ETH-USDT-SWAP": -2.0}

    monkeypatch.setattr(adapter, "get_positions", fake_positions)

    out = _run(adapter.close_position("BTC-USDT-SWAP"))
    assert out.order_id == "NO_POSITION"
    assert out.side == "FLAT"
