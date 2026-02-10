from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .data_sources import AetherDataSources


class MacroRegimeC(str, Enum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


@dataclass(frozen=True)
class AetherCInputs:
    fear_greed: float
    btc_dominance: float
    total_market_cap_change_24h: float
    dxy_trend: str


@dataclass(frozen=True)
class AetherCResult:
    score: float
    regime: MacroRegimeC
    reason: str
    components: dict[str, float]


class AetherCEngine:
    """Macro composite model (Fear&Greed + Dominance + MCap + DXY)."""

    def __init__(self, data_sources: Optional[AetherDataSources] = None) -> None:
        self.sources = data_sources or AetherDataSources()

    async def collect_inputs(self) -> AetherCInputs:
        fg = await self.sources.fetch_fear_greed()
        global_data = await self.sources.fetch_global_metrics()
        dxy = await self.sources.fetch_dxy_snapshot()

        btc_dom = float((global_data.get("market_cap_percentage") or {}).get("btc", 50.0))
        mcap_change = float(global_data.get("market_cap_change_percentage_24h_usd", 0.0))
        dxy_trend = str(dxy.get("trend", "FLAT")).upper()

        return AetherCInputs(
            fear_greed=float(fg),
            btc_dominance=btc_dom,
            total_market_cap_change_24h=mcap_change,
            dxy_trend=dxy_trend,
        )

    def evaluate(self, x: AetherCInputs) -> AetherCResult:
        c_fg = self._score_fg(x.fear_greed)
        c_dom = self._score_dominance(x.btc_dominance)
        c_mcap = self._score_mcap(x.total_market_cap_change_24h)
        c_dxy = self._score_dxy(x.dxy_trend)

        score = 0.35 * c_fg + 0.25 * c_dom + 0.25 * c_mcap + 0.15 * c_dxy
        score = float(max(0.0, min(100.0, score)))

        if score >= 62.0:
            regime = MacroRegimeC.RISK_ON
        elif score <= 40.0:
            regime = MacroRegimeC.RISK_OFF
        else:
            regime = MacroRegimeC.NEUTRAL

        reason = (
            f"AETHER-C score={score:.1f} regime={regime.value} "
            f"| fg={x.fear_greed:.1f} dom={x.btc_dominance:.1f} "
            f"mcap24h={x.total_market_cap_change_24h:.2f}% dxy={x.dxy_trend}"
        )

        return AetherCResult(
            score=score,
            regime=regime,
            reason=reason,
            components={
                "fear_greed": c_fg,
                "dominance": c_dom,
                "market_cap": c_mcap,
                "dxy": c_dxy,
            },
        )

    @staticmethod
    def _clip(v: float) -> float:
        return float(max(0.0, min(100.0, v)))

    def _score_fg(self, fg: float) -> float:
        # Extreme greed -> fragile, deep fear -> opportunistic but uncertain.
        if fg < 20:
            return 58.0
        if fg > 80:
            return 35.0
        return self._clip(50.0 + (fg - 50.0) * 0.4)

    def _score_dominance(self, dom: float) -> float:
        # Falling dominance usually risk-on for broad crypto beta.
        return self._clip(62.0 - (dom - 45.0) * 1.1)

    def _score_mcap(self, mcap_change: float) -> float:
        return self._clip(50.0 + mcap_change * 4.5)

    def _score_dxy(self, dxy_trend: str) -> float:
        trend = dxy_trend.upper()
        if trend == "DOWN":
            return 68.0
        if trend == "UP":
            return 36.0
        return 50.0
