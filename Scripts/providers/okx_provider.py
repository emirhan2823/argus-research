"""OKX OHLCV provider wrapper."""

from __future__ import annotations

from typing import Any

from Scripts.providers.base import INTERVAL_MS, OHLCVProvider, OHLCVRow, ProviderError

OKX_CANDLES_URL = "https://www.okx.com/api/v5/market/history-candles"

_TF_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
}


def _okx_symbol(symbol: str) -> str:
    clean = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    if clean.endswith("USDT"):
        return f"{clean[:-4]}-USDT"
    return clean


class OkxProvider(OHLCVProvider):
    name = "okx"
    max_limit = 100

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
        bar = _TF_MAP.get(timeframe)
        if bar is None:
            raise ProviderError(f"[{self.name}] unsupported timeframe: {timeframe}")

        params = {
            "instId": _okx_symbol(symbol),
            "bar": bar,
            "after": str(int(start_ts)),
            "before": str(int(end_ts)),
            "limit": str(int(max(1, min(limit, self.max_limit)))),
        }
        payload = self._request_json(url=OKX_CANDLES_URL, params=params)
        if not isinstance(payload, dict):
            raise ProviderError(f"[{self.name}] invalid payload type: {type(payload)}")
        code = str(payload.get("code", ""))
        if code not in {"0", ""}:
            raise ProviderError(f"[{self.name}] api_error code={code} msg={payload.get('msg')}")
        raw_rows = payload.get("data", [])
        if not isinstance(raw_rows, list):
            raise ProviderError(f"[{self.name}] invalid data field type: {type(raw_rows)}")

        interval_ms = INTERVAL_MS[timeframe]
        rows: list[OHLCVRow] = []
        for item in raw_rows:
            if not isinstance(item, list) or len(item) < 6:
                continue
            ts_ms = int(item[0])
            # OKX format: [ts,o,h,l,c,vol,volCcy,volCcyQuote,confirm]
            quote_volume = float(item[7]) if len(item) > 7 else None
            rows.append(
                OHLCVRow(
                    timestamp_ms=ts_ms,
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    close_time_ms=ts_ms + interval_ms - 1,
                    quote_volume=quote_volume,
                )
            )
        return rows
