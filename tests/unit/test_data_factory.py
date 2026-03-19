from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.data_factory import DataFactory, LocalDataProvider, normalize_symbol


class _FakeExchangeClient:
    def __init__(self, payload: list[list[object]] | None = None) -> None:
        self.payload = payload or []
        self.calls = 0

    def fetch_ohlcv(self, *, symbol: str, timeframe: str = "1m", limit: int = 500) -> list[list[object]]:
        _ = (symbol, timeframe, limit)
        self.calls += 1
        return list(self.payload)


def _sample_frame() -> pd.DataFrame:
    ts = pd.date_range("2024-01-01T00:00:00Z", periods=3, freq="h")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "volume": [100.0, 200.0, 300.0],
        }
    )


def test_normalize_symbol_accepts_slash_underscore_and_case() -> None:
    assert normalize_symbol("BTC/USDT") == "BTC_USDT"
    assert normalize_symbol("btc_usdt") == "BTC_USDT"
    assert normalize_symbol("BtC-uSdT") == "BTC_USDT"


def test_local_provider_symbol_mapping_resolves_btc_usdt_file(tmp_path: Path) -> None:
    target = tmp_path / "btc_usdt.parquet"
    target.write_bytes(b"stub")
    provider = LocalDataProvider(root=tmp_path)
    assert provider.resolve_parquet_path("BTC/USDT") == target
    assert provider.resolve_parquet_path("btc_usdt") == target


def test_extreme_gap_uses_absolute_parquet_timeline(tmp_path: Path, monkeypatch) -> None:
    parquet_file = tmp_path / "BTC_USDT.parquet"
    parquet_file.write_bytes(b"stub")
    df = _sample_frame()
    monkeypatch.setattr(LocalDataProvider, "_read_parquet", staticmethod(lambda _: df.copy()))

    factory = DataFactory(data_root=tmp_path, evolve=False, exchange_client=None)
    aligned = factory.load_frame(
        symbol="BTC/USDT",
        now=pd.Timestamp("2030-01-01T00:00:00Z"),
    )

    assert aligned["timestamp"].iloc[0] == df["timestamp"].iloc[0]
    assert aligned["relative_index"].tolist() == [0, 1, 2]


def test_evolve_mode_bypasses_exchange_and_returns_real_local_rows(tmp_path: Path, monkeypatch) -> None:
    parquet_file = tmp_path / "BTC_USDT.parquet"
    parquet_file.write_bytes(b"stub")
    df = _sample_frame()
    monkeypatch.setattr(LocalDataProvider, "_read_parquet", staticmethod(lambda _: df.copy()))

    exchange = _FakeExchangeClient(payload=[[0, 0, 0, 0, 0, 0]])
    factory = DataFactory(data_root=tmp_path, evolve=True, exchange_client=exchange)

    first = factory.fetch_ohlcv(symbol="BTC/USDT", limit=2, now=pd.Timestamp("2030-01-01T00:00:00Z"))
    second = factory.fetch_ohlcv(symbol="BTC/USDT", limit=2, now=pd.Timestamp("2030-01-01T00:00:00Z"))

    assert exchange.calls == 0
    assert len(first) == 2
    assert first[0][1:6] == [10.0, 11.0, 9.0, 10.5, 100.0]
    assert len(second) == 1
    assert second[0][1:6] == [12.0, 13.0, 11.0, 12.5, 300.0]


def test_non_evolve_prefers_exchange_client_when_available() -> None:
    exchange = _FakeExchangeClient(payload=[[1, 2, 3, 4, 5, 6]])
    factory = DataFactory(data_root="data/time_machine", evolve=False, exchange_client=exchange)
    rows = factory.fetch_ohlcv(symbol="BTC/USDT", limit=1)
    assert rows == [[1, 2, 3, 4, 5, 6]]
    assert exchange.calls == 1
