from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
import requests

import Scripts.backfill as backfill
from Scripts.providers.base import INTERVAL_MS, OHLCVRow
from Scripts.providers.binance_provider import BinanceProvider
from Scripts.providers.bybit_provider import BybitProvider
from Scripts.providers.kraken_provider import KrakenProvider
from Scripts.providers.okx_provider import OkxProvider


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: object, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400 and self.status_code not in (418, 429):
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self) -> object:
        return self._payload


def test_binance_provider_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = BinanceProvider(rate_limit_sleep=0.0)
    payload = [
        [
            1704067200000,
            "100",
            "110",
            "90",
            "105",
            "10",
            1704070799999,
            "1000",
            "33",
            "5",
            "500",
        ]
    ]
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: _FakeResponse(status_code=200, payload=payload),
    )
    rows = provider.fetch_ohlcv(
        symbol="BTCUSDT",
        timeframe="1h",
        start_ts=1704067200000,
        end_ts=1704070800000,
        limit=1000,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.timestamp_ms == 1704067200000
    assert row.open == 100.0
    assert row.close == 105.0
    assert row.num_trades == 33


def test_okx_provider_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OkxProvider(rate_limit_sleep=0.0)
    payload = {
        "code": "0",
        "data": [
            ["1704067200000", "100", "110", "90", "105", "10", "10", "1000", "1"],
        ],
    }
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: _FakeResponse(status_code=200, payload=payload),
    )
    rows = provider.fetch_ohlcv(
        symbol="BTCUSDT",
        timeframe="1h",
        start_ts=1704067200000,
        end_ts=1704070800000,
        limit=100,
    )
    assert len(rows) == 1
    assert rows[0].timestamp_ms == 1704067200000
    assert rows[0].quote_volume == 1000.0


def test_kraken_provider_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = KrakenProvider(rate_limit_sleep=0.0)
    payload = {
        "error": [],
        "result": {
            "XBTUSDT": [
                [1704067200, "100", "110", "90", "105", "103", "10", "20"],
            ],
            "last": 1704067200,
        },
    }
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: _FakeResponse(status_code=200, payload=payload),
    )
    rows = provider.fetch_ohlcv(
        symbol="BTCUSDT",
        timeframe="1h",
        start_ts=1704067200000,
        end_ts=1704070800000,
        limit=100,
    )
    assert len(rows) == 1
    assert rows[0].timestamp_ms == 1704067200000
    assert rows[0].volume == 10.0
    assert rows[0].num_trades == 20


def test_bybit_provider_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = BybitProvider(rate_limit_sleep=0.0)
    payload = {
        "retCode": 0,
        "result": {
            "list": [
                ["1704067200000", "100", "110", "90", "105", "10", "1000"],
            ]
        },
    }
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: _FakeResponse(status_code=200, payload=payload),
    )
    rows = provider.fetch_ohlcv(
        symbol="BTCUSDT",
        timeframe="1h",
        start_ts=1704067200000,
        end_ts=1704070800000,
        limit=100,
    )
    assert len(rows) == 1
    assert rows[0].timestamp_ms == 1704067200000
    assert rows[0].quote_volume == 1000.0


def test_backfill_fallback_provider_fills_chunk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PrimaryFailProvider:
        name = "primary"
        max_limit = 1000

        def __init__(self) -> None:
            self.calls = 0

        def fetch_ohlcv(self, *, symbol: str, timeframe: str, start_ts: int, end_ts: int, limit: int) -> list[OHLCVRow]:
            self.calls += 1
            raise RuntimeError("simulated primary failure")

    class _FallbackProvider:
        name = "secondary"
        max_limit = 1000

        def __init__(self) -> None:
            self.calls = 0

        def fetch_ohlcv(self, *, symbol: str, timeframe: str, start_ts: int, end_ts: int, limit: int) -> list[OHLCVRow]:
            self.calls += 1
            interval_ms = INTERVAL_MS[timeframe]
            out: list[OHLCVRow] = []
            cursor = start_ts
            while cursor < end_ts and len(out) < limit:
                out.append(
                    OHLCVRow(
                        timestamp_ms=cursor,
                        open=100.0,
                        high=101.0,
                        low=99.0,
                        close=100.5,
                        volume=10.0,
                        close_time_ms=cursor + interval_ms - 1,
                    )
                )
                cursor += interval_ms
            return out

    provider_objs = {
        "primary": _PrimaryFailProvider(),
        "secondary": _FallbackProvider(),
    }

    def _fake_create_provider(name: str, **kwargs: object) -> object:
        return provider_objs[name]

    monkeypatch.setattr(backfill, "available_providers", lambda: ["primary", "secondary"])
    monkeypatch.setattr(backfill, "create_provider", _fake_create_provider)

    compat_root = tmp_path / "binance"
    raw_root = tmp_path / "market"

    exit_code = backfill.main(
        [
            "--provider",
            "primary",
            "--fallback-providers",
            "secondary",
            "--symbols",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-02",
            "--output-root",
            str(compat_root),
            "--raw-root",
            str(raw_root),
            "--rate-limit-sleep",
            "0",
        ]
    )

    assert exit_code == 0
    assert provider_objs["primary"].calls > 0
    assert provider_objs["secondary"].calls > 0

    compat_file = compat_root / "BTCUSDT" / "1h" / "2024.parquet"
    raw_fallback_file = raw_root / "secondary" / "BTCUSDT" / "1h" / "2024.parquet"
    raw_primary_file = raw_root / "primary" / "BTCUSDT" / "1h" / "2024.parquet"

    assert compat_file.exists()
    assert raw_fallback_file.exists()
    assert not raw_primary_file.exists()

    frame = pd.read_parquet(compat_file)
    assert len(frame) == 24
    assert pd.to_datetime(frame["timestamp"], utc=True).is_monotonic_increasing
    assert frame["timestamp"].duplicated().sum() == 0
