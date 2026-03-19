from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class MarketRegime(Enum):
    TREND = "TREND"
    CHOP = "CHOP"
    RISK_OFF = "RISK_OFF"
    NEWS_SHOCK = "NEWS_SHOCK"
    NEUTRAL = "NEUTRAL"


@dataclass
class RegimeContext:
    orion_score: Optional[float]
    aether_score: Optional[float]
    hermes_score: Optional[float]
    adx: float
    chop_index: float
    recent_volatility: float


@dataclass
class ChironResult:
    regime: MarketRegime
    core_weights: Dict[str, float]
    pulse_weights: Dict[str, float]
    explanation: str
    confidence: float


class ChironRegimeEngine:
    """Detects market regime and adjusts core/pulse weights."""

    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path
        self._last_regime: MarketRegime = MarketRegime.NEUTRAL

    def evaluate(self, context: RegimeContext) -> ChironResult:
        regime = self._detect_regime(context)
        core, pulse = self._get_base_weights(regime)

        core = self._adjust_for_missing(core, context)
        pulse = self._adjust_for_missing(pulse, context)

        self._last_regime = regime

        if self.state_path is not None:
            self.save_state(self.state_path)

        return ChironResult(
            regime=regime,
            core_weights=core,
            pulse_weights=pulse,
            explanation=self._explain(regime, context),
            confidence=self._calculate_confidence(context),
        )

    def _detect_regime(self, ctx: RegimeContext) -> MarketRegime:
        aether = ctx.aether_score if ctx.aether_score is not None else 50.0
        orion = ctx.orion_score if ctx.orion_score is not None else 50.0
        hermes = ctx.hermes_score if ctx.hermes_score is not None else 50.0

        if hermes < 20 or hermes > 85:
            return MarketRegime.NEWS_SHOCK

        if aether < 35:
            return MarketRegime.RISK_OFF

        if ctx.adx >= 25 and ctx.chop_index < 45:
            return MarketRegime.TREND

        if ctx.chop_index > 60 or (ctx.adx < 20 and 40 < orion < 60):
            return MarketRegime.CHOP

        return MarketRegime.NEUTRAL

    def _get_base_weights(self, regime: MarketRegime) -> tuple[Dict[str, float], Dict[str, float]]:
        weight_table = {
            MarketRegime.TREND: (
                {"orion": 0.35, "aether": 0.20, "hermes": 0.15, "phoenix": 0.20, "aegean": 0.10},
                {"orion": 0.40, "phoenix": 0.30, "hermes": 0.15, "aegean": 0.15},
            ),
            MarketRegime.CHOP: (
                {"orion": 0.15, "aether": 0.30, "hermes": 0.20, "phoenix": 0.25, "aegean": 0.10},
                {"phoenix": 0.40, "hermes": 0.25, "orion": 0.20, "aegean": 0.15},
            ),
            MarketRegime.RISK_OFF: (
                {"aether": 0.40, "hermes": 0.30, "orion": 0.10, "phoenix": 0.10, "aegean": 0.10},
                {"hermes": 0.50, "aether": 0.30, "phoenix": 0.10, "orion": 0.10},
            ),
            MarketRegime.NEWS_SHOCK: (
                {"hermes": 0.50, "aether": 0.25, "orion": 0.10, "phoenix": 0.05, "aegean": 0.10},
                {"hermes": 0.60, "aether": 0.20, "phoenix": 0.10, "orion": 0.10},
            ),
            MarketRegime.NEUTRAL: (
                {"orion": 0.25, "aether": 0.25, "hermes": 0.20, "phoenix": 0.20, "aegean": 0.10},
                {"orion": 0.25, "phoenix": 0.25, "hermes": 0.25, "aegean": 0.25},
            ),
        }
        return weight_table.get(regime, weight_table[MarketRegime.NEUTRAL])

    def _adjust_for_missing(self, weights: Dict[str, float], ctx: RegimeContext) -> Dict[str, float]:
        adjusted = dict(weights)

        if ctx.orion_score is None and "orion" in adjusted:
            adjusted["orion"] = 0.0
        if ctx.aether_score is None and "aether" in adjusted:
            adjusted["aether"] = 0.0
        if ctx.hermes_score is None and "hermes" in adjusted:
            adjusted["hermes"] = 0.0

        total = sum(adjusted.values())
        if total <= 0:
            return adjusted

        return {k: v / total for k, v in adjusted.items()}

    def save_state(self, path: Optional[Path] = None):
        target = path or self.state_path
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        state = {"last_regime": self._last_regime.value}
        target.write_text(json.dumps(state), encoding="utf-8")

    def load_state(self, path: Optional[Path] = None):
        target = path or self.state_path
        if target is None:
            return
        if target.exists():
            state = json.loads(target.read_text(encoding="utf-8"))
            self._last_regime = MarketRegime(state.get("last_regime", "NEUTRAL"))

    def _calculate_confidence(self, ctx: RegimeContext) -> float:
        # Confidence from signal clarity (adx/chop extremes + macro/news deviation from neutral).
        adx_component = min(1.0, abs(ctx.adx - 22.5) / 25.0)
        chop_component = min(1.0, abs(ctx.chop_index - 50.0) / 50.0)

        macro_dev = abs((ctx.aether_score if ctx.aether_score is not None else 50.0) - 50.0) / 50.0
        news_dev = abs((ctx.hermes_score if ctx.hermes_score is not None else 50.0) - 50.0) / 50.0

        confidence = (adx_component * 0.30) + (chop_component * 0.30) + (macro_dev * 0.20) + (news_dev * 0.20)
        return max(0.0, min(1.0, confidence))

    def _explain(self, regime: MarketRegime, ctx: RegimeContext) -> str:
        bits: List[str] = [
            f"regime={regime.value}",
            f"adx={ctx.adx:.1f}",
            f"chop={ctx.chop_index:.1f}",
            f"vol={ctx.recent_volatility:.2f}",
        ]
        if ctx.aether_score is not None:
            bits.append(f"aether={ctx.aether_score:.1f}")
        if ctx.hermes_score is not None:
            bits.append(f"hermes={ctx.hermes_score:.1f}")
        if ctx.orion_score is not None:
            bits.append(f"orion={ctx.orion_score:.1f}")
        return " | ".join(bits)
