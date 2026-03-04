"""Kraken OHLCV provider wrapper."""

from __future__ import annotations

from typing import Any

from Scripts.providers.base import INTERVAL_MS, OHLCVProvider, OHLCVRow, ProviderError

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

_TF_MIN_MAP = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def _kraken_pair(symbol: str) -> str:
    clean = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    if clean.endswith("USDT"):
        base = clean[:-4]
        if base == "BTC":
            base = "XBT"
        return f"{base}USDT"
    return clean


class KrakenProvider(OHLCVProvider):
    name = "kraken"
    max_limit = 720

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        limit: int,
    ) -> list[OHLCVRow]:
        interval_min = _TF_MIN_MAP.get(timeframe)
        if interval_min is None:
            raise ProviderError(f"[{self.name}] unsupported timeframe: {timeframe}")

        params = {
            "pair": _kraken_pair(symbol),
            "interval": interval_min,
            "since": int(start_ts // 1000),
        }
        payload = self._request_json(url=KRAKEN_OHLC_URL, params=params)
        if not isinstance(payload, dict):
            raise ProviderError(f"[{self.name}] invalid payload type: {type(payload)}")

        errors = payload.get("error", [])
        if isinstance(errors, list) and errors:
            raise ProviderError(f"[{self.name}] api_error={errors}")

        result = payload.get("result", {})
        if not isinstance(result, dict):
            raise ProviderError(f"[{self.name}] invalid result type: {type(result)}")

        data_key = next((key for key in result.keys() if key != "last"), None)
        if data_key is None:
            return []
        raw_rows = result.get(data_key, [])
        if not isinstance(raw_rows, list):
            return []

        interval_ms = INTERVAL_MS[timeframe]
        out: list[OHLCVRow] = []
        for item in raw_rows:
            # Kraken: [time, open, high, low, close, vwap, volume, count]
            if not isinstance(item, list) or len(item) < 7:
                continue
            ts_ms = int(float(item[0]) * 1000)
            if ts_ms >= end_ts:
                continue
            out.append(
                OHLCVRow(
                    timestamp_ms=ts_ms,
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[6]),
                    close_time_ms=ts_ms + interval_ms - 1,
                    num_trades=int(float(item[7])) if len(item) > 7 else None,
                )
            )
            if len(out) >= min(limit, self.max_limit):
                break
        return out
