from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.scanner.replay_sonar_client import ReplaySonarClient


def _write_month_data(root: Path, symbol: str, interval: str, month: str, start: str) -> None:
    out_dir = root / symbol / interval
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range(start=start, periods=120, freq="15min", tz="UTC")
    base = 100.0 if symbol == "BTCUSDT" else 10.0
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": [base + i * 0.01 for i in range(len(ts))],
            "high": [base + i * 0.012 for i in range(len(ts))],
            "low": [base + i * 0.008 for i in range(len(ts))],
            "close": [base + i * 0.011 for i in range(len(ts))],
            "volume": [1000.0 + i for i in range(len(ts))],
        }
    )
    df.to_parquet(out_dir / f"{month}.parquet", index=False)


def test_replay_sonar_client_filters_symbols_by_listing_time(tmp_path: Path) -> None:
    _write_month_data(tmp_path, "BTCUSDT", "15m", "2024-01", "2024-01-01T00:00:00Z")
    _write_month_data(tmp_path, "HYPEUSDT", "15m", "2024-12", "2024-12-05T00:00:00Z")

    client = ReplaySonarClient(root=tmp_path, default_interval="15m")
    pre = client.fetch_exchange_info(as_of=datetime(2024, 11, 20, tzinfo=timezone.utc))
    post = client.fetch_exchange_info(as_of=datetime(2025, 1, 15, tzinfo=timezone.utc))

    assert {x["symbol"] for x in pre} == {"BTCUSDT"}
    assert {x["symbol"] for x in post} == {"BTCUSDT", "HYPEUSDT"}


def test_replay_sonar_client_tickers_respect_listing_time(tmp_path: Path) -> None:
    _write_month_data(tmp_path, "BTCUSDT", "15m", "2024-01", "2024-01-01T00:00:00Z")
    _write_month_data(tmp_path, "HYPEUSDT", "15m", "2024-12", "2024-12-05T00:00:00Z")

    client = ReplaySonarClient(root=tmp_path, default_interval="15m")
    pre = client.fetch_24h_tickers(as_of=datetime(2024, 11, 20, tzinfo=timezone.utc))
    post = client.fetch_24h_tickers(as_of=datetime(2025, 1, 15, tzinfo=timezone.utc))

    assert {x["symbol"] for x in pre} == {"BTCUSDT"}
    assert {x["symbol"] for x in post} == {"BTCUSDT", "HYPEUSDT"}
    assert all(float(x["volume_usdt"]) > 0.0 for x in post)

