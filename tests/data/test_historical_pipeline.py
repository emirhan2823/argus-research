"""End-to-end tests for the historical data pipeline.

Tests the full flow: download -> store -> replay, all with mocked HTTP.
No real network calls are made.

Run:
    python -m pytest tests/data/test_historical_pipeline.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.binance_downloader import BinanceDownloader, _parse_kline
from src.data.local_store import LocalStore
from src.data.replay_loader import ReplayLoader
from src.data.data_factory import DataFactory


# ---------------------------------------------------------------------------
# Fixtures: generate deterministic Binance-format kline data
# ---------------------------------------------------------------------------

def _make_kline(open_time_ms: int, price_base: float = 42000.0) -> list:
    """Create a single Binance kline array (12 elements).

    [open_time, open, high, low, close, volume, close_time,
     quote_vol, num_trades, taker_buy_base, taker_buy_quote, ignore]
    """
    o = price_base
    h = price_base + 50.0
    l = price_base - 30.0
    c = price_base + 10.0
    v = 1234.56
    close_time = open_time_ms + 59_999  # 1m candle
    return [
        open_time_ms, str(o), str(h), str(l), str(c), str(v),
        close_time, str(v * o), 500, str(v * 0.6), str(v * 0.6 * o), "0",
    ]


def _make_klines_batch(
    start_ms: int,
    count: int,
    interval_ms: int = 60_000,
    price_base: float = 42000.0,
) -> list[list]:
    """Create a batch of N kline arrays starting at start_ms."""
    return [
        _make_kline(start_ms + i * interval_ms, price_base + i * 0.1)
        for i in range(count)
    ]


# Known window: 2024-01-15 00:00 UTC -> 2024-01-15 01:00 UTC (60 bars @ 1m)
JAN15_START_MS = int(datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
KNOWN_KLINES_60 = _make_klines_batch(JAN15_START_MS, 60)

# Larger set spanning 2 months: 2024-01-30 -> 2024-02-02 (4320 bars @ 1m = 3 days)
JAN30_START_MS = int(datetime(2024, 1, 30, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
CROSS_MONTH_KLINES = _make_klines_batch(JAN30_START_MS, 4320)


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    """Temporary directory for LocalStore."""
    return tmp_path / "binance"


@pytest.fixture
def store(store_dir: Path) -> LocalStore:
    return LocalStore(root=store_dir)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """60-bar 1m DataFrame for 2024-01-15 00:00-01:00 UTC."""
    rows = [_parse_kline(k) for k in KNOWN_KLINES_60]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df


@pytest.fixture
def cross_month_df() -> pd.DataFrame:
    """4320-bar DataFrame spanning Jan 30 -> Feb 2, 2024 (3 days)."""
    rows = [_parse_kline(k) for k in CROSS_MONTH_KLINES]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df


# ---------------------------------------------------------------------------
# A) BinanceDownloader tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestBinanceDownloader:
    """Tests for the chunked downloader with mocked requests."""

    def test_download_small_window_mocked(self) -> None:
        """Download 60 bars with a single chunk (under 1000 limit)."""
        downloader = BinanceDownloader(use_futures=True, rate_limit_sleep=0.0)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = KNOWN_KLINES_60
        mock_resp.raise_for_status = MagicMock()

        with patch.object(downloader._session, "get", return_value=mock_resp):
            df = downloader.download(
                symbol="BTCUSDT",
                interval="1m",
                start_date="2024-01-15",
                end_date="2024-01-15T01:00:00",
            )

        assert len(df) == 60
        assert list(df.columns[:6]) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert df["timestamp"].is_monotonic_increasing
        assert df["timestamp"].duplicated().sum() == 0

    def test_download_chunks_pagination(self) -> None:
        """Verify downloader handles multi-chunk pagination."""
        downloader = BinanceDownloader(use_futures=True, rate_limit_sleep=0.0)

        # First call returns 1000 bars, second returns 500, third returns empty
        chunk1 = _make_klines_batch(JAN15_START_MS, 1000)
        chunk2 = _make_klines_batch(JAN15_START_MS + 1000 * 60_000, 500)

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if call_count == 1:
                resp.json.return_value = chunk1
            elif call_count == 2:
                resp.json.return_value = chunk2
            else:
                resp.json.return_value = []
            return resp

        with patch.object(downloader._session, "get", side_effect=mock_get):
            df = downloader.download(
                symbol="BTCUSDT",
                interval="1m",
                start_date="2024-01-15",
                end_date="2024-01-16",
            )

        assert len(df) == 1500
        assert df["timestamp"].is_monotonic_increasing

    def test_download_retries_on_failure(self) -> None:
        """Verify retry logic on HTTP errors."""
        import requests as _req

        downloader = BinanceDownloader(
            use_futures=True,
            max_retries=3,
            rate_limit_sleep=0.0,
        )

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise _req.exceptions.ConnectionError("timeout")
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = KNOWN_KLINES_60
            return resp

        with patch.object(downloader._session, "get", side_effect=mock_get):
            df = downloader.download(
                symbol="BTCUSDT",
                interval="1m",
                start_date="2024-01-15",
                end_date="2024-01-15T01:00:00",
            )

        assert len(df) == 60
        assert call_count >= 2  # At least one retry

    def test_parse_kline_values(self) -> None:
        """Verify individual kline parsing."""
        k = _make_kline(JAN15_START_MS, 42000.0)
        parsed = _parse_kline(k)

        assert parsed["timestamp"] == JAN15_START_MS
        assert parsed["open"] == 42000.0
        assert parsed["high"] == 42050.0
        assert parsed["low"] == 41970.0
        assert parsed["close"] == 42010.0
        assert parsed["volume"] == 1234.56

    def test_date_parsing(self) -> None:
        """Verify date string parsing."""
        dt = BinanceDownloader._parse_date("2024-01-15", default_days_ago=0)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.tzinfo is not None

    def test_empty_response_returns_empty_df(self) -> None:
        """Download with no data returns empty DataFrame."""
        downloader = BinanceDownloader(use_futures=True, rate_limit_sleep=0.0)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        with patch.object(downloader._session, "get", return_value=mock_resp):
            df = downloader.download(
                symbol="BTCUSDT",
                interval="1m",
                start_date="2024-01-15",
                end_date="2024-01-15T01:00:00",
            )

        assert df.empty
        assert "timestamp" in df.columns


# ---------------------------------------------------------------------------
# B) LocalStore tests (Parquet persistence)
# ---------------------------------------------------------------------------

class TestLocalStore:
    """Tests for month-partitioned Parquet storage."""

    def test_save_and_load_single_month(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """Save a single month of data and reload it."""
        paths = store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        assert len(paths) == 1
        assert "2024-01" in str(paths[0])
        assert paths[0].exists()

        loaded = store.load_month("BTCUSDT", "1m", "2024-01")
        assert len(loaded) == 60
        assert loaded["timestamp"].is_monotonic_increasing

    def test_save_cross_month_partitions(
        self, store: LocalStore, cross_month_df: pd.DataFrame,
    ) -> None:
        """Data spanning Jan 30 -> Feb 1 should create 2 parquet files."""
        paths = store.save(df=cross_month_df, symbol="BTCUSDT", interval="1m")

        assert len(paths) == 2
        months = store.list_months("BTCUSDT", "1m")
        assert "2024-01" in months
        assert "2024-02" in months

    def test_append_safe_deduplication(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """Saving same data twice should not create duplicates."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loaded = store.load_month("BTCUSDT", "1m", "2024-01")
        assert len(loaded) == 60  # Not 120

    def test_sorted_after_save(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """Data is always sorted by timestamp after save."""
        # Shuffle the input
        shuffled = sample_df.sample(frac=1.0, random_state=42).reset_index(drop=True)
        store.save(df=shuffled, symbol="BTCUSDT", interval="1m")

        loaded = store.load_month("BTCUSDT", "1m", "2024-01")
        assert loaded["timestamp"].is_monotonic_increasing

    def test_load_all_combines_months(
        self, store: LocalStore, cross_month_df: pd.DataFrame,
    ) -> None:
        """load_all() combines all monthly files into one sorted DataFrame."""
        store.save(df=cross_month_df, symbol="BTCUSDT", interval="1m")

        combined = store.load_all("BTCUSDT", "1m")
        assert len(combined) == 4320
        assert combined["timestamp"].is_monotonic_increasing
        assert combined["timestamp"].duplicated().sum() == 0

    def test_list_symbols(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """list_symbols() discovers saved data."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")
        store.save(df=sample_df, symbol="ETHUSDT", interval="1m")

        symbols = store.list_symbols()
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_list_intervals(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """list_intervals() discovers interval directories."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")
        store.save(df=sample_df, symbol="BTCUSDT", interval="1h")

        intervals = store.list_intervals("BTCUSDT")
        assert "1m" in intervals
        assert "1h" in intervals

    def test_verify_integrity_clean_data(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """Integrity check on clean data reports no issues."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        result = store.verify_integrity("BTCUSDT", "1m")
        assert result["total_bars"] == 60
        assert result["is_sorted"] is True
        assert result["has_duplicates"] is False
        assert result["gap_count"] == 0

    def test_verify_integrity_with_gap(self, store: LocalStore) -> None:
        """Integrity check detects gaps in data."""
        # Create data with a 5-minute gap in the middle
        ts = list(pd.date_range("2024-01-15 00:00", periods=30, freq="1min", tz="UTC"))
        ts += list(pd.date_range("2024-01-15 00:35", periods=25, freq="1min", tz="UTC"))

        df = pd.DataFrame({
            "timestamp": ts,
            "open": [42000.0] * 55,
            "high": [42050.0] * 55,
            "low": [41970.0] * 55,
            "close": [42010.0] * 55,
            "volume": [1234.0] * 55,
        })
        store.save(df=df, symbol="BTCUSDT", interval="1m")

        result = store.verify_integrity("BTCUSDT", "1m")
        assert result["gap_count"] == 1

    def test_empty_dataframe_save(self, store: LocalStore) -> None:
        """Saving empty DataFrame does nothing."""
        empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        paths = store.save(df=empty, symbol="BTCUSDT", interval="1m")
        assert paths == []

    def test_symbol_normalization(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """Symbols are normalized to bare format (BTCUSDT)."""
        store.save(df=sample_df, symbol="BTC/USDT", interval="1m")
        months = store.list_months("BTCUSDT", "1m")
        assert "2024-01" in months

        store.save(df=sample_df, symbol="BTC_USDT", interval="1h")
        intervals = store.list_intervals("BTCUSDT")
        assert "1h" in intervals

    def test_delete_symbol(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """delete_symbol removes all data for a symbol."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")
        assert store.list_symbols() == ["BTCUSDT"]

        deleted = store.delete_symbol("BTCUSDT")
        assert deleted is True
        assert store.list_symbols() == []


# ---------------------------------------------------------------------------
# C) ReplayLoader tests
# ---------------------------------------------------------------------------

class TestReplayLoader:
    """Tests for deterministic OHLCV replay."""

    def test_load_exact_range(
        self, store: LocalStore, cross_month_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """Load data for an exact date range."""
        store.save(df=cross_month_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        df = loader.load_ohlcv(
            "BTCUSDT", "1m",
            start="2024-01-30",
            end="2024-01-31",
        )

        assert not df.empty
        assert df["timestamp"].iloc[0] >= pd.Timestamp("2024-01-30", tz="UTC")
        assert df["timestamp"].iloc[-1] <= pd.Timestamp("2024-01-31", tz="UTC")
        assert df["timestamp"].is_monotonic_increasing

    def test_load_all_available(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """Load all available data when no range specified."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        df = loader.load_ohlcv("BTCUSDT", "1m")

        assert len(df) == 60

    def test_replay_deterministic(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """Same query always returns identical results."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        df1 = loader.load_ohlcv("BTCUSDT", "1m")
        df2 = loader.load_ohlcv("BTCUSDT", "1m")

        pd.testing.assert_frame_equal(df1, df2)

    def test_no_duplicates_in_replay(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """Replay data has no duplicate timestamps."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        df = loader.load_ohlcv("BTCUSDT", "1m")

        assert df["timestamp"].duplicated().sum() == 0

    def test_sorted_replay(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """Replayed data is always sorted by timestamp."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        df = loader.load_ohlcv("BTCUSDT", "1m")

        assert df["timestamp"].is_monotonic_increasing

    def test_load_ohlcv_rows_format(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """load_ohlcv_rows returns ExchangeClient-compatible format."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        rows = loader.load_ohlcv_rows("BTCUSDT", "1m")

        assert len(rows) == 60
        assert len(rows[0]) == 6  # [ts, o, h, l, c, v]
        # All numeric values (except timestamp)
        for row in rows:
            assert isinstance(row[1], float)  # open
            assert isinstance(row[2], float)  # high
            assert isinstance(row[3], float)  # low
            assert isinstance(row[4], float)  # close
            assert isinstance(row[5], float)  # volume

    def test_load_ohlcv_rows_with_limit(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """load_ohlcv_rows respects limit parameter."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        rows = loader.load_ohlcv_rows("BTCUSDT", "1m", limit=10)

        assert len(rows) == 10

    def test_missing_symbol_raises(self, store_dir: Path) -> None:
        """Loading nonexistent symbol raises FileNotFoundError."""
        loader = ReplayLoader(root=store_dir)
        with pytest.raises(FileNotFoundError):
            loader.load_ohlcv("NONEXISTENT", "1m")

    def test_replay_windows(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path,
    ) -> None:
        """replay_windows yields correct sliding windows."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        windows = list(loader.replay_windows(
            "BTCUSDT", "1m",
            window_size=20,
            step_size=10,
        ))

        # 60 bars, window=20, step=10 -> windows at [0:20], [10:30], [20:40], [30:50], [40:60]
        assert len(windows) == 5
        for w in windows:
            assert len(w) == 20
            assert w["timestamp"].is_monotonic_increasing

    def test_gap_warning(
        self, store: LocalStore, store_dir: Path,
    ) -> None:
        """Gaps in data trigger a warning."""
        ts = list(pd.date_range("2024-01-15 00:00", periods=30, freq="1min", tz="UTC"))
        ts += list(pd.date_range("2024-01-15 00:35", periods=25, freq="1min", tz="UTC"))

        df = pd.DataFrame({
            "timestamp": ts,
            "open": [42000.0] * 55,
            "high": [42050.0] * 55,
            "low": [41970.0] * 55,
            "close": [42010.0] * 55,
            "volume": [1234.0] * 55,
        })
        store.save(df=df, symbol="BTCUSDT", interval="1m")

        loader = ReplayLoader(root=store_dir)
        with pytest.warns(UserWarning, match="gap"):
            loader.load_ohlcv("BTCUSDT", "1m", verify=True)


# ---------------------------------------------------------------------------
# D) Full pipeline: download -> store -> replay
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """End-to-end: mock download -> save to parquet -> replay loads same data."""

    def test_download_save_replay_roundtrip(self, store_dir: Path) -> None:
        """Full roundtrip: download mocked data, save, reload, verify equality."""
        # Step 1: Download with mocked HTTP
        downloader = BinanceDownloader(use_futures=True, rate_limit_sleep=0.0)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = KNOWN_KLINES_60
        mock_resp.raise_for_status = MagicMock()

        with patch.object(downloader._session, "get", return_value=mock_resp):
            downloaded_df = downloader.download(
                symbol="BTCUSDT",
                interval="1m",
                start_date="2024-01-15",
                end_date="2024-01-15T01:00:00",
            )

        # Step 2: Save to local store
        store = LocalStore(root=store_dir)
        paths = store.save(df=downloaded_df, symbol="BTCUSDT", interval="1m")
        assert len(paths) >= 1

        # Step 3: Replay load
        loader = ReplayLoader(root=store_dir)
        replayed_df = loader.load_ohlcv("BTCUSDT", "1m")

        # Step 4: Verify equality
        assert len(replayed_df) == len(downloaded_df)

        # Compare OHLCV values (core columns)
        for col in ("open", "high", "low", "close", "volume"):
            pd.testing.assert_series_equal(
                downloaded_df[col].reset_index(drop=True),
                replayed_df[col].reset_index(drop=True),
                check_names=False,
            )

        # Timestamps match
        assert (
            downloaded_df["timestamp"].reset_index(drop=True)
            == replayed_df["timestamp"].reset_index(drop=True)
        ).all()

        # Both sorted
        assert downloaded_df["timestamp"].is_monotonic_increasing
        assert replayed_df["timestamp"].is_monotonic_increasing

        # No duplicates
        assert downloaded_df["timestamp"].duplicated().sum() == 0
        assert replayed_df["timestamp"].duplicated().sum() == 0


# ---------------------------------------------------------------------------
# E) DataFactory integration (mode="replay")
# ---------------------------------------------------------------------------

class TestDataFactoryReplayMode:
    """Test DataFactory with mode='replay'."""

    def test_replay_mode_uses_replay_loader(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path, tmp_path: Path,
    ) -> None:
        """DataFactory in replay mode loads from partitioned parquet."""
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        factory = DataFactory(
            data_root=tmp_path / "time_machine",
            mode="replay",
            replay_root=store_dir,
        )

        rows = factory.fetch_ohlcv(symbol="BTCUSDT", timeframe="1m", limit=60)
        assert len(rows) == 60
        # Verify format: [timestamp, open, high, low, close, volume]
        assert len(rows[0]) == 6

    def test_replay_mode_fallback_to_exchange(
        self, store_dir: Path, tmp_path: Path,
    ) -> None:
        """If replay has no data, fall through to exchange client."""

        class _FakeClient:
            def fetch_ohlcv(self, *, symbol, timeframe="1m", limit=500):
                return [[1, 2, 3, 4, 5, 6]]

        factory = DataFactory(
            data_root=tmp_path / "time_machine",
            mode="replay",
            replay_root=store_dir,  # empty store
            exchange_client=_FakeClient(),
        )

        rows = factory.fetch_ohlcv(symbol="NONEXISTENT", timeframe="1m", limit=1)
        assert rows == [[1, 2, 3, 4, 5, 6]]

    def test_mock_mode_unchanged(self, tmp_path: Path) -> None:
        """Mock mode behavior is unchanged (backward compat)."""

        class _FakeClient:
            def fetch_ohlcv(self, *, symbol, timeframe="1m", limit=500):
                return [[10, 20, 30, 40, 50, 60]]

        factory = DataFactory(
            data_root=tmp_path / "time_machine",
            mode="mock",
            exchange_client=_FakeClient(),
        )

        rows = factory.fetch_ohlcv(symbol="BTCUSDT", timeframe="1m", limit=1)
        assert rows == [[10, 20, 30, 40, 50, 60]]

    def test_evolve_mode_unaffected(
        self, store: LocalStore, sample_df: pd.DataFrame, store_dir: Path, tmp_path: Path,
    ) -> None:
        """Evolve mode always uses local provider, ignores replay mode."""
        # Save data in replay store
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")

        # Create local time_machine data
        tm_dir = tmp_path / "time_machine"
        tm_dir.mkdir()
        local_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=5, freq="h", tz="UTC"),
            "open": [99.0] * 5,
            "high": [100.0] * 5,
            "low": [98.0] * 5,
            "close": [99.5] * 5,
            "volume": [500.0] * 5,
        })
        local_df.to_parquet(tm_dir / "BTC_USDT.parquet", index=False)

        factory = DataFactory(
            data_root=tm_dir,
            evolve=True,
            mode="replay",
            replay_root=store_dir,
        )

        rows = factory.fetch_ohlcv(symbol="BTC/USDT", limit=3)
        # Should get local data (99.0), not replay data (42000.0)
        assert len(rows) == 3
        assert rows[0][1] == 99.0  # open from local


# ---------------------------------------------------------------------------
# F) Multi-timeframe support
# ---------------------------------------------------------------------------

class TestMultiTimeframe:
    """Test that different intervals are stored separately."""

    def test_different_intervals_separate_files(
        self, store: LocalStore, sample_df: pd.DataFrame,
    ) -> None:
        """1m and 1h data stored in separate directories."""
        # Save as 1m
        store.save(df=sample_df, symbol="BTCUSDT", interval="1m")
        # Save as 1h (same data, different interval label)
        store.save(df=sample_df, symbol="BTCUSDT", interval="1h")

        assert store.list_intervals("BTCUSDT") == ["1h", "1m"]
        m1 = store.load_month("BTCUSDT", "1m", "2024-01")
        h1 = store.load_month("BTCUSDT", "1h", "2024-01")
        assert len(m1) == 60
        assert len(h1) == 60
