"""Month-partitioned Parquet local storage for OHLCV data.

Storage layout:
    data/binance/{SYMBOL}/{INTERVAL}/{YYYY-MM}.parquet

Design rules:
    - Append-safe: new data merges with existing parquet files
    - Deduplicate: timestamps are unique per file
    - Sorted: rows always ordered by timestamp ascending
    - Deterministic: same input -> same output, always
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOG = logging.getLogger(__name__)


def _normalize_store_symbol(symbol: str) -> str:
    """Convert any symbol format to uppercase bare format (BTCUSDT)."""
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


class LocalStore:
    """Month-partitioned Parquet storage for Binance OHLCV data.

    Files are stored as:
        {root}/{SYMBOL}/{interval}/{YYYY-MM}.parquet

    Each parquet file contains all bars for that calendar month,
    sorted by timestamp, with no duplicate timestamps.
    """

    OHLCV_COLUMNS = [
        "timestamp", "open", "high", "low", "close", "volume",
    ]
    EXTRA_COLUMNS = [
        "close_time", "quote_volume", "num_trades",
        "taker_buy_volume", "taker_buy_quote_volume",
    ]

    def __init__(self, root: str | Path = "data/binance") -> None:
        self.root = Path(root)

    # ------------------------------------------------------------------
    # Save (with month partitioning)
    # ------------------------------------------------------------------

    def save(
        self,
        *,
        df: pd.DataFrame,
        symbol: str,
        interval: str = "1m",
    ) -> list[Path]:
        """Save OHLCV DataFrame to month-partitioned parquet files.

        Merges with any existing data (append-safe + deduplicate).

        Args:
            df: DataFrame with at least 'timestamp' column (UTC datetime).
            symbol: Trading pair (e.g. BTCUSDT).
            interval: Candle interval (e.g. 1m, 1h).

        Returns:
            List of paths to written parquet files.
        """
        if df.empty:
            LOG.warning("Empty DataFrame, nothing to save.")
            return []

        clean_symbol = _normalize_store_symbol(symbol)
        df = self._ensure_datetime_timestamp(df)

        # Group by year-month (strip tz before to_period to avoid pandas warning)
        _ts_utc = df["timestamp"].dt.tz_localize(None) if df["timestamp"].dt.tz is not None else df["timestamp"]
        df["_ym"] = _ts_utc.dt.to_period("M")
        groups = df.groupby("_ym")

        written_paths: list[Path] = []
        for period, group in groups:
            month_str = str(period)  # e.g. "2024-01"
            path = self._parquet_path(clean_symbol, interval, month_str)

            # Merge with existing data if file exists
            merged = self._merge_with_existing(path, group.drop(columns=["_ym"]))

            # Ensure sorted, deduplicated, reset index
            merged = (
                merged
                .drop_duplicates(subset=["timestamp"])
                .sort_values("timestamp")
                .reset_index(drop=True)
            )

            # Write
            path.parent.mkdir(parents=True, exist_ok=True)
            merged.to_parquet(path, index=False)

            LOG.debug("Wrote %d bars to %s", len(merged), path)
            written_paths.append(path)

        LOG.info(
            "Saved %s %s: %d bars across %d monthly files",
            clean_symbol, interval, len(df), len(written_paths),
        )
        return written_paths

    # ------------------------------------------------------------------
    # List available data
    # ------------------------------------------------------------------

    def list_symbols(self) -> list[str]:
        """List all symbols that have stored data."""
        if not self.root.exists():
            return []
        return sorted([
            d.name for d in self.root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

    def list_intervals(self, symbol: str) -> list[str]:
        """List available intervals for a symbol."""
        clean = _normalize_store_symbol(symbol)
        sym_dir = self.root / clean
        if not sym_dir.exists():
            return []
        return sorted([
            d.name for d in sym_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

    def list_months(self, symbol: str, interval: str = "1m") -> list[str]:
        """List available month files for symbol/interval."""
        clean = _normalize_store_symbol(symbol)
        interval_dir = self.root / clean / interval
        if not interval_dir.exists():
            return []
        return sorted([
            f.stem for f in interval_dir.glob("*.parquet")
        ])

    # ------------------------------------------------------------------
    # Load (raw, single month)
    # ------------------------------------------------------------------

    def load_month(
        self,
        symbol: str,
        interval: str = "1m",
        month: str = "",
    ) -> pd.DataFrame:
        """Load a single month parquet file.

        Args:
            symbol: Trading pair
            interval: Candle interval
            month: Year-month string (e.g. "2024-01")

        Returns:
            DataFrame, or empty DataFrame if file doesn't exist.
        """
        clean = _normalize_store_symbol(symbol)
        path = self._parquet_path(clean, interval, month)
        if not path.exists():
            LOG.debug("Month file not found: %s", path)
            return pd.DataFrame(columns=self.OHLCV_COLUMNS)
        return pd.read_parquet(path)

    def load_all(
        self,
        symbol: str,
        interval: str = "1m",
    ) -> pd.DataFrame:
        """Load all available months for a symbol/interval, concatenated.

        Returns sorted, deduplicated DataFrame.
        """
        months = self.list_months(symbol, interval)
        if not months:
            return pd.DataFrame(columns=self.OHLCV_COLUMNS)

        frames = []
        for m in months:
            df = self.load_month(symbol, interval, m)
            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame(columns=self.OHLCV_COLUMNS)

        combined = pd.concat(frames, ignore_index=True)
        combined = (
            combined
            .drop_duplicates(subset=["timestamp"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        return combined

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def verify_integrity(
        self,
        symbol: str,
        interval: str = "1m",
    ) -> dict[str, object]:
        """Run integrity checks on stored data.

        Returns dict with check results:
            - total_bars: int
            - is_sorted: bool
            - has_duplicates: bool
            - gap_count: int (missing expected timestamps)
            - date_range: tuple[str, str] or None
        """
        df = self.load_all(symbol, interval)
        if df.empty:
            return {
                "total_bars": 0,
                "is_sorted": True,
                "has_duplicates": False,
                "gap_count": 0,
                "date_range": None,
            }

        df = self._ensure_datetime_timestamp(df)
        ts = df["timestamp"]

        is_sorted = bool(ts.is_monotonic_increasing)
        has_duplicates = bool(ts.duplicated().any())

        # Check for gaps
        gap_count = self._count_gaps(ts, interval)

        return {
            "total_bars": len(df),
            "is_sorted": is_sorted,
            "has_duplicates": has_duplicates,
            "gap_count": gap_count,
            "date_range": (
                ts.iloc[0].isoformat(),
                ts.iloc[-1].isoformat(),
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parquet_path(self, symbol: str, interval: str, month: str) -> Path:
        """Build the parquet file path for a given symbol/interval/month."""
        return self.root / symbol / interval / f"{month}.parquet"

    def _merge_with_existing(
        self,
        path: Path,
        new_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge new data with existing parquet file if it exists."""
        if not path.exists():
            return new_data.copy()

        try:
            existing = pd.read_parquet(path)
            # Ensure both have datetime timestamps for proper dedup
            existing = self._ensure_datetime_timestamp(existing)
            new_data = self._ensure_datetime_timestamp(new_data)
            combined = pd.concat([existing, new_data], ignore_index=True)
            return combined
        except Exception as exc:
            LOG.warning("Failed to read existing parquet %s: %s. Overwriting.", path, exc)
            return new_data.copy()

    @staticmethod
    def _ensure_datetime_timestamp(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the timestamp column is UTC datetime."""
        if "timestamp" not in df.columns:
            return df
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        elif df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        return df

    @staticmethod
    def _count_gaps(ts: pd.Series, interval: str) -> int:
        """Count the number of missing expected timestamps in the series.

        Only counts gaps within trading hours. Crypto trades 24/7 so
        every interval should be present.
        """
        if len(ts) < 2:
            return 0

        # Map interval to expected timedelta
        _interval_td = {
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

        expected_td = _interval_td.get(interval)
        if expected_td is None:
            return 0  # Can't check gaps for unknown intervals

        diffs = ts.diff().dropna()
        # A gap is any diff > 1.5x the expected interval
        threshold = expected_td * 1.5
        gap_mask = diffs > threshold
        return int(gap_mask.sum())

    def delete_symbol(self, symbol: str) -> bool:
        """Delete all stored data for a symbol. Returns True if data existed."""
        import shutil
        clean = _normalize_store_symbol(symbol)
        sym_dir = self.root / clean
        if sym_dir.exists():
            shutil.rmtree(sym_dir)
            LOG.info("Deleted all data for %s", clean)
            return True
        return False
