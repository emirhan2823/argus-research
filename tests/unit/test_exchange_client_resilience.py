from __future__ import annotations

from http.client import RemoteDisconnected
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

from src.data.exchange_clients import BinancePublicClient


def _fake_kline_payload() -> list[list[object]]:
    return [
        [1700000000000, "50000.0", "50100.0", "49900.0", "50050.0", "100.0", 1700003599999],
        [1700003600000, "50050.0", "50200.0", "50000.0", "50150.0", "120.0", 1700007199999],
    ]


def test_backoff_and_circuit_breaker_behavior() -> None:
    # Backoff timing check
    client = BinancePublicClient(
        use_futures=True,
        max_retries=3,
        cache_ttl=0.0,
        breaker_failures=99,
        breaker_cooldown_seconds=60.0,
    )
    client.MIN_REQUEST_INTERVAL = 0.0

    sleep_calls: list[float] = []

    with patch.object(client, "_refresh_session", return_value=None):
        with patch.object(client._session, "get", side_effect=requests.exceptions.ConnectionError("boom")):
            with patch("src.data.exchange_clients.random.uniform", return_value=0.0):
                with patch("src.data.exchange_clients.time.sleep", side_effect=lambda s: sleep_calls.append(float(s))):
                    rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
                    assert rows == []

    assert sleep_calls == [2.0, 4.0]

    # Circuit breaker open check
    breaker_client = BinancePublicClient(
        use_futures=True,
        max_retries=1,
        cache_ttl=0.0,
        breaker_failures=5,
        breaker_cooldown_seconds=60.0,
    )
    breaker_client.MIN_REQUEST_INTERVAL = 0.0

    with patch.object(breaker_client, "_refresh_session", return_value=None):
        with patch.object(breaker_client._session, "get", side_effect=requests.exceptions.ConnectionError("disconnect")) as mock_get:
            for _ in range(5):
                assert breaker_client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10) == []

            before = mock_get.call_count
            assert breaker_client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10) == []
            assert mock_get.call_count == before
            assert breaker_client._breaker_open_until > time.monotonic()


def test_session_refresh_after_idle(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[list[object]]:
            return _fake_kline_payload()

    sessions: list["FakeSession"] = []

    class FakeSession:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            sessions.append(self)

        def get(self, *args, **kwargs):
            _ = args, kwargs
            return FakeResponse()

        def close(self) -> None:
            return None

    monkeypatch.setattr("src.data.exchange_clients.requests.Session", FakeSession)

    client = BinancePublicClient(
        use_futures=True,
        max_retries=1,
        cache_ttl=0.0,
        idle_refresh_seconds=180.0,
    )
    client.MIN_REQUEST_INTERVAL = 0.0

    rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
    assert len(rows) == 2
    first_session = client._session

    client._last_activity_time = time.monotonic() - 181.0
    rows2 = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
    assert len(rows2) == 2
    assert client._session is not first_session
    assert len(sessions) >= 2


def test_remote_disconnected_triggers_breaker_and_recovers() -> None:
    client = BinancePublicClient(
        use_futures=True,
        max_retries=1,
        cache_ttl=0.0,
        breaker_failures=2,
        breaker_cooldown_seconds=60.0,
    )
    client.MIN_REQUEST_INTERVAL = 0.0

    ok_response = MagicMock()
    ok_response.raise_for_status.return_value = None
    ok_response.json.return_value = _fake_kline_payload()

    with patch.object(client, "_refresh_session", return_value=None):
        with patch.object(client._session, "get", side_effect=RemoteDisconnected("peer closed")):
            assert client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10) == []
            assert client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10) == []

    assert client._breaker_open_until > time.monotonic()

    with patch.object(client._session, "get", return_value=ok_response) as mock_get:
        assert client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10) == []
        assert mock_get.call_count == 0

    client._breaker_open_until = time.monotonic() - 0.01
    with patch.object(client._session, "get", return_value=ok_response) as mock_get:
        rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
        assert len(rows) == 2
        assert mock_get.call_count == 1

    assert client._consecutive_failures == 0


def test_cache_is_served_while_breaker_open() -> None:
    client = BinancePublicClient(
        use_futures=True,
        max_retries=1,
        cache_ttl=600.0,
        breaker_failures=2,
        breaker_cooldown_seconds=60.0,
    )
    client.MIN_REQUEST_INTERVAL = 0.0

    ok_response = MagicMock()
    ok_response.raise_for_status.return_value = None
    ok_response.json.return_value = _fake_kline_payload()

    with patch.object(client._session, "get", return_value=ok_response) as mock_get:
        cached_rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)
        assert len(cached_rows) == 2
        assert mock_get.call_count == 1

    client._consecutive_failures = 5
    client._breaker_open_until = time.monotonic() + 30.0

    with patch.object(client._session, "get", side_effect=AssertionError("http should not be called")):
        rows = client.fetch_ohlcv(symbol="BTCUSDT", timeframe="1h", limit=10)

    assert rows == cached_rows
