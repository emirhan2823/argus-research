"""Bybit OHLCV provider wrapper."""

from __future__ import annotations

from typing import Any

from Scripts.providers.base import INTERVAL_MS, OHLCVProvider, OHLCVRow, ProviderError

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"

_TF_MAP = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "D",
}


def _normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace("_", "").replace("-", "")


class BybitProvider(OHLCVProvider):
    name = "bybit"
    max_limit = 1000

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
        mapped_tf = _TF_MAP.get(timeframe)
        if mapped_tf is None:
            raise ProviderError(f"[{self.name}] unsupported timeframe: {timeframe}")

        params = {
            "category": "linear",
            "symbol": _normalize_symbol(symbol),
            "interval": mapped_tf,
            "start": int(start_ts),
            "end": int(max(start_ts, end_ts - 1)),
            "limit": int(max(1, min(limit, self.max_limit))),
        }
        payload = self._request_json(url=BYBIT_KLINE_URL, params=params)
        if not isinstance(payload, dict):
            raise ProviderError(f"[{self.name}] invalid payload type: {type(payload)}")

        ret_code = int(payload.get("retCode", -1))
        if ret_code != 0:
            raise ProviderError(f"[{self.name}] api_error retCode={ret_code} msg={payload.get('retMsg')}")

        result = payload.get("result", {})
        if not isinstance(result, dict):
            return []
        raw_rows = result.get("list", [])
        if not isinstance(raw_rows, list):
            return []

        interval_ms = INTERVAL_MS[timeframe]
        out: list[OHLCVRow] = []
        for item in raw_rows:
            # Bybit: [startTime, open, high, low, close, volume, turnover]
            if not isinstance(item, list) or len(item) < 6:
                continue
            ts_ms = int(item[0])
            out.append(
                OHLCVRow(
                    timestamp_ms=ts_ms,
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    close_time_ms=ts_ms + interval_ms - 1,
                    quote_volume=float(item[6]) if len(item) > 6 else None,
                )
            )
        return out
