"""Tests for BingX client classes: symbol normalization, signing, order mapping."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from src.data.exchange_clients import (
    BingXPublicClient,
    BingXPrivateClient,
    _to_bingx_symbol,
    _BINGX_ORDER_TYPE_MAP,
    _BINGX_SIDE_MAP,
)


# ── Symbol normalization ─────────────────────────────────────────


def test_bingx_symbol_btcusdt():
    assert _to_bingx_symbol("BTCUSDT") == "BTC-USDT"


def test_bingx_symbol_slash():
    assert _to_bingx_symbol("BTC/USDT") == "BTC-USDT"


def test_bingx_symbol_underscore():
    assert _to_bingx_symbol("ETH_USDT") == "ETH-USDT"


def test_bingx_symbol_usdc():
    assert _to_bingx_symbol("SOLUSDC") == "SOL-USDC"


def test_bingx_symbol_busd():
    assert _to_bingx_symbol("BNBBUSD") == "BNB-BUSD"


def test_bingx_symbol_case_insensitive():
    assert _to_bingx_symbol("btcusdt") == "BTC-USDT"


# ── HMAC signing ─────────────────────────────────────────────────


def test_hmac_signing():
    """Verify HMAC-SHA256 signing matches manual computation."""
    client = BingXPrivateClient(api_key="test_key", api_secret="test_secret")
    params = {"symbol": "BTC-USDT", "side": "BUY", "quantity": "0.01"}
    sig = client._sign(params)

    # Manual verification
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    param_string = urlencode(sorted_params)
    expected = hmac.new(
        b"test_secret", param_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert sig == expected


def test_hmac_signing_deterministic():
    """Same params always produce same signature."""
    client = BingXPrivateClient(api_key="k", api_secret="s")
    params = {"a": "1", "b": "2", "c": "3"}
    sig1 = client._sign(params)
    sig2 = client._sign(params)
    assert sig1 == sig2


def test_hmac_signing_order_independent():
    """Params in different order should produce same signature (sorted internally)."""
    client = BingXPrivateClient(api_key="k", api_secret="s")
    sig1 = client._sign({"z": "1", "a": "2"})
    sig2 = client._sign({"a": "2", "z": "1"})
    assert sig1 == sig2


# ── Order type mapping ───────────────────────────────────────────


def test_order_type_market():
    assert _BINGX_ORDER_TYPE_MAP["market"] == "MARKET"


def test_order_type_emergency():
    assert _BINGX_ORDER_TYPE_MAP["EMERGENCY"] == "MARKET"


def test_order_type_limit():
    assert _BINGX_ORDER_TYPE_MAP["limit"] == "LIMIT"


def test_order_type_aggressive_limit():
    assert _BINGX_ORDER_TYPE_MAP["aggressive_limit"] == "LIMIT"


def test_order_type_passive_limit():
    assert _BINGX_ORDER_TYPE_MAP["passive_limit"] == "LIMIT"


# ── Side mapping ─────────────────────────────────────────────────


def test_side_long_to_buy():
    assert _BINGX_SIDE_MAP["long"] == "BUY"


def test_side_short_to_sell():
    assert _BINGX_SIDE_MAP["short"] == "SELL"


def test_side_buy_passthrough():
    assert _BINGX_SIDE_MAP["BUY"] == "BUY"


# ── Client initialization ───────────────────────────────────────


def test_public_client_init():
    client = BingXPublicClient(timeout=5.0)
    assert client.timeout == 5.0


def test_private_client_auth():
    client = BingXPrivateClient(api_key="k", api_secret="s")
    assert client.is_authenticated is True


def test_private_client_no_auth():
    client = BingXPrivateClient(api_key="", api_secret="")
    assert client.is_authenticated is False


def test_private_client_partial_auth():
    client = BingXPrivateClient(api_key="k", api_secret="")
    assert client.is_authenticated is False
