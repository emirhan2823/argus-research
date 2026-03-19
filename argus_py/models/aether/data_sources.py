from __future__ import annotations

import asyncio
import time
from typing import Dict

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency in some environments
    httpx = None

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - optional dependency in some environments
    yf = None


class AetherDataSources:
    """External data adapters for Aether-C."""

    def __init__(self, min_coingecko_interval: float = 6.0, timeout: float = 10.0):
        self.min_coingecko_interval = min_coingecko_interval
        self.timeout = timeout
        self._coingecko_last_call = 0.0

    async def fetch_fear_greed(self) -> int:
        if httpx is None:
            raise RuntimeError("httpx is not installed")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get("https://api.alternative.me/fng/?limit=1")
            response.raise_for_status()
            payload = response.json()
            return int(payload["data"][0]["value"])

    async def fetch_global_metrics(self) -> Dict:
        if httpx is None:
            raise RuntimeError("httpx is not installed")

        await self._respect_coingecko_rate_limit()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get("https://api.coingecko.com/api/v3/global")
            response.raise_for_status()
            payload = response.json()
            return payload["data"]

    async def fetch_dxy_snapshot(self) -> Dict[str, float | str]:
        if yf is None:
            raise RuntimeError("yfinance is not installed")

        ticker = yf.Ticker("DX-Y.NYB")
        hist = await asyncio.to_thread(ticker.history, period="5d")

        if hist is None or hist.empty or "Close" not in hist:
            raise RuntimeError("No DXY data returned")

        closes = hist["Close"].dropna()
        if closes.empty:
            raise RuntimeError("No DXY close values returned")

        latest = float(closes.iloc[-1])
        if len(closes) < 2:
            trend = "FLAT"
        else:
            prev = float(closes.iloc[0])
            if latest > prev:
                trend = "UP"
            elif latest < prev:
                trend = "DOWN"
            else:
                trend = "FLAT"

        return {"value": latest, "trend": trend}

    async def fetch_funding_rate(self, symbol: str = "BTCUSDT") -> float:
        if httpx is None:
            raise RuntimeError("httpx is not installed")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                "https://fapi.binance.com/fapi/v1/fundingRate",
                params={"symbol": symbol, "limit": 1},
            )
            response.raise_for_status()
            payload = response.json()

        if not payload:
            raise RuntimeError("No funding rate data returned")

        return float(payload[0]["fundingRate"])

    async def _respect_coingecko_rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._coingecko_last_call
        if elapsed < self.min_coingecko_interval:
            await asyncio.sleep(self.min_coingecko_interval - elapsed)
        self._coingecko_last_call = time.time()
