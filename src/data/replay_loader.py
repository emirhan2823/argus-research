"""Deterministic OHLCV replay loader from month-partitioned Parquet storage.

Loads only the required parquet files for a given date range,
filters precisely, verifies no gaps, and returns a sorted DataFrame.

Usage:
    from src.data.replay_loader import ReplayLoader

    loader = ReplayLoader(root="data/binance")
    df = loader.load_ohlcv("BTCUSDT", "1m", "2024-01-01", "2024-03-01")
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.data.local_store import LocalStore

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interval -> timedelta mapping
# ---------------------------------------------------------------------------

_INTERVAL_TD: dict[str, pd.Timedelta] = {
    "1m": pd.Timedelta(minutes=1),
    "3m": pd.Timedelta(minutes=3),
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "2h": pd.Timedelta(hours=2),
    "4h": pd.Timedelta(hours=4),
    "6h": pd.Timedelta(hours=6),
    "8h": pd.Timedelta(hours=8),
    "12h": pd.Timedelta(hours=12),
    "1d": pd.Timedelta(days=1),
}


class ReplayLoader:
    """Load OHLCV data from local month-partitioned Parquet storage.

    Designed for deterministic backtesting and walk-forward validation.
    Only reads the parquet files that overlap the requested date range.
    """

    def __init__(self, root: str | Path = "data/binance") -> None:
        self._store = LocalStore(root=root)

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def load_ohlcv(
        self,
        symbol: str,
        interval: str = "1m",
        start: str | datetime | pd.Timestamp | None = None,
        end: str | datetime | pd.Timestamp | None = None,
        *,
        verify: bool = True,
    ) -> pd.DataFrame:
        """Load OHLCV data for a symbol/interval within a date range.

        Args:
            symbol: Trading pair (e.g. BTCUSDT, BTC_USDT, BTC/USDT).
            interval: Candle interval (e.g. 1m, 5m, 1h, 1d).
            start: Start of date range (inclusive). None = all available.
            end: End of date range (inclusive). None = all available.
            verify: If True, run gap detection and integrity checks.

        Returns:
            Sorted, deduplicated DataFrame with columns:
            timestamp, open, high, low, close, volume, [extras...]

        Raises:
            FileNotFoundError: If no data exists for the symbol/interval.
        """
        start_ts = self._parse_ts(start) if start is not None else None
        end_ts = self._parse_ts(end) if end is not None else None

        # Determine which monthly files to load
        available_months = self._store.list_months(symbol, interval)
        if not available_months:
            raise FileNotFoundError(
                f"No stored data for {symbol}/{interval} in {self._store.root}"
            )

        # Filter months to only those overlapping the requested range
        needed_months = self._filter_months(available_months, start_ts, end_ts)
        if not needed_months:
            LOG.warning(
                "No data for %s/%s in range %s -> %s. Available months: %s",
                symbol, interval, start, end, available_months,
            )
            return pd.DataFrame(columns=LocalStore.OHLCV_COLUMNS)

        LOG.debug(
            "Loading %d monthly files for %s/%s: %s",
            len(needed_months), symbol, interval, needed_months,
        )

        # Load and concatenate only needed months
        frames: list[pd.DataFrame] = []
        for month in needed_months:
            mdf = self._store.load_month(symbol, interval, month)
            if not mdf.empty:
                frames.append(mdf)

        if not frames:
            return pd.DataFrame(columns=LocalStore.OHLCV_COLUMNS)

        df = pd.concat(frames, ignore_index=True)

        # Ensure timestamp is UTC datetime
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        elif df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

        # Sort and deduplicate (deterministic)
        df = (
            df.drop_duplicates(subset=["timestamp"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        # Filter to exact date range
        if start_ts is not None:
            df = df[df["timestamp"] >= start_ts]
        if end_ts is not None:
            df = df[df["timestamp"] <= end_ts]

        df = df.reset_index(drop=True)

        # Integrity verification
        if verify and not df.empty:
            self._verify_integrity(df, symbol, interval)

        LOG.info(
            "Loaded %s/%s: %d bars, %s -> %s",
            symbol, interval, len(df),
            df["timestamp"].iloc[0].isoformat() if not df.empty else "N/A",
            df["timestamp"].iloc[-1].isoformat() if not df.empty else "N/A",
        )

        return df

    # ------------------------------------------------------------------
    # Convenience: load as list[list] for DataFactory compatibility
    # ------------------------------------------------------------------

    def load_ohlcv_rows(
        self,
        symbol: str,
        interval: str = "1m",
        start: str | datetime | pd.Timestamp | None = None,
        end: str | datetime | pd.Timestamp | None = None,
        *,
        limit: int | None = None,
        now: str | datetime | pd.Timestamp | None = None,
    ) -> list[list]:
        """Load OHLCV as list of [timestamp, open, high, low, close, volume].

        Compatible with ExchangeClient.fetch_ohlcv() return format.

        When ``now`` is provided, it acts as the right-edge of the window:
        return the last ``limit`` bars whose timestamp <= now.  This makes
        replay deterministic — the same ``now`` always yields the same slice.
        """
        # When now is given, use it as the end boundary
        effective_end = end
        if now is not None and end is None:
            effective_end = now

        df = self.load_ohlcv(symbol, interval, start, effective_end, verify=False)

        if limit is not None and len(df) > limit:
            df = df.tail(limit)

        return [
            [
                row.timestamp,
                float(row.open),
                float(row.high),
                float(row.low),
                float(row.close),
                float(row.volume),
            ]
            for row in df.itertuples(index=False)
        ]

    # ------------------------------------------------------------------
    # Window-based replay (for walk-forward)
    # ------------------------------------------------------------------

    def replay_windows(
        self,
        symbol: str,
        interval: str = "1m",
        start: str | datetime | pd.Timestamp | None = None,
        end: str | datetime | pd.Timestamp | None = None,
        *,
        window_size: int = 260,
        step_size: int = 1,
    ):
        """Yield sliding windows of OHLCV data for walk-forward replay.

        Args:
            symbol: Trading pair.
            interval: Candle interval.
            start: Start of replay range.
            end: End of replay range.
            window_size: Number of bars per window.
            step_size: Bars to advance between windows.

        Yields:
            DataFrame of window_size bars for each step.
        """
        df = self.load_ohlcv(symbol, interval, start, end, verify=True)

        if len(df) < window_size:
            LOG.warning(
                "Insufficient data for replay: %d bars < window_size %d",
                len(df), window_size,
            )
            return

        for i in range(0, len(df) - window_size + 1, step_size):
            window = df.iloc[i: i + window_size].copy().reset_index(drop=True)
            yield window

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ts(value: str | datetime | pd.Timestamp) -> pd.Timestamp:
        """Parse a date value into a UTC pd.Timestamp."""
        if isinstance(value, pd.Timestamp):
            if value.tzinfo is None:
                return value.tz_localize("UTC")
            return value.tz_convert("UTC")
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return pd.Timestamp(value, tz="UTC")
        # String
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(str(value), fmt)
                return pd.Timestamp(dt, tz="UTC")
            except ValueError:
                continue
        raise ValueError(f"Cannot parse timestamp: {value!r}")

    @staticmethod
    def _filter_months(
        available: list[str],
        start_ts: pd.Timestamp | None,
        end_ts: pd.Timestamp | None,
    ) -> list[str]:
        """Filter available months to only those overlapping the date range.

        Month strings are formatted as 'YYYY-MM'.
        """
        if start_ts is None and end_ts is None:
            return available

        needed = []
        for m in available:
            # Parse month string to a period
            try:
                period = pd.Period(m, freq="M")
            except Exception:
                needed.append(m)  # Can't parse, include it
                continue

            month_start = period.start_time.tz_localize("UTC")
            month_end = period.end_time.tz_localize("UTC")

            # Check overlap with requested range
            if end_ts is not None and month_start > end_ts:
                continue
            if start_ts is not None and month_end < start_ts:
                continue
            needed.append(m)

        return needed

    def _verify_integrity(
        self,
        df: pd.DataFrame,
        symbol: str,
        interval: str,
    ) -> None:
        """Verify loaded data integrity. Warns on issues, never raises."""
        # Check sorted
        if not df["timestamp"].is_monotonic_increasing:
            warnings.warn(
                f"Data for {symbol}/{interval} is not sorted by timestamp!",
                stacklevel=3,
            )

        # Check duplicates
        dup_count = df["timestamp"].duplicated().sum()
        if dup_count > 0:
            warnings.warn(
                f"Data for {symbol}/{interval} has {dup_count} duplicate timestamps!",
                stacklevel=3,
            )

        # Check gaps
        expected_td = _INTERVAL_TD.get(interval)
        if expected_td is not None and len(df) >= 2:
            diffs = df["timestamp"].diff().dropna()
            threshold = expected_td * 1.5
            gap_mask = diffs > threshold
            gap_count = int(gap_mask.sum())

            if gap_count > 0:
                # Find the biggest gap for logging
                max_gap = diffs[gap_mask].max()
                warnings.warn(
                    f"Data for {symbol}/{interval} has {gap_count} gap(s). "
                    f"Largest gap: {max_gap}. Expected interval: {expected_td}.",
                    stacklevel=3,
                )

        # Check NaN in OHLCV columns
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                nan_count = df[col].isna().sum()
                if nan_count > 0:
                    warnings.warn(
                        f"Data for {symbol}/{interval} has {nan_count} NaN values in '{col}'.",
                        stacklevel=3,
                    )
