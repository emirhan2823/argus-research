"""Exchange API clients for live OHLCV data.

Provides BinancePublicClient (no API key needed, read-only klines)
and BingXClient (authenticated, for future trading).

Both satisfy the ExchangeClient protocol in data_factory.py:
    fetch_ohlcv(symbol, timeframe, limit) -> list[list[Any]]
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Symbol normalizers
# ---------------------------------------------------------------------------

def _to_binance_symbol(symbol: str) -> str:
    """Convert ARGUS symbol format to Binance format.

    BTCUSDT -> BTCUSDT
    BTC/USDT -> BTCUSDT
    BTC_USDT -> BTCUSDT
    """
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


def _to_bingx_symbol(symbol: str) -> str:
    """Convert ARGUS symbol format to BingX format.

    BTCUSDT -> BTC-USDT
    BTC/USDT -> BTC-USDT
    BTC_USDT -> BTC-USDT
    """
    clean = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    # Common quote currencies
    for quote in ("USDT", "USDC", "BUSD", "USD"):
        if clean.endswith(quote) and len(clean) > len(quote):
            base = clean[: -len(quote)]
            return f"{base}-{quote}"
    return clean


_BINANCE_TF_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h",
    "12h": "12h", "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
}

_BINGX_TF_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h",
    "1d": "1d", "1w": "1w", "1M": "1M",
}


# ---------------------------------------------------------------------------
# Binance Public Client (no API key needed)
# ---------------------------------------------------------------------------

class BinancePublicClient:
    """Read-only Binance klines client. No API key required.

    Uses the public REST endpoint for candlestick data.
    Supports both spot and futures endpoints.
    """

    SPOT_URL = "https://api.binance.com/api/v3/klines"
    FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"

    def __init__(
        self,
        use_futures: bool = True,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = self.FUTURES_URL if use_futures else self.SPOT_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "ARGUS/2.5"})

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
    ) -> list[list[Any]]:
        """Fetch OHLCV klines from Binance.

        Returns list of [timestamp, open, high, low, close, volume].
        Timestamps are pandas-compatible UTC datetime strings.
        """
        binance_symbol = _to_binance_symbol(symbol)
        interval = _BINANCE_TF_MAP.get(timeframe, timeframe)
        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": min(limit, 1500),
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(
                    self.base_url, params=params, timeout=self.timeout,
                )
                resp.raise_for_status()
                raw = resp.json()

                if not isinstance(raw, list) or not raw:
                    LOG.warning(
                        "Binance returned empty/invalid for %s/%s (attempt %d)",
                        binance_symbol, interval, attempt,
                    )
                    return []

                rows: list[list[Any]] = []
                for k in raw:
                    # Binance kline: [open_time, open, high, low, close, volume, ...]
                    ts = datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc)
                    rows.append([
                        ts,
                        float(k[1]),  # open
                        float(k[2]),  # high
                        float(k[3]),  # low
                        float(k[4]),  # close
                        float(k[5]),  # volume
                    ])

                LOG.debug("Binance: %s %s -> %d bars", binance_symbol, interval, len(rows))
                return rows

            except requests.exceptions.RequestException as exc:
                LOG.warning(
                    "Binance request failed (attempt %d/%d): %s",
                    attempt, self.max_retries, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(1.0 * attempt)

        LOG.error("Binance: all %d attempts failed for %s", self.max_retries, binance_symbol)
        return []

    def fetch_ohlcv_history(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1500,
    ) -> list[list[Any]]:
        """Fetch historical klines with start/end time for backtesting data download."""
        binance_symbol = _to_binance_symbol(symbol)
        interval = _BINANCE_TF_MAP.get(timeframe, timeframe)
        params: dict[str, Any] = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": min(limit, 1500),
        }
        if start_time is not None:
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time is not None:
            params["endTime"] = int(end_time.timestamp() * 1000)

        try:
            resp = self._session.get(self.base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            raw = resp.json()
            if not isinstance(raw, list):
                return []
            rows: list[list[Any]] = []
            for k in raw:
                ts = datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc)
                rows.append([ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
            return rows
        except Exception as exc:
            LOG.error("Binance history fetch failed: %s", exc)
            return []

    def fetch_funding_rate(self, *, symbol: str) -> float | None:
        """Fetch latest funding rate for a futures symbol."""
        try:
            resp = self._session.get(
                "https://fapi.binance.com/fapi/v1/fundingRate",
                params={"symbol": _to_binance_symbol(symbol), "limit": 1},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list):
                return float(data[-1]["fundingRate"])
        except Exception:
            LOG.debug("Funding rate fetch failed for %s", symbol, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# BingX Client (authenticated, for future live trading)
# ---------------------------------------------------------------------------

class BingXClient:
    """BingX perpetual swap client.

    For now: read-only klines (public endpoint, no auth needed).
    Future: authenticated order placement with API key/secret.
    """

    BASE_URL = "https://open-api.bingx.com"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.getenv("BINGX_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINGX_API_SECRET", "")
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"X-BX-APIKEY": self.api_key})

    @property
    def is_authenticated(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
    ) -> list[list[Any]]:
        """Fetch klines from BingX (public endpoint)."""
        bingx_symbol = _to_bingx_symbol(symbol)
        interval = _BINGX_TF_MAP.get(timeframe, timeframe)

        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/klines",
                params={
                    "symbol": bingx_symbol,
                    "interval": interval,
                    "limit": min(limit, 1440),
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                LOG.warning("BingX error: %s", data.get("msg", "unknown"))
                return []

            klines = data.get("data", [])
            if not klines:
                return []

            rows: list[list[Any]] = []
            for k in klines:
                ts = datetime.fromtimestamp(int(k["time"]) / 1000, tz=timezone.utc)
                rows.append([
                    ts,
                    float(k["open"]),
                    float(k["high"]),
                    float(k["low"]),
                    float(k["close"]),
                    float(k["volume"]),
                ])

            LOG.debug("BingX: %s %s -> %d bars", bingx_symbol, interval, len(rows))
            return rows

        except Exception as exc:
            LOG.warning("BingX klines failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Historical data downloader (for backtesting)
# ---------------------------------------------------------------------------

class HistoricalDataDownloader:
    """Download bulk historical OHLCV data and save as parquet.

    Uses Binance public API with pagination to download months of data.
    """

    def __init__(self, client: BinancePublicClient | None = None) -> None:
        self.client = client or BinancePublicClient(use_futures=True)

    def download(
        self,
        *,
        symbol: str,
        timeframe: str = "1m",
        days: int = 90,
        output_dir: str = "data/time_machine",
    ) -> str:
        """Download historical data and save as parquet.

        Returns the path to the saved parquet file.
        """
        import pandas as pd
        from pathlib import Path

        end_time = datetime.now(timezone.utc)
        # Calculate start time
        from datetime import timedelta
        start_time = end_time - timedelta(days=days)

        LOG.info(
            "Downloading %s %s: %s -> %s (%d days)",
            symbol, timeframe,
            start_time.strftime("%Y-%m-%d"),
            end_time.strftime("%Y-%m-%d"),
            days,
        )

        all_rows: list[list[Any]] = []
        current_start = start_time

        while current_start < end_time:
            batch = self.client.fetch_ohlcv_history(
                symbol=symbol,
                timeframe=timeframe,
                start_time=current_start,
                end_time=end_time,
                limit=1500,
            )
            if not batch:
                LOG.warning("No more data for %s from %s", symbol, current_start)
                break

            all_rows.extend(batch)
            last_ts = batch[-1][0]
            if isinstance(last_ts, datetime):
                current_start = last_ts + timedelta(seconds=1)
            else:
                break

            LOG.info("  ... %d bars so far (last: %s)", len(all_rows), last_ts)
            time.sleep(0.3)  # Rate limit respect

        if not all_rows:
            LOG.error("No data downloaded for %s", symbol)
            return ""

        # Build DataFrame
        df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        # Save
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        from src.data.data_factory import normalize_symbol
        canonical = normalize_symbol(symbol)
        out_path = out_dir / f"{canonical}.parquet"
        df.to_parquet(out_path, index=False)

        LOG.info("Saved %d bars to %s", len(df), out_path)
        return str(out_path)

    def download_multiple(
        self,
        symbols: list[str],
        timeframe: str = "1m",
        days: int = 90,
        output_dir: str = "data/time_machine",
    ) -> list[str]:
        """Download data for multiple symbols."""
        paths = []
        for symbol in symbols:
            path = self.download(
                symbol=symbol,
                timeframe=timeframe,
                days=days,
                output_dir=output_dir,
            )
            if path:
                paths.append(path)
            time.sleep(1.0)  # Be nice between symbols
        return paths


# ---------------------------------------------------------------------------
# News downloader (for backtesting with sentiment)
# ---------------------------------------------------------------------------

class CryptoNewsDownloader:
    """Download crypto news headlines via RSS for sentiment analysis.

    Saves headlines with timestamps for backtesting with Hermes.
    """

    RSS_FEEDS = {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "theblock": "https://www.theblock.co/rss.xml",
    }

    def __init__(self) -> None:
        try:
            import feedparser  # noqa: F401
            self._has_feedparser = True
        except ImportError:
            self._has_feedparser = False

    def fetch_headlines(self, max_per_source: int = 50) -> list[dict]:
        """Fetch recent headlines from all configured RSS feeds."""
        if not self._has_feedparser:
            LOG.warning("feedparser not installed. Run: pip install feedparser")
            return []

        import feedparser

        all_headlines: list[dict] = []
        for source, url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_per_source]:
                    published = entry.get("published", entry.get("updated", ""))
                    all_headlines.append({
                        "source": source,
                        "title": entry.get("title", ""),
                        "published": published,
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", "")[:500],
                    })
                LOG.info("Fetched %d headlines from %s", min(len(feed.entries), max_per_source), source)
            except Exception as exc:
                LOG.warning("Failed to fetch %s: %s", source, exc)

        return all_headlines

    def save_headlines(self, output_path: str = "data/news/headlines.jsonl") -> int:
        """Fetch and save headlines to JSONL file."""
        import json
        from pathlib import Path

        headlines = self.fetch_headlines()
        if not headlines:
            return 0

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "a", encoding="utf-8") as f:
            for h in headlines:
                h["_fetched_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(h, ensure_ascii=False) + "\n")

        LOG.info("Saved %d headlines to %s", len(headlines), path)
        return len(headlines)
