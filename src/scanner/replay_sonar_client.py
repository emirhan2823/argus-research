"""Replay-backed market data client for SONAR backtests.

Provides Binance-like public methods used by SonarScanner:
- fetch_exchange_info(as_of=...)
- fetch_24h_tickers(as_of=...)
- fetch_ohlcv(..., now=...)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.local_store import LocalStore
from src.data.replay_loader import ReplayLoader


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ReplaySonarClient:
    """Replay data source that mimics public exchange discovery methods."""

    def __init__(self, *, root: str | Path = "data/binance", default_interval: str = "15m") -> None:
        self.root = Path(root)
        self.default_interval = str(default_interval)
        self._store = LocalStore(root=self.root)
        self._loader = ReplayLoader(root=self.root)
        self._listing_cache: dict[tuple[str, str], datetime | None] = {}

    def fetch_exchange_info(self, *, as_of: datetime | None = None) -> list[dict[str, Any]]:
        as_of_utc = _as_utc(as_of)
        symbols = self._store.list_symbols()
        out: list[dict[str, Any]] = []
        for sym in symbols:
            listed = self._first_seen_ts(sym, self.default_interval)
            if listed is None:
                continue
            if as_of_utc is not None and listed > as_of_utc:
                continue
            quote = "USDT" if sym.endswith("USDT") else ""
            base = sym[:-4] if quote == "USDT" and len(sym) > 4 else sym
            out.append(
                {
                    "symbol": sym,
                    "base_asset": base,
                    "quote_asset": quote,
                    "listing_ts": listed.isoformat(),
                }
            )
        return out

    def fetch_all_symbols(self, *, as_of: datetime | None = None) -> list[dict[str, Any]]:
        """Compatibility alias for clients exposing fetch_all_symbols()."""
        return self.fetch_exchange_info(as_of=as_of)

    def fetch_24h_tickers(self, *, as_of: datetime | None = None) -> list[dict[str, Any]]:
        as_of_utc = _as_utc(as_of)
        out: list[dict[str, Any]] = []
        for item in self.fetch_exchange_info(as_of=as_of_utc):
            symbol = str(item.get("symbol", ""))
            if not symbol:
                continue
            rows = self.fetch_ohlcv(
                symbol=symbol,
                timeframe=self.default_interval,
                limit=96,
                now=as_of_utc,
            )
            if len(rows) < 2:
                continue
            first_close = float(rows[0][4])
            last_close = float(rows[-1][4])
            quote_volume = 0.0
            for r in rows:
                close = float(r[4])
                volume = float(r[5])
                quote_volume += abs(close * volume)
            change_pct = 0.0
            if first_close > 0.0:
                change_pct = ((last_close - first_close) / first_close) * 100.0
            out.append(
                {
                    "symbol": symbol,
                    "volume_usdt": quote_volume,
                    "last_price": last_close,
                    "price_change_pct": change_pct,
                }
            )
        out.sort(key=lambda x: float(x.get("volume_usdt", 0.0)), reverse=True)
        return out

    def fetch_all_tickers(self, *, as_of: datetime | None = None) -> list[dict[str, Any]]:
        """Compatibility alias for clients exposing fetch_all_tickers()."""
        return self.fetch_24h_tickers(as_of=as_of)

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        now: datetime | None = None,
    ) -> list[list[Any]]:
        tf = str(timeframe or self.default_interval)
        try:
            anchor = _as_utc(now)
            return self._loader.load_ohlcv_rows(
                symbol=symbol,
                interval=tf,
                limit=max(1, int(limit)),
                now=pd.Timestamp(anchor) if anchor is not None else None,
            )
        except Exception:
            return []

    def _first_seen_ts(self, symbol: str, interval: str) -> datetime | None:
        key = (str(symbol).upper(), str(interval))
        if key in self._listing_cache:
            return self._listing_cache[key]

        candidate_intervals = [interval]
        for itv in self._store.list_intervals(symbol):
            if itv not in candidate_intervals:
                candidate_intervals.append(itv)

        first_seen: datetime | None = None
        for itv in candidate_intervals:
            months = self._store.list_months(symbol, itv)
            if not months:
                continue
            month = months[0]
            df = self._store.load_month(symbol, itv, month)
            if df.empty or "timestamp" not in df.columns:
                continue
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna()
            if ts.empty:
                continue
            min_ts = ts.min().to_pydatetime()
            if min_ts.tzinfo is None:
                min_ts = min_ts.replace(tzinfo=timezone.utc)
            else:
                min_ts = min_ts.astimezone(timezone.utc)
            if first_seen is None or min_ts < first_seen:
                first_seen = min_ts

        self._listing_cache[key] = first_seen
        return first_seen
