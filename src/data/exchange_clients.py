"""Exchange API clients for live OHLCV data and order execution.

Provides:
  - BinancePublicClient (no API key needed, read-only klines)
  - BingXClient (read-only klines, public endpoint)
  - BingXPublicClient (ticker, depth, funding rate via public endpoints)
  - BingXPrivateClient (HMAC-SHA256 authenticated order placement, implements BrokerAdapter)

ExchangeClient protocol: fetch_ohlcv(symbol, timeframe, limit) -> list[list[Any]]
BrokerAdapter protocol: place_order(*, symbol, side, size, order_type, urgency) -> dict
"""

from __future__ import annotations

import hashlib
import hmac
from http.client import RemoteDisconnected
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

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

    Features:
        - In-memory TTL cache to avoid redundant API calls within a cycle
        - Inter-request rate limiter (100ms min between calls)
    """

    SPOT_URL = "https://api.binance.com/api/v3/klines"
    FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"

    # Cache settings
    DEFAULT_CACHE_TTL = 55.0   # seconds (just under 1m candle interval)
    MAX_CACHE_ENTRIES = 100
    MIN_REQUEST_INTERVAL = 0.1  # 100ms between API calls
    DEFAULT_IDLE_REFRESH_SECONDS = 180.0
    DEFAULT_BREAKER_FAILURES = 5
    DEFAULT_BREAKER_COOLDOWN_SECONDS = 60.0

    def __init__(
        self,
        use_futures: bool = True,
        timeout: float = 10.0,
        max_retries: int = 3,
        cache_ttl: float | None = None,
        idle_refresh_seconds: float = DEFAULT_IDLE_REFRESH_SECONDS,
        breaker_failures: int = DEFAULT_BREAKER_FAILURES,
        breaker_cooldown_seconds: float = DEFAULT_BREAKER_COOLDOWN_SECONDS,
    ) -> None:
        self.base_url = self.FUTURES_URL if use_futures else self.SPOT_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl if cache_ttl is not None else self.DEFAULT_CACHE_TTL
        self.idle_refresh_seconds = max(float(idle_refresh_seconds), 1.0)
        self.breaker_failures = max(int(breaker_failures), 1)
        self.breaker_cooldown_seconds = max(float(breaker_cooldown_seconds), 1.0)
        self._session = self._new_session()
        # TTL cache: {(symbol, timeframe): (timestamp, rows)}
        self._cache: dict[tuple[str, str], tuple[float, list]] = {}
        self._last_request_time: float = 0.0
        self._request_count: int = 0
        self._last_activity_time: float = time.monotonic()
        self._consecutive_failures: int = 0
        self._breaker_open_until: float = 0.0

    @staticmethod
    def _new_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": "ARGUS/2.5"})
        return session

    def _refresh_session(self, *, reason: str) -> None:
        try:
            self._session.close()
        except Exception:
            pass
        self._session = self._new_session()
        LOG.info("Binance session refreshed: reason=%s", reason)

    def _maybe_refresh_session(self, *, now_mono: float) -> None:
        idle = now_mono - self._last_activity_time
        if idle >= self.idle_refresh_seconds:
            self._refresh_session(reason=f"idle_{idle:.1f}s")

    def _is_breaker_open(self, *, now_mono: float) -> bool:
        if now_mono < self._breaker_open_until:
            remaining = self._breaker_open_until - now_mono
            LOG.warning(
                "Binance circuit breaker OPEN: remaining=%.2fs failures=%d",
                remaining,
                self._consecutive_failures,
            )
            return True

        if self._breaker_open_until > 0.0 and self._consecutive_failures >= self.breaker_failures:
            LOG.info("Binance circuit breaker CLOSED: cooldown elapsed")
            self._consecutive_failures = 0
            self._breaker_open_until = 0.0
        return False

    def _record_failure(self, *, now_mono: float, attempt: int, exc: Exception) -> None:
        self._consecutive_failures += 1
        LOG.warning(
            "Binance request failed: attempt=%d/%d failures=%d error=%s",
            attempt,
            self.max_retries,
            self._consecutive_failures,
            exc,
        )
        self._refresh_session(reason="request_error")

        if self._consecutive_failures >= self.breaker_failures:
            self._breaker_open_until = now_mono + self.breaker_cooldown_seconds
            LOG.error(
                "Binance circuit breaker OPENED: failures=%d cooldown=%.1fs",
                self._consecutive_failures,
                self.breaker_cooldown_seconds,
            )

    def _record_success(self) -> None:
        if self._consecutive_failures > 0:
            LOG.info("Binance request recovered after %d failures", self._consecutive_failures)
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    @staticmethod
    def _backoff_delay(*, attempt: int) -> float:
        return min(30.0, (2 ** int(attempt)) + random.uniform(0.0, 1.0))

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
        Uses TTL cache to avoid redundant API calls within a cycle.
        """
        binance_symbol = _to_binance_symbol(symbol)
        interval = _BINANCE_TF_MAP.get(timeframe, timeframe)
        cache_key = (binance_symbol, interval)

        # Cache hit check
        now_mono = time.monotonic()
        self._maybe_refresh_session(now_mono=now_mono)
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_at, cached_rows = cached
            if (now_mono - cached_at) < self.cache_ttl:
                LOG.debug("Cache HIT %s/%s (%d bars)", binance_symbol, interval, len(cached_rows))
                return cached_rows

        if self._is_breaker_open(now_mono=now_mono):
            return []

        # Inter-request rate limiter
        elapsed = now_mono - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": min(limit, 1500),
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                self._last_request_time = time.monotonic()
                self._last_activity_time = self._last_request_time
                self._request_count += 1
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
                    self._record_failure(
                        now_mono=time.monotonic(),
                        attempt=attempt,
                        exc=ValueError("empty_or_invalid_response"),
                    )
                    if attempt < self.max_retries:
                        delay = self._backoff_delay(attempt=attempt)
                        LOG.warning(
                            "Binance retry backoff: attempt=%d sleep=%.2fs",
                            attempt,
                            delay,
                        )
                        time.sleep(delay)
                    continue

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

                # Store in cache
                self._cache[cache_key] = (time.monotonic(), rows)
                # LRU eviction if cache is too large
                if len(self._cache) > self.MAX_CACHE_ENTRIES:
                    oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
                    del self._cache[oldest_key]

                self._record_success()
                return rows

            except (requests.exceptions.RequestException, RemoteDisconnected) as exc:
                self._record_failure(
                    now_mono=time.monotonic(),
                    attempt=attempt,
                    exc=exc,
                )
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt=attempt)
                    LOG.warning(
                        "Binance retry backoff: attempt=%d sleep=%.2fs",
                        attempt,
                        delay,
                    )
                    time.sleep(delay)

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

    def fetch_exchange_info(self) -> list[dict[str, Any]]:
        """Fetch all USDT-margined perpetual symbols with status=TRADING.

        Single call to /fapi/v1/exchangeInfo (public, no API key).
        Returns list of {symbol, base_asset, quote_asset}.
        """
        try:
            resp = self._session.get(
                "https://fapi.binance.com/fapi/v1/exchangeInfo",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            symbols: list[dict[str, Any]] = []
            for s in data.get("symbols", []):
                if (
                    s.get("status") == "TRADING"
                    and s.get("quoteAsset") == "USDT"
                    and s.get("contractType") == "PERPETUAL"
                ):
                    symbols.append({
                        "symbol": str(s["symbol"]),
                        "base_asset": str(s["baseAsset"]),
                        "quote_asset": str(s["quoteAsset"]),
                    })
            return symbols
        except Exception as exc:
            LOG.warning("Binance exchangeInfo failed: %s", exc)
            return []

    def fetch_24h_tickers(self) -> list[dict[str, Any]]:
        """Fetch 24h ticker stats for ALL futures symbols in one call.

        Single call to /fapi/v1/ticker/24hr (public, no API key).
        Returns list of {symbol, volume_usdt, last_price, price_change_pct}.
        """
        try:
            resp = self._session.get(
                "https://fapi.binance.com/fapi/v1/ticker/24hr",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            raw = resp.json()
            tickers: list[dict[str, Any]] = []
            for t in raw:
                if not isinstance(t, dict):
                    continue
                tickers.append({
                    "symbol": str(t.get("symbol", "")),
                    "volume_usdt": float(t.get("quoteVolume", 0)),
                    "last_price": float(t.get("lastPrice", 0)),
                    "price_change_pct": float(t.get("priceChangePercent", 0)),
                })
            return tickers
        except Exception as exc:
            LOG.warning("Binance 24h tickers failed: %s", exc)
            return []


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
# BingX Public Client (extended: ticker, depth, funding)
# ---------------------------------------------------------------------------

class BingXPublicClient:
    """Extended BingX public client with ticker, depth, and funding rate.

    Satisfies ExchangeClient protocol (fetch_ohlcv) and adds market data methods.
    """

    BASE_URL = "https://open-api.bingx.com"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "ARGUS/2.5"})

    def fetch_ohlcv(
        self, *, symbol: str, timeframe: str = "1m", limit: int = 500,
    ) -> list[list[Any]]:
        """Fetch klines from BingX (public endpoint)."""
        bingx_symbol = _to_bingx_symbol(symbol)
        interval = _BINGX_TF_MAP.get(timeframe, timeframe)
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/klines",
                params={"symbol": bingx_symbol, "interval": interval, "limit": min(limit, 1440)},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                LOG.warning("BingX klines error: %s", data.get("msg", "unknown"))
                return []
            klines = data.get("data", [])
            rows: list[list[Any]] = []
            for k in klines:
                ts = datetime.fromtimestamp(int(k["time"]) / 1000, tz=timezone.utc)
                rows.append([ts, float(k["open"]), float(k["high"]), float(k["low"]), float(k["close"]), float(k["volume"])])
            return rows
        except Exception as exc:
            LOG.warning("BingX klines failed: %s", exc)
            return []

    def fetch_ticker(self, *, symbol: str) -> dict[str, Any] | None:
        """Fetch 24h ticker stats for a symbol."""
        bingx_symbol = _to_bingx_symbol(symbol)
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/ticker",
                params={"symbol": bingx_symbol},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                return None
            ticker = data.get("data", {})
            return {
                "symbol": symbol,
                "last_price": float(ticker.get("lastPrice", 0)),
                "bid": float(ticker.get("bidPrice", 0)),
                "ask": float(ticker.get("askPrice", 0)),
                "high_24h": float(ticker.get("highPrice", 0)),
                "low_24h": float(ticker.get("lowPrice", 0)),
                "volume_24h": float(ticker.get("volume", 0)),
                "price_change_pct": float(ticker.get("priceChangePercent", 0)),
            }
        except Exception as exc:
            LOG.warning("BingX ticker failed for %s: %s", symbol, exc)
            return None

    def fetch_depth(self, *, symbol: str, limit: int = 20) -> dict[str, Any] | None:
        """Fetch order book snapshot."""
        bingx_symbol = _to_bingx_symbol(symbol)
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/depth",
                params={"symbol": bingx_symbol, "limit": min(limit, 100)},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                return None
            book = data.get("data", {})
            return {
                "bids": [[float(p), float(q)] for p, q in (book.get("bids") or [])],
                "asks": [[float(p), float(q)] for p, q in (book.get("asks") or [])],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            LOG.warning("BingX depth failed for %s: %s", symbol, exc)
            return None

    def fetch_funding_rate(self, *, symbol: str) -> float | None:
        """Fetch current funding rate for perpetual swap."""
        bingx_symbol = _to_bingx_symbol(symbol)
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/premiumIndex",
                params={"symbol": bingx_symbol},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                return None
            info = data.get("data", {})
            return float(info.get("lastFundingRate", 0))
        except Exception as exc:
            LOG.warning("BingX funding rate failed for %s: %s", symbol, exc)
            return None

    def fetch_all_symbols(self) -> list[dict[str, Any]]:
        """Fetch all USDT-M perpetual swap contracts from BingX.

        Single call to /openApi/swap/v2/quote/contracts (public).
        Returns list of {symbol, base_asset, quote_asset}.
        """
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/contracts",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                LOG.warning("BingX contracts error: %s", data.get("msg", "unknown"))
                return []
            contracts = data.get("data", [])
            symbols: list[dict[str, Any]] = []
            for c in contracts:
                if not isinstance(c, dict):
                    continue
                raw_symbol = str(c.get("symbol", ""))
                # BingX uses BTC-USDT format; normalize to BTCUSDT
                normalized = raw_symbol.replace("-", "")
                if normalized.endswith("USDT"):
                    symbols.append({
                        "symbol": normalized,
                        "base_asset": normalized.replace("USDT", ""),
                        "quote_asset": "USDT",
                    })
            return symbols
        except Exception as exc:
            LOG.warning("BingX contracts fetch failed: %s", exc)
            return []

    def fetch_all_tickers(self) -> list[dict[str, Any]]:
        """Fetch 24h ticker stats for ALL BingX swap symbols in one call.

        Single call to /openApi/swap/v2/quote/ticker (public).
        Returns list of {symbol, volume_usdt, last_price}.
        """
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/openApi/swap/v2/quote/ticker",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                LOG.warning("BingX tickers error: %s", data.get("msg", "unknown"))
                return []
            tickers_raw = data.get("data", [])
            tickers: list[dict[str, Any]] = []
            for t in tickers_raw:
                if not isinstance(t, dict):
                    continue
                raw_symbol = str(t.get("symbol", ""))
                normalized = raw_symbol.replace("-", "")
                tickers.append({
                    "symbol": normalized,
                    "volume_usdt": float(t.get("quoteVolume", t.get("volume", 0))),
                    "last_price": float(t.get("lastPrice", 0)),
                })
            return tickers
        except Exception as exc:
            LOG.warning("BingX all tickers failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# BingX Private Client (authenticated, implements BrokerAdapter protocol)
# ---------------------------------------------------------------------------

# Order type mapping: ARGUS → BingX
_BINGX_ORDER_TYPE_MAP: dict[str, str] = {
    "market": "MARKET",
    "limit": "LIMIT",
    "aggressive_limit": "LIMIT",
    "passive_limit": "LIMIT",
    "EMERGENCY": "MARKET",
}

# BingX trade side mapping
_BINGX_SIDE_MAP: dict[str, str] = {
    "long": "BUY",
    "short": "SELL",
    "buy": "BUY",
    "sell": "SELL",
    "BUY": "BUY",
    "SELL": "SELL",
}


class BingXPrivateClient:
    """Authenticated BingX perpetual swap client.

    Implements the BrokerAdapter protocol for order placement.
    Uses HMAC-SHA256 request signing per BingX API spec:
        sign = HMAC-SHA256(secret, sorted_param_string)
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
        self._session.headers.update({
            "User-Agent": "ARGUS/2.5",
            "X-BX-APIKEY": self.api_key,
        })

    @property
    def is_authenticated(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _sign(self, params: dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for BingX API.

        BingX signing: sort params alphabetically, build query string,
        HMAC-SHA256 with secret key.
        """
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        param_string = urlencode(sorted_params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            param_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a signed request to BingX API."""
        if not self.is_authenticated:
            raise RuntimeError("BingXPrivateClient requires API key and secret")

        params = params or {}
        params["timestamp"] = str(int(time.time() * 1000))
        params["signature"] = self._sign(params)

        url = f"{self.BASE_URL}{path}"
        headers = {
            "X-BX-APIKEY": self.api_key,
            "X-BX-SIGN": params.pop("signature"),
            "X-BX-TIMESTAMP": params.pop("timestamp"),
        }
        # Re-add timestamp to params since BingX expects it there too
        params["timestamp"] = headers["X-BX-TIMESTAMP"]

        try:
            if method.upper() == "GET":
                resp = self._session.get(url, params=params, headers=headers, timeout=self.timeout)
            else:
                resp = self._session.post(url, params=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                LOG.error("BingX API error: code=%s msg=%s", data.get("code"), data.get("msg"))
            return data
        except requests.exceptions.RequestException as exc:
            LOG.error("BingX request failed: %s %s -> %s", method, path, exc)
            return {"code": -1, "msg": str(exc)}

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market",
        urgency: str = "NORMAL",
        price: float | None = None,
        leverage: int | None = None,
    ) -> dict[str, Any]:
        """Place a perpetual swap order on BingX.

        Satisfies BrokerAdapter protocol.
        Maps ARGUS order types to BingX: market/EMERGENCY → MARKET, limit variants → LIMIT.
        """
        bingx_symbol = _to_bingx_symbol(symbol)
        bingx_side = _BINGX_SIDE_MAP.get(side, "BUY")
        bingx_type = _BINGX_ORDER_TYPE_MAP.get(order_type, "MARKET")

        # Set leverage if specified
        if leverage is not None:
            self._set_leverage(symbol=bingx_symbol, leverage=leverage)

        params: dict[str, Any] = {
            "symbol": bingx_symbol,
            "side": bingx_side,
            "type": bingx_type,
            "quantity": str(round(size, 8)),
            "positionSide": "LONG" if bingx_side == "BUY" else "SHORT",
        }
        if bingx_type == "LIMIT" and price is not None:
            params["price"] = str(round(price, 8))

        LOG.info(
            "BingX order: %s %s %s qty=%s type=%s urgency=%s",
            bingx_side, bingx_symbol, side, size, bingx_type, urgency,
        )

        data = self._signed_request("POST", "/openApi/swap/v3/trade/order", params)

        if data.get("code") == 0:
            order_info = data.get("data", {})
            return {
                "success": True,
                "order_id": str(order_info.get("orderId", "")),
                "symbol": symbol,
                "side": side,
                "size": size,
                "type": bingx_type,
                "status": order_info.get("status", "NEW"),
            }
        return {
            "success": False,
            "error": data.get("msg", "unknown"),
            "code": data.get("code"),
        }

    def cancel_order(self, *, symbol: str, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        params = {
            "symbol": _to_bingx_symbol(symbol),
            "orderId": order_id,
        }
        data = self._signed_request("POST", "/openApi/swap/v3/trade/cancel", params)
        return {
            "success": data.get("code") == 0,
            "order_id": order_id,
            "msg": data.get("msg", ""),
        }

    def get_position(self, *, symbol: str) -> dict[str, Any] | None:
        """Get current position for a symbol."""
        params = {"symbol": _to_bingx_symbol(symbol)}
        data = self._signed_request("GET", "/openApi/swap/v2/user/positions", params)
        if data.get("code") != 0:
            return None
        positions = data.get("data", [])
        if not positions:
            return None
        # Return first non-zero position
        for pos in positions:
            size = float(pos.get("positionAmt", 0))
            if abs(size) > 0:
                return {
                    "symbol": symbol,
                    "side": "long" if size > 0 else "short",
                    "size": abs(size),
                    "entry_price": float(pos.get("avgPrice", 0)),
                    "unrealized_pnl": float(pos.get("unrealizedProfit", 0)),
                    "leverage": int(pos.get("leverage", 1)),
                    "margin_type": pos.get("marginType", "cross"),
                }
        return None

    def get_balance(self) -> dict[str, Any] | None:
        """Get account balance."""
        data = self._signed_request("GET", "/openApi/swap/v2/user/balance", {})
        if data.get("code") != 0:
            return None
        balance = data.get("data", {}).get("balance", {})
        return {
            "total": float(balance.get("balance", 0)),
            "available": float(balance.get("availableMargin", 0)),
            "unrealized_pnl": float(balance.get("unrealizedProfit", 0)),
            "used_margin": float(balance.get("usedMargin", 0)),
        }

    def _set_leverage(self, *, symbol: str, leverage: int) -> None:
        """Set leverage for a symbol (capped 1-125)."""
        leverage = max(1, min(125, leverage))
        params = {
            "symbol": symbol,
            "side": "BOTH",
            "leverage": str(leverage),
        }
        data = self._signed_request("POST", "/openApi/swap/v2/trade/leverage", params)
        if data.get("code") == 0:
            LOG.info("BingX leverage set: %s -> %dx", symbol, leverage)
        else:
            LOG.warning("BingX leverage set failed: %s -> %s", symbol, data.get("msg"))


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
            if not isinstance(batch, list) or not batch:
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
                    summary_text = str(entry.get("summary", "") or "")
                    all_headlines.append({
                        "source": source,
                        "title": entry.get("title", ""),
                        "published": published,
                        "link": entry.get("link", ""),
                        "summary": summary_text[:500],
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
