"""Rule-based market regime classifier for ARGUS v2.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import (
    HERMES_CRITICAL,
    REGIME_CRISIS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)


@dataclass(frozen=True)
class RuleBasedInput:
    """Minimal feature snapshot required by rule-based regime detection."""

    adx_14: float
    price_vs_ma200: float
    ema_21_vs_55: float
    hurst_exponent: float
    atr_ratio_5_20: float
    vol_multiple_60d: float
    price_drop_24h: float = 0.0
    liquidation_pctile: Optional[float] = None
    depth_ratio: Optional[float] = None
    directional_alignment_candles: int = 0
    hermes_urgency: Optional[str] = None
    hermes_sentiment_score: Optional[float] = None


class RuleBasedRegimeClassifier:
    """Priority-order rule regime classifier.

    Priority:
    1. CRISIS
    2. VOLATILE
    3. TRENDING
    4. RANGING
    5. default: RANGING
    """

    def __init__(
        self,
        *,
        crisis_price_drop_24h: float = -0.08,
        crisis_vol_multiple: float = 3.0,
        crisis_liquidation_pctile: float = 99.0,
        crisis_depth_ratio: float = 0.30,
        volatile_atr_ratio: float = 1.4,
        volatile_vol_multiple: float = 1.5,
        trending_min_adx: float = 32.0,
        trending_min_hurst: float = 0.58,
        trending_alignment_candles: int = 20,
        ranging_max_adx: float = 32.0,
        ranging_max_hurst: float = 0.50,
    ) -> None:
        self.crisis_price_drop_24h = crisis_price_drop_24h
        self.crisis_vol_multiple = crisis_vol_multiple
        self.crisis_liquidation_pctile = crisis_liquidation_pctile
        self.crisis_depth_ratio = crisis_depth_ratio
        self.volatile_atr_ratio = volatile_atr_ratio
        self.volatile_vol_multiple = volatile_vol_multiple
        self.trending_min_adx = trending_min_adx
        self.trending_min_hurst = trending_min_hurst
        self.trending_alignment_candles = trending_alignment_candles
        self.ranging_max_adx = ranging_max_adx
        self.ranging_max_hurst = ranging_max_hurst

    def classify(self, inp: RuleBasedInput) -> str:
        """Return one of TRENDING/RANGING/VOLATILE/CRISIS."""
        if self._is_crisis(inp):
            return REGIME_CRISIS
        if self._is_volatile(inp):
            return REGIME_VOLATILE
        if self._is_trending(inp):
            return REGIME_TRENDING
        if self._is_ranging(inp):
            return REGIME_RANGING
        return REGIME_RANGING

    def _is_crisis(self, inp: RuleBasedInput) -> bool:
        hermes_forced = (
            inp.hermes_urgency == HERMES_CRITICAL
            and (inp.hermes_sentiment_score is None or inp.hermes_sentiment_score < -70.0)
        )
        if hermes_forced:
            return True
        if inp.price_drop_24h <= self.crisis_price_drop_24h:
            return True
        if inp.vol_multiple_60d >= self.crisis_vol_multiple:
            return True
        if (
            inp.liquidation_pctile is not None
            and inp.liquidation_pctile >= self.crisis_liquidation_pctile
        ):
            return True
        if inp.depth_ratio is not None and inp.depth_ratio <= self.crisis_depth_ratio:
            return True
        return False

    def _is_volatile(self, inp: RuleBasedInput) -> bool:
        # Single strong signal
        if inp.atr_ratio_5_20 >= self.volatile_atr_ratio:
            return True
        if inp.vol_multiple_60d >= self.volatile_vol_multiple:
            return True
        # Combined moderate signals
        if inp.atr_ratio_5_20 >= 1.2 and inp.vol_multiple_60d >= 1.3:
            return True
        return False

    def _is_trending(self, inp: RuleBasedInput) -> bool:
        # Directional alignment requires price and EMA slope to agree.
        aligned = (inp.price_vs_ma200 >= 0 and inp.ema_21_vs_55 >= 0) or (
            inp.price_vs_ma200 < 0 and inp.ema_21_vs_55 < 0
        )
        # Hurst must show persistent (trending) behavior, not mean-reverting
        persistent = inp.hurst_exponent >= self.trending_min_hurst
        return (
            inp.adx_14 >= self.trending_min_adx
            and aligned
            and persistent
        )

    def _is_ranging(self, inp: RuleBasedInput) -> bool:
        # Standard range: low ADX + mean-reverting/random Hurst
        if inp.adx_14 <= self.ranging_max_adx and inp.hurst_exponent <= self.ranging_max_hurst:
            return True
        # Strongly mean-reverting Hurst overrides moderate ADX
        if inp.hurst_exponent <= 0.40 and inp.adx_14 <= 30:
            return True
        # Weak trend zone (ADX 25-32 + non-persistent Hurst) → RANGING
        if 25 <= inp.adx_14 < 32 and inp.hurst_exponent < 0.58:
            return True
        return False
