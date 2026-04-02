"""Hybrid 6-state regime classifier for the snowball architecture.

States:
    BULLISH_TREND    — ADX strong + price above MA200 + Hurst persistent
                       → enable Trend Engine (TITAN), long-biased
    BEARISH_TREND    — ADX strong + price below MA200 + Hurst persistent
                       → enable Trend Engine (TITAN), short-biased
    RANGE_MR         — low ADX + Hurst mean-reverting
                       → enable MR Engine (POSEIDON), both sides
    EXPANSION        — moderate/high volatility + directional (ATR expanding)
                       → enable Trend Engine with caution (momentum play)
    CHOP             — high volatility + no direction (ATR expanding, ADX weak)
                       → avoid new positions
    CRISIS_DEFENSIVE — crash conditions or extreme vol
                       → disable all engines

Confidence score (0.0–1.0) measures how cleanly the regime conditions are met.
High confidence → full sizing. Borderline → reduced sizing.

Designed to be used alongside the existing RuleBasedRegimeClassifier:
    - RuleBasedRegimeClassifier routes existing engines (POSEIDON, TITAN, etc.)
    - HybridRegimeClassifier provides richer context for admission + sizing
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class HybridRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    RANGE_MR = "RANGE_MR"
    EXPANSION = "EXPANSION"
    CHOP = "CHOP"
    CRISIS_DEFENSIVE = "CRISIS_DEFENSIVE"


class HybridRegimeResult(NamedTuple):
    regime: HybridRegime
    confidence: float           # 0.0 – 1.0
    direction: int              # +1 bullish, -1 bearish, 0 neutral
    trend_suitable: bool        # True → Trend Engine enabled
    mr_suitable: bool           # True → MR Engine enabled
    size_mult: float            # Suggested position size multiplier
    reason: str                 # Diagnostic string


@dataclass
class HybridRegimeInput:
    """Minimal feature snapshot for hybrid regime classification."""
    adx_14: float
    price_vs_ma200: float       # (close/MA200 - 1): positive = above
    ema_21_vs_55: float         # (EMA21/EMA55 - 1): positive = EMA21 above
    hurst_exponent: float       # 0.5+ trending, <0.5 mean-reverting
    atr_ratio_5_20: float       # ATR(5)/ATR(20): >1 expanding, <1 contracting
    vol_multiple_60d: float     # current vol / 60d avg vol
    price_drop_24h: float = 0.0 # for crisis detection
    directional_score: float = 0.0  # external directional bias score if available


@dataclass
class HybridRegimeClassifier:
    """Deterministic 6-state regime classifier.

    Priority order (highest to lowest):
        1. CRISIS_DEFENSIVE
        2. CHOP
        3. BULLISH_TREND
        4. BEARISH_TREND
        5. EXPANSION
        6. RANGE_MR (default)
    """

    # ── TREND thresholds (relaxed from original 32/0.58 for better coverage) ──
    trending_min_adx: float = 26.0
    trending_min_hurst: float = 0.52
    trending_strong_adx: float = 32.0    # confident trend at this ADX
    trending_strong_hurst: float = 0.58  # confident trend at this Hurst

    # ── RANGE thresholds ──
    range_max_adx: float = 24.0
    range_max_hurst: float = 0.52
    range_strong_max_adx: float = 20.0   # very clean range

    # ── EXPANSION thresholds (directional momentum with expanding vol) ──
    expansion_atr_ratio: float = 1.3     # ATR expanding
    expansion_min_adx: float = 18.0      # some direction
    expansion_max_adx: float = 30.0      # below full trend threshold

    # ── CHOP thresholds (high vol + no direction) ──
    chop_atr_ratio: float = 1.4
    chop_max_adx: float = 20.0

    # ── CRISIS thresholds ──
    crisis_price_drop_24h: float = -0.08
    crisis_vol_multiple: float = 3.0
    crisis_atr_ratio: float = 2.5

    def classify(self, inp: HybridRegimeInput) -> HybridRegimeResult:
        """Classify regime. Returns HybridRegimeResult with confidence + routing hints."""

        # ── CRISIS DEFENSIVE ────────────────────────────────────────────────
        if self._is_crisis(inp):
            return HybridRegimeResult(
                regime=HybridRegime.CRISIS_DEFENSIVE,
                confidence=1.0,
                direction=0,
                trend_suitable=False,
                mr_suitable=False,
                size_mult=0.0,
                reason="crisis_conditions",
            )

        # ── CHOP (high vol + no direction → avoid) ──────────────────────────
        if self._is_chop(inp):
            return HybridRegimeResult(
                regime=HybridRegime.CHOP,
                confidence=0.7,
                direction=0,
                trend_suitable=False,
                mr_suitable=False,
                size_mult=0.0,
                reason=f"chop_atr={inp.atr_ratio_5_20:.2f}_adx={inp.adx_14:.1f}",
            )

        # ── BULLISH TREND ────────────────────────────────────────────────────
        if self._is_bullish_trend(inp):
            conf = self._trend_confidence(inp)
            return HybridRegimeResult(
                regime=HybridRegime.BULLISH_TREND,
                confidence=conf,
                direction=+1,
                trend_suitable=True,
                mr_suitable=False,
                size_mult=min(1.2, 0.7 + conf * 0.5),
                reason=f"bullish_trend_adx={inp.adx_14:.1f}_hurst={inp.hurst_exponent:.2f}",
            )

        # ── BEARISH TREND ────────────────────────────────────────────────────
        if self._is_bearish_trend(inp):
            conf = self._trend_confidence(inp)
            return HybridRegimeResult(
                regime=HybridRegime.BEARISH_TREND,
                confidence=conf,
                direction=-1,
                trend_suitable=True,
                mr_suitable=False,
                size_mult=min(1.1, 0.65 + conf * 0.45),
                reason=f"bearish_trend_adx={inp.adx_14:.1f}_hurst={inp.hurst_exponent:.2f}",
            )

        # ── EXPANSION (directional momentum with expanding vol) ─────────────
        if self._is_expansion(inp):
            direction = +1 if inp.price_vs_ma200 >= 0 else -1
            conf = min(0.75, 0.45 + inp.atr_ratio_5_20 * 0.15)
            return HybridRegimeResult(
                regime=HybridRegime.EXPANSION,
                confidence=conf,
                direction=direction,
                trend_suitable=True,
                mr_suitable=False,
                size_mult=min(0.9, 0.5 + conf * 0.5),
                reason=f"expansion_atr={inp.atr_ratio_5_20:.2f}_adx={inp.adx_14:.1f}",
            )

        # ── RANGE / MR ───────────────────────────────────────────────────────
        conf = self._range_confidence(inp)
        return HybridRegimeResult(
            regime=HybridRegime.RANGE_MR,
            confidence=conf,
            direction=0,
            trend_suitable=False,
            mr_suitable=True,
            size_mult=min(1.0, 0.6 + conf * 0.4),
            reason=f"range_mr_adx={inp.adx_14:.1f}_hurst={inp.hurst_exponent:.2f}",
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _is_crisis(self, inp: HybridRegimeInput) -> bool:
        if inp.price_drop_24h <= self.crisis_price_drop_24h:
            return True
        if inp.vol_multiple_60d >= self.crisis_vol_multiple:
            return True
        if inp.atr_ratio_5_20 >= self.crisis_atr_ratio:
            return True
        return False

    def _is_chop(self, inp: HybridRegimeInput) -> bool:
        """High volatility expansion WITH no clear direction."""
        if inp.atr_ratio_5_20 >= self.chop_atr_ratio and inp.adx_14 <= self.chop_max_adx:
            return True
        return False

    def _is_bullish_trend(self, inp: HybridRegimeInput) -> bool:
        """ADX strong, Hurst persistent, price above MA200, EMA21 > EMA55."""
        if inp.adx_14 < self.trending_min_adx:
            return False
        if inp.hurst_exponent < self.trending_min_hurst:
            return False
        # Directional alignment: both price and EMA21/55 agree bullish
        aligned = inp.price_vs_ma200 >= 0 and inp.ema_21_vs_55 >= 0
        return aligned

    def _is_bearish_trend(self, inp: HybridRegimeInput) -> bool:
        """ADX strong, Hurst persistent, price below MA200, EMA21 < EMA55."""
        if inp.adx_14 < self.trending_min_adx:
            return False
        if inp.hurst_exponent < self.trending_min_hurst:
            return False
        aligned = inp.price_vs_ma200 < 0 and inp.ema_21_vs_55 < 0
        return aligned

    def _is_expansion(self, inp: HybridRegimeInput) -> bool:
        """ATR expanding + moderate ADX → momentum play."""
        return (
            inp.atr_ratio_5_20 >= self.expansion_atr_ratio
            and self.expansion_min_adx <= inp.adx_14 <= self.expansion_max_adx
        )

    def _trend_confidence(self, inp: HybridRegimeInput) -> float:
        """Confidence score for trend regime (0.5–1.0)."""
        # ADX component: 0.5 at min_adx, 1.0 at strong_adx
        adx_range = max(self.trending_strong_adx - self.trending_min_adx, 1.0)
        adx_score = min(1.0, (inp.adx_14 - self.trending_min_adx) / adx_range)

        # Hurst component: 0.5 at min_hurst, 1.0 at strong_hurst
        hurst_range = max(self.trending_strong_hurst - self.trending_min_hurst, 0.01)
        hurst_score = min(1.0, (inp.hurst_exponent - self.trending_min_hurst) / hurst_range)

        # Combined: weighted average
        raw = 0.5 + (adx_score * 0.4 + hurst_score * 0.2)
        return round(min(1.0, raw), 3)

    def _range_confidence(self, inp: HybridRegimeInput) -> float:
        """Confidence score for range regime (0.5–1.0)."""
        # Low ADX = good for MR
        adx_score = max(0.0, 1.0 - inp.adx_14 / self.range_max_adx)
        # Low Hurst = strong mean-reversion tendency
        hurst_score = max(0.0, 1.0 - inp.hurst_exponent / self.range_max_hurst)

        raw = 0.5 + (adx_score * 0.3 + hurst_score * 0.2)
        return round(min(1.0, raw), 3)
