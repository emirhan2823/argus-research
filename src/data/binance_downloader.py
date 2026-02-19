"""Production-grade Binance historical OHLCV downloader.

Handles the /api/v3/klines and /fapi/v1/klines endpoints with:
- Chunked pagination (1000-bar limit per request)
- Rate-limit-safe sleep between requests
- Multi-timeframe support (1m primary)
- Robust error handling + retry
- CLI entry point for standalone use

Usage:
    python -m src.data.binance_downloader \\
        --symbol BTCUSDT --interval 1m \\
        --start 2024-01-01 --end 2024-03-01
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPOT_URL = "https://api.binance.com/api/v3/klines"
FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"

CHUNK_LIMIT = 1000  # Binance hard limit per request

INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}

_TF_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h",
    "12h": "12h", "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
}

RATE_LIMIT_SLEEP = 0.25  # seconds between requests (conservative)
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5  # exponential backoff multiplier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_binance_symbol(symbol: str) -> str:
    """Normalize any symbol format to bare Binance symbol (BTCUSDT)."""
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


def _parse_kline(k: list) -> dict[str, Any]:
    """Parse a single Binance kline array into a typed dict.

    Binance kline format:
    [open_time, open, high, low, close, volume, close_time,
     quote_asset_vol, num_trades, taker_buy_base_vol, taker_buy_quote_vol, ignore]
    """
    return {
        "timestamp": int(k[0]),       # open_time in ms
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
        "close_time": int(k[6]),
        "quote_volume": float(k[7]),
        "num_trades": int(k[8]),
        "taker_buy_volume": float(k[9]),
        "taker_buy_quote_volume": float(k[10]),
    }


# ---------------------------------------------------------------------------
# Core downloader
# ---------------------------------------------------------------------------

class BinanceDownloader:
    """Chunked historical OHLCV downloader for Binance.

    Downloads data in 1000-bar chunks, handles pagination automatically,
    respects rate limits, and returns a clean pandas DataFrame.
    """

    def __init__(
        self,
        *,
        use_futures: bool = True,
        timeout: float = 15.0,
        max_retries: int = MAX_RETRIES,
        rate_limit_sleep: float = RATE_LIMIT_SLEEP,
    ) -> None:
        self.base_url = FUTURES_URL if use_futures else SPOT_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_sleep = rate_limit_sleep
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "ARGUS/2.5-Downloader"})
        self._request_count = 0

    # ------------------------------------------------------------------
    # Single-chunk fetch
    # ------------------------------------------------------------------

    def _fetch_chunk(
        self,
        *,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> list[dict[str, Any]]:
        """Fetch a single chunk of up to CHUNK_LIMIT bars.

        Returns list of parsed kline dicts. Empty list on failure.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": CHUNK_LIMIT,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(
                    self.base_url, params=params, timeout=self.timeout,
                )

                # Handle rate-limit (HTTP 429)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    LOG.warning(
                        "Rate limited (429). Sleeping %ds (attempt %d/%d)",
                        retry_after, attempt, self.max_retries,
                    )
                    time.sleep(retry_after)
                    continue

                # Handle IP ban (HTTP 418)
                if resp.status_code == 418:
                    ban_seconds = int(resp.headers.get("Retry-After", "120"))
                    LOG.error("IP banned (418). Sleeping %ds", ban_seconds)
                    time.sleep(ban_seconds)
                    continue

                resp.raise_for_status()
                raw = resp.json()
                self._request_count += 1

                if not isinstance(raw, list):
                    LOG.warning("Unexpected response type: %s", type(raw).__name__)
                    return []

                return [_parse_kline(k) for k in raw]

            except requests.exceptions.RequestException as exc:
                LOG.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt, self.max_retries, exc,
                )
                if attempt < self.max_retries:
                    sleep_time = RETRY_BACKOFF ** attempt
                    time.sleep(sleep_time)

        LOG.error("All %d attempts failed for %s", self.max_retries, symbol)
        return []

    # ------------------------------------------------------------------
    # Full-range download with auto-chunking
    # ------------------------------------------------------------------

    def download(
        self,
        *,
        symbol: str,
        interval: str = "1m",
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
    ) -> pd.DataFrame:
        """Download full OHLCV history for a symbol in a date range.

        Args:
            symbol: Trading pair (e.g. BTCUSDT, BTC/USDT, BTC_USDT)
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            start_date: Start date (str YYYY-MM-DD or datetime). Default: 90 days ago.
            end_date: End date (str YYYY-MM-DD or datetime). Default: now.

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume,
            close_time, quote_volume, num_trades, taker_buy_volume,
            taker_buy_quote_volume.
            Sorted by timestamp, deduplicated.
        """
        binance_symbol = _to_binance_symbol(symbol)
        mapped_interval = _TF_MAP.get(interval, interval)

        # Parse dates
        start_dt = self._parse_date(start_date, default_days_ago=90)
        end_dt = self._parse_date(end_date, default_days_ago=0)

        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

        interval_ms = INTERVAL_MS.get(mapped_interval, 60_000)

        LOG.info(
            "Downloading %s %s: %s -> %s",
            binance_symbol, mapped_interval,
            start_dt.strftime("%Y-%m-%d %H:%M"),
            end_dt.strftime("%Y-%m-%d %H:%M"),
        )

        all_rows: list[dict[str, Any]] = []
        cursor_ms = start_ms
        chunk_count = 0

        while cursor_ms < end_ms:
            chunk = self._fetch_chunk(
                symbol=binance_symbol,
                interval=mapped_interval,
                start_ms=cursor_ms,
                end_ms=end_ms,
            )

            if not chunk:
                LOG.info(
                    "No more data at cursor %s. Total: %d bars, %d chunks.",
                    datetime.fromtimestamp(cursor_ms / 1000, tz=timezone.utc).isoformat(),
                    len(all_rows), chunk_count,
                )
                break

            all_rows.extend(chunk)
            chunk_count += 1

            # Advance cursor past the last bar's open_time
            last_ts = chunk[-1]["timestamp"]
            cursor_ms = last_ts + interval_ms

            # Progress logging
            if chunk_count % 10 == 0:
                pct = min(100.0, (cursor_ms - start_ms) / max(end_ms - start_ms, 1) * 100)
                LOG.info(
                    "  ... %d bars, %d chunks, %.1f%% complete",
                    len(all_rows), chunk_count, pct,
                )

            # Rate limit
            time.sleep(self.rate_limit_sleep)

        if not all_rows:
            LOG.warning("No data downloaded for %s", binance_symbol)
            return pd.DataFrame(
                columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "num_trades",
                    "taker_buy_volume", "taker_buy_quote_volume",
                ]
            )

        df = pd.DataFrame(all_rows)

        # Deduplicate by timestamp (open_time), sort deterministically
        df = (
            df.drop_duplicates(subset=["timestamp"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        # Convert ms timestamp to UTC datetime for the main column
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        LOG.info(
            "Download complete: %s %s -> %d bars, %d chunks, %d API requests",
            binance_symbol, mapped_interval,
            len(df), chunk_count, self._request_count,
        )

        return df

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(
        value: str | datetime | None,
        default_days_ago: int,
    ) -> datetime:
        """Parse a date string or datetime, with a default relative to now."""
        if value is None:
            return datetime.now(timezone.utc) - timedelta(days=default_days_ago)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        # String parsing: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {value!r}. Use YYYY-MM-DD format.")

    @property
    def request_count(self) -> int:
        """Total API requests made in this session."""
        return self._request_count


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    """CLI for downloading Binance historical data."""
    parser = argparse.ArgumentParser(
        description="Download Binance historical OHLCV data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.data.binance_downloader --symbol BTCUSDT --interval 1m --start 2024-01-01 --end 2024-03-01
  python -m src.data.binance_downloader --symbol ETHUSDT --interval 1h --start 2024-06-01 --end 2024-09-01
  python -m src.data.binance_downloader --symbol SOLUSDT --interval 5m --days 30
        """,
    )
    parser.add_argument("--symbol", required=True, help="Trading pair (e.g. BTCUSDT)")
    parser.add_argument("--interval", default="1m", help="Candle interval (default: 1m)")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD (default: 90 days ago)")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: now)")
    parser.add_argument("--days", type=int, default=None, help="Alternative to --start: download last N days")
    parser.add_argument("--output", default="data/binance", help="Output directory (default: data/binance)")
    parser.add_argument("--spot", action="store_true", help="Use spot endpoint instead of futures")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Resolve start date
    start_date = args.start
    if args.days is not None and start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    downloader = BinanceDownloader(use_futures=not args.spot)
    df = downloader.download(
        symbol=args.symbol,
        interval=args.interval,
        start_date=start_date,
        end_date=args.end,
    )

    if df.empty:
        LOG.error("No data to save.")
        sys.exit(1)

    # Save via local_store
    from src.data.local_store import LocalStore

    store = LocalStore(root=args.output)
    path = store.save(
        df=df,
        symbol=args.symbol,
        interval=args.interval,
    )
    LOG.info("Saved to: %s", path)
    LOG.info(
        "Summary: %d bars, %s -> %s",
        len(df),
        df["timestamp"].iloc[0].strftime("%Y-%m-%d %H:%M"),
        df["timestamp"].iloc[-1].strftime("%Y-%m-%d %H:%M"),
    )


if __name__ == "__main__":
    main()
