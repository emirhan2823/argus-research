from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.broker.live import LiveBroker, LiveConfig, OrderRequest, OrderSide, OrderType


class _FakeResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self):
        self.last = None
        self.account_payload = {
            "assets": [{"asset": "USDT", "availableBalance": "123.45"}],
            "positions": [{"symbol": "BTCUSDT", "positionAmt": "0.01"}],
        }
        self.order_payload = {
            "orderId": 99,
            "avgPrice": "50010",
            "executedQty": "0.01",
            "commission": "0.20",
        }

    def get(self, url, params=None, headers=None):
        self.last = ("GET", url, params, headers)
        return _FakeResponse(self.account_payload)

    def post(self, url, params=None, headers=None):
        self.last = ("POST", url, params, headers)
        return _FakeResponse(self.order_payload)


def _broker(**kwargs):
    cfg = LiveConfig(api_key="k", api_secret="s", require_confirmation=False, **kwargs)
    return LiveBroker(cfg, client=_FakeClient())


def test_safety_limits_block_oversized_orders():
    broker = _broker(max_order_value=50.0)
    res = broker.execute(
        OrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, quantity=0.01),
        current_price=10000,
    )
    assert res.success is False
    assert "exceeds max" in res.error


def test_confirmation_prompt_cancels(monkeypatch):
    cfg = LiveConfig(api_key="k", api_secret="s", require_confirmation=True)
    broker = LiveBroker(cfg, client=_FakeClient())

    monkeypatch.setattr("builtins.input", lambda _: "NO")

    res = broker.execute(
        OrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, quantity=0.001),
        current_price=1000,
    )
    assert res.success is False
    assert res.error == "User cancelled"


def test_daily_volume_tracking_updates_on_success():
    broker = _broker(max_order_value=1000.0, max_daily_volume=2000.0)
    res = broker.execute(
        OrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, quantity=0.01),
        current_price=50000,
    )
    assert res.success is True
    assert abs(broker.daily_volume - 500.0) < 1e-9
    assert len(broker.orders_today) == 1


def test_position_close_works():
    broker = _broker(max_order_value=1000.0)
    out = broker.close_position("BTCUSDT", current_price=50000)
    assert out.success is True
    method, _, params, _ = broker._client.last
    assert method == "POST"
    assert params["reduceOnly"] == "true"


def test_error_handling_robust(monkeypatch):
    broker = _broker(max_order_value=1000.0)

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(broker, "_request", boom)

    res = broker.execute(
        OrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, quantity=0.01),
        current_price=1000,
    )
    assert res.success is False
    assert "network down" in (res.error or "")


def test_testnet_orders_use_testnet_url():
    cfg = LiveConfig(api_key="k", api_secret="s", testnet=True, require_confirmation=False)
    broker = LiveBroker(cfg, client=_FakeClient())
    _ = broker.get_balance()
    assert "testnet.binancefuture.com" in broker._client.last[1]


def test_get_positions_and_balance_parsing():
    broker = _broker()
    balance = broker.get_balance()
    positions = broker.get_positions()
    assert abs(balance - 123.45) < 1e-9
    assert positions["BTCUSDT"] == 0.01
