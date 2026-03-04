"""Binance OHLCV provider wrapper."""

from __future__ import annotations

from typing import Any

from Scripts.providers.base import INTERVAL_MS, OHLCVProvider, OHLCVRow, ProviderError

BINANCE_SPOT_URL = "https://api.binance.com/api/v3/klines"
BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"

_TF_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
}


def _normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


class BinanceProvider(OHLCVProvider):
    name = "binance"
    max_limit = 1000

    def __init__(self, *, use_spot: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.url = BINANCE_SPOT_URL if use_spot else BINANCE_FUTURES_URL

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        limit: int,
    ) -> list[OHLCVRow]:
        mapped_tf = _TF_MAP.get(timeframe)
        if mapped_tf is None:
            raise ProviderError(f"[{self.name}] unsupported timeframe: {timeframe}")
        params = {
            "symbol": _normalize_symbol(symbol),
            "interval": mapped_tf,
            "startTime": int(start_ts),
            "endTime": int(max(start_ts, end_ts - 1)),
            "limit": int(max(1, min(limit, self.max_limit))),
        }
        payload = self._request_json(url=self.url, params=params)
        if not isinstance(payload, list):
            raise ProviderError(f"[{self.name}] invalid payload type: {type(payload)}")

        rows: list[OHLCVRow] = []
        interval_ms = INTERVAL_MS[timeframe]
        for item in payload:
            if not isinstance(item, list) or len(item) < 6:
                continue
            ts_ms = int(item[0])
            close_time_ms = int(item[6]) if len(item) > 6 else ts_ms + interval_ms - 1
            quote_volume = float(item[7]) if len(item) > 7 else None
            num_trades = int(item[8]) if len(item) > 8 else None
            taker_buy_volume = float(item[9]) if len(item) > 9 else None
            taker_buy_quote_volume = float(item[10]) if len(item) > 10 else None
            rows.append(
                OHLCVRow(
                    timestamp_ms=ts_ms,
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    close_time_ms=close_time_ms,
                    quote_volume=quote_volume,
                    num_trades=num_trades,
                    taker_buy_volume=taker_buy_volume,
                    taker_buy_quote_volume=taker_buy_quote_volume,
                )
            )
        return rows
