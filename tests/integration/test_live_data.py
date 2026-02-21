"""Integration tests for real market data pipeline (Stage-2A).

Tests marked @pytest.mark.integration require internet access.
Other tests use mocks and run offline.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import os
import pytest
import requests
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Test 1: BinancePublicClient returns valid candle schema (ONLINE)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_ONLINE_TESTS") != "1",
    reason="Skipping online tests (set RUN_ONLINE_TESTS=1 to enable)",
)
def test_binance_client_fetch_returns_valid_schema():
    """Hit real Binance API and validate the returned candle schema."""
    from src.data.exchange_clients import BinancePublicClient

    client = BinancePublicClient(use_futures=True, cache_ttl=0)
    rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)

    assert len(rows) > 0, "Binance should return at least 1 candle"
    assert len(rows) <= 10, f"Requested 10, got {len(rows)}"

    for i, row in enumerate(rows):
        assert len(row) == 6, f"Row {i} should have 6 fields [ts,o,h,l,c,v], got {len(row)}"
        ts, o, h, l, c, v = row
        assert isinstance(ts, datetime), f"Row {i} timestamp should be datetime"
        assert ts.tzinfo is not None, f"Row {i} timestamp should be tz-aware"
        for val_name, val in [("open", o), ("high", h), ("low", l), ("close", c), ("volume", v)]:
            assert isinstance(val, float), f"Row {i} {val_name} should be float"
            assert val >= 0, f"Row {i} {val_name} should be non-negative"

        # Sanity: BTC price should be > $1000
        assert c > 1000, f"Row {i} BTC close={c} seems too low"


# ---------------------------------------------------------------------------
# Test 2: DataFactory delegates to exchange_client when provided (OFFLINE)
# ---------------------------------------------------------------------------

def test_data_factory_uses_exchange_client():
    """DataFactory.fetch_ohlcv should call exchange_client.fetch_ohlcv in mock mode."""
    from src.data.data_factory import DataFactory

    fake_rows = [
        [datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), 100.0, 105.0, 95.0, 102.0, 5000.0],
        [datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc), 102.0, 108.0, 100.0, 106.0, 6000.0],
    ]

    mock_client = MagicMock()
    mock_client.fetch_ohlcv.return_value = fake_rows

    factory = DataFactory(
        exchange_client=mock_client,
        mode="mock",
        evolve=False,
    )

    result = factory.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=100)

    mock_client.fetch_ohlcv.assert_called_once_with(
        symbol="BTCUSDT", timeframe="1h", limit=100,
    )
    assert result == fake_rows
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Test 3: Pipeline in live-data mode runs N cycles without crash (ONLINE)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_ONLINE_TESTS") != "1",
    reason="Skipping online tests (set RUN_ONLINE_TESTS=1 to enable)",
)
def test_paper_mode_n_cycles_without_crash(tmp_path):
    """Pipeline in live-data mode should complete 2 cycles using real market data."""
    import sqlite3
    from src.main import ArgusPipeline

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    pipeline = ArgusPipeline(
        mode="paper",
        assets=["crypto"],
        data_mode="live",
        ohlcv_limit=100,
        v25_conn=conn,
    )
    setattr(pipeline, "_primary_tf", "1h")

    all_outputs = []
    for cycle in range(2):
        outputs = pipeline.run_once()
        assert isinstance(outputs, list), f"Cycle {cycle}: run_once should return list"
        all_outputs.extend(outputs)

    # At least some outputs should be generated
    assert len(all_outputs) > 0, "Should produce at least one output over 2 cycles"

    # Each output should have required fields
    for out in all_outputs:
        assert "symbol" in out
        assert "status" in out
        assert "engine" in out

    conn.close()


# ---------------------------------------------------------------------------
# Test 4: Cache prevents duplicate API requests (OFFLINE)
# ---------------------------------------------------------------------------

def test_cache_prevents_duplicate_requests():
    """BinancePublicClient cache should serve repeated requests from memory."""
    from src.data.exchange_clients import BinancePublicClient

    client = BinancePublicClient(use_futures=True, cache_ttl=10.0)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = [
        [1700000000000, "50000.0", "50100.0", "49900.0", "50050.0", "100.0",
         1700003599999, "5000000.0", 1000, "50.0", "2500000.0", "0"],
    ]
    fake_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=fake_response) as mock_get:
        # First call: cache miss -> API call
        rows1 = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
        assert len(rows1) == 1
        assert mock_get.call_count == 1

        # Second call: cache hit -> no API call
        rows2 = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
        assert len(rows2) == 1
        assert mock_get.call_count == 1  # Still 1 — served from cache

        # Verify the cached data is identical
        assert rows1 == rows2

    # Request count should be 1 (only one actual API call)
    assert client._request_count == 1


# ---------------------------------------------------------------------------
# Bonus Test 5: Cache expires after TTL (OFFLINE)
# ---------------------------------------------------------------------------

def test_cache_expires_after_ttl():
    """After TTL expires, the next fetch should hit the API again."""
    from src.data.exchange_clients import BinancePublicClient

    client = BinancePublicClient(use_futures=True, cache_ttl=0.1)  # 100ms TTL

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = [
        [1700000000000, "50000.0", "50100.0", "49900.0", "50050.0", "100.0",
         1700003599999, "5000000.0", 1000, "50.0", "2500000.0", "0"],
    ]
    fake_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=fake_response) as mock_get:
        # First call
        client.fetch_ohlcv(symbol="ETHUSDT", timeframe="5m", limit=5)
        assert mock_get.call_count == 1

        # Wait for TTL to expire
        time.sleep(0.15)

        # Second call: cache expired -> API call
        client.fetch_ohlcv(symbol="ETHUSDT", timeframe="5m", limit=5)
        assert mock_get.call_count == 2


def test_live_data_path_uses_exchange_client_and_cache_for_multiple_symbols(tmp_path):
    """Offline integration: 5-symbol live-data path should use client cache across cycles."""
    import sqlite3

    from src.data.exchange_clients import BinancePublicClient
    from src.main import ArgusPipeline

    db_path = tmp_path / "v25_live_multi.db"
    conn = sqlite3.connect(str(db_path))

    payload = []
    start_ms = 1700000000000
    for i in range(400):
        t = start_ms + i * 60_000
        close = 50000 + i
        payload.append([
            t,
            f"{close - 5}",
            f"{close + 10}",
            f"{close - 20}",
            f"{close}",
            "100.0",
            t + 59_999,
        ])

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = payload

    client = BinancePublicClient(use_futures=True, cache_ttl=600.0)
    client.MIN_REQUEST_INTERVAL = 0.0

    with patch.object(client._session, "get", return_value=fake_response) as mock_get:
        with patch.object(ArgusPipeline, "_init_exchange_client", staticmethod(lambda evolve: client)):
            pipeline = ArgusPipeline(
                mode="paper",
                assets=["crypto"],
                data_mode="live",
                ohlcv_limit=260,
                v25_conn=conn,
                symbols_override={"crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]},
            )
            setattr(pipeline, "_primary_tf", "1h")

            out1 = pipeline.run_once(now=datetime.now(timezone.utc))
            out2 = pipeline.run_once(now=datetime.now(timezone.utc) + timedelta(minutes=1))

    # 5 symbols x first cycle requests; second cycle should hit cache
    assert mock_get.call_count == 5
    assert len(out1) == 5
    assert len(out2) == 5
    conn.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_ONLINE_TESTS") != "1",
    reason="Skipping online tests (set RUN_ONLINE_TESTS=1 to enable)",
)
def test_binance_live_data_multi_symbol_smoke():
    """Gentle online smoke over two symbols."""
    from src.data.exchange_clients import BinancePublicClient

    client = BinancePublicClient(use_futures=True, cache_ttl=0.0, max_retries=2)
    symbols = ["BTCUSDT", "ETHUSDT"]
    for sym in symbols:
        rows = client.fetch_ohlcv(symbol=sym, timeframe="1h", limit=5)
        assert rows, f"Expected non-empty rows for {sym}"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_ONLINE_TESTS") != "1",
    reason="Skipping online tests (set RUN_ONLINE_TESTS=1 to enable)",
)
def test_binance_live_data_handles_disconnect_gracefully():
    """Graceful handling of disconnect/retry path (simulated)."""
    from src.data.exchange_clients import BinancePublicClient

    client = BinancePublicClient(
        use_futures=True,
        cache_ttl=0.0,
        max_retries=2,
        breaker_failures=3,
        breaker_cooldown_seconds=1.0,
    )
    client.MIN_REQUEST_INTERVAL = 0.0

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = [
        [1700000000000, "50000.0", "50100.0", "49900.0", "50050.0", "100.0", 1700003599999],
    ]

    calls = {"n": 0}

    def _flaky_get(*args, **kwargs):
        _ = args, kwargs
        if calls["n"] == 0:
            calls["n"] += 1
            raise requests.exceptions.ConnectionError("RemoteDisconnected")
        return fake_response

    with patch.object(client._session, "get", side_effect=_flaky_get):
        rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=2)

    assert rows, "Client should recover and return data after retry"
