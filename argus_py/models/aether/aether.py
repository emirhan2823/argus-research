from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from .data_sources import AetherDataSources


class MacroRegime(Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"


@dataclass
class AetherComponents:
    fear_greed: float
    btc_dominance: float
    total_mcap_change: float
    dxy_trend: str
    funding_rate: float


@dataclass
class AetherResult:
    regime: MacroRegime
    score: float
    components: AetherComponents
    reasoning: str


class AetherEngine:
    """Crypto macro environment detector."""

    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cache: Optional[AetherResult] = None
        self._cache_time: float = 0.0
        self._sources = AetherDataSources()

    async def evaluate(self, force_refresh: bool = False) -> AetherResult:
        """Main evaluation - returns cached if fresh."""
        now = time.time()
        if (
            not force_refresh
            and self._cache is not None
            and (now - self._cache_time) < self.cache_ttl
        ):
            return self._cache

        components = await self._collect_components()
        score = self._calculate_score(components)
        regime = self._determine_regime(score)
        reasoning = self._build_reasoning(components, score, regime)

        result = AetherResult(
            regime=regime,
            score=score,
            components=components,
            reasoning=reasoning,
        )

        self._cache = result
        self._cache_time = now
        return result

    async def _collect_components(self) -> AetherComponents:
        fear_greed_task = asyncio.create_task(self._safe_call(self._fetch_fear_greed, 50))
        global_task = asyncio.create_task(self._safe_call(self._fetch_global_metrics, {}))
        dxy_task = asyncio.create_task(self._safe_call(self._sources.fetch_dxy_snapshot, {"value": 0.0, "trend": "FLAT"}))
        funding_task = asyncio.create_task(self._safe_call(self._fetch_funding_rate, 0.0))

        fear_greed, global_data, dxy, funding_rate = await asyncio.gather(
            fear_greed_task,
            global_task,
            dxy_task,
            funding_task,
        )

        btc_dominance = 50.0
        total_mcap_change = 0.0

        if isinstance(global_data, dict):
            market_cap_pct = global_data.get("market_cap_percentage", {}) or {}
            btc_dominance = float(market_cap_pct.get("btc", 50.0))
            total_mcap_change = float(global_data.get("market_cap_change_percentage_24h_usd", 0.0))

        dxy_trend = "FLAT"
        if isinstance(dxy, dict):
            dxy_trend = str(dxy.get("trend", "FLAT")).upper()
            if dxy_trend not in {"UP", "DOWN", "FLAT"}:
                dxy_trend = "FLAT"

        return AetherComponents(
            fear_greed=float(fear_greed),
            btc_dominance=btc_dominance,
            total_mcap_change=total_mcap_change,
            dxy_trend=dxy_trend,
            funding_rate=float(funding_rate),
        )

    async def _safe_call(self, fn, fallback):
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception:
            return fallback

    async def _fetch_fear_greed(self) -> int:
        """Fetch from Alternative.me API."""
        return await self._sources.fetch_fear_greed()

    async def _fetch_global_metrics(self) -> Dict:
        """Fetch from CoinGecko."""
        return await self._sources.fetch_global_metrics()

    async def _fetch_dxy(self) -> float:
        """Fetch DXY from Yahoo Finance."""
        snapshot = await self._sources.fetch_dxy_snapshot()
        return float(snapshot["value"])

    async def _fetch_funding_rate(self, symbol: str = "BTCUSDT") -> float:
        """Fetch from Binance public API."""
        return await self._sources.fetch_funding_rate(symbol=symbol)

    def _calculate_score(self, components: AetherComponents) -> float:
        score = 50.0

        # Fear & Greed (30%)
        if components.fear_greed < 25:
            score += 15
        elif components.fear_greed > 75:
            score -= 10
        elif components.fear_greed > 50:
            score += 5

        # BTC Dominance (20%)
        if components.btc_dominance > 50:
            score -= 5
        elif components.btc_dominance < 40:
            score += 10

        # Total Market Cap Change (20%)
        if components.total_mcap_change > 3:
            score += 10
        elif components.total_mcap_change < -3:
            score -= 10

        # DXY Trend (15%)
        if components.dxy_trend == "DOWN":
            score += 8
        elif components.dxy_trend == "UP":
            score -= 5

        # Funding Rate (15%)
        if components.funding_rate > 0.001:
            score -= 5
        elif components.funding_rate < -0.001:
            score += 8

        return max(0.0, min(100.0, score))

    def _determine_regime(self, score: float) -> MacroRegime:
        if score >= 60:
            return MacroRegime.RISK_ON
        if score <= 40:
            return MacroRegime.RISK_OFF
        return MacroRegime.NEUTRAL

    def _build_reasoning(self, components: AetherComponents, score: float, regime: MacroRegime) -> str:
        return (
            f"Regime={regime.value} Score={score:.1f} | "
            f"FG={components.fear_greed:.1f}, BTC.DOM={components.btc_dominance:.1f}, "
            f"MCAP24h={components.total_mcap_change:.2f}%, DXY={components.dxy_trend}, "
            f"Funding={components.funding_rate:.5f}"
        )
