from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from argus_py.council.defs import Vote
from argus_py.data.market_state import Bar
from argus_py.models.orion.indicators import IndicatorService


@dataclass
class OrionScoreComponents:
    structure: float  # 0-35
    trend: float  # 0-25
    momentum: float  # 0-25
    pattern: float  # 0-15


class OrionEngine:
    """
    Orion voter with multi-indicator technical scoring.

    Backward compatibility:
    - returns Vote(module="Orion", direction/confidence/score/reasons/metadata)
    - keeps metadata fields used elsewhere: adx, atr, trend_active
    """

    def __init__(self, adx_period: int = 14, lookback: int = 260):
        self.adx_period = adx_period
        self.lookback = lookback

    def calculate(self, history: List[Bar]) -> Optional[Vote]:
        min_bars = max(200, self.lookback // 2)
        if len(history) < min_bars:
            return Vote(
                "Orion",
                "FLAT",
                0.0,
                50.0,
                ["Insufficient Data"],
                metadata={"orion_valid": False, "reason": "WARMUP"},
            )

        subset = history[-self.lookback :]
        highs = [b.high for b in subset]
        lows = [b.low for b in subset]
        closes = [b.close for b in subset]
        price = closes[-1]

        sma50 = IndicatorService.sma(closes, 50)
        sma200 = IndicatorService.sma(closes, 200)
        ema12 = IndicatorService.ema(closes, 12)
        ema26 = IndicatorService.ema(closes, 26)

        bb_upper, bb_mid, bb_lower = IndicatorService.bollinger(closes)
        adx_series = IndicatorService.adx(highs, lows, closes, self.adx_period)
        atr_series = IndicatorService.atr(highs, lows, closes, self.adx_period)

        rsi_series = IndicatorService.rsi(closes)
        macd_line, macd_signal, macd_hist = IndicatorService.macd(closes)
        stoch_k, stoch_d = IndicatorService.stochastic(highs, lows, closes)

        structure = self._score_structure(
            price=price,
            sma50_last=self._last_valid(sma50),
            sma200_last=self._last_valid(sma200),
            bb_lower_last=self._last_valid(bb_lower),
            bb_upper_last=self._last_valid(bb_upper),
        )
        trend = self._score_trend(
            adx_last=self._last_valid(adx_series, default=0.0),
            ema12_last=ema12[-1] if ema12 else price,
            ema26_last=ema26[-1] if ema26 else price,
            price=price,
        )
        momentum = self._score_momentum(
            rsi_last=self._last_valid(rsi_series, default=50.0),
            macd_hist_last=macd_hist[-1] if macd_hist else 0.0,
            stoch_k_last=stoch_k[-1] if stoch_k else 50.0,
            stoch_d_last=stoch_d[-1] if stoch_d else 50.0,
        )
        pattern = self._detect_divergence(closes, rsi_series)

        components = OrionScoreComponents(
            structure=structure,
            trend=trend,
            momentum=momentum,
            pattern=pattern,
        )

        total = max(0.0, min(100.0, components.structure + components.trend + components.momentum + components.pattern))

        direction, confidence = self._to_vote_direction(total)

        reasons = [
            f"Structure={components.structure:.1f}/35",
            f"Trend={components.trend:.1f}/25",
            f"Momentum={components.momentum:.1f}/25",
            f"Pattern={components.pattern:.1f}/15",
            f"Total={total:.1f}/100",
        ]

        adx_last = self._last_valid(adx_series, default=0.0)
        atr_last = self._last_valid(atr_series, default=0.0)
        rsi_last = self._last_valid(rsi_series, default=50.0)
        bb_squeeze = IndicatorService.bollinger_squeeze(bb_upper, bb_mid, bb_lower)
        macd_cross = IndicatorService.macd_crossover(macd_line, macd_signal)

        metadata = {
            "orion_valid": True,
            "adx": adx_last,
            "atr": atr_last,
            "rsi": rsi_last,
            "macd_hist": macd_hist[-1] if macd_hist else 0.0,
            "stoch_k": stoch_k[-1] if stoch_k else 50.0,
            "stoch_d": stoch_d[-1] if stoch_d else 50.0,
            "structure": components.structure,
            "trend": components.trend,
            "momentum": components.momentum,
            "pattern": components.pattern,
            "trend_active": adx_last > 25.0,
            "bb_squeeze": bb_squeeze,
            "macd_crossover": macd_cross,
            "score_components": {
                "structure": components.structure,
                "trend": components.trend,
                "momentum": components.momentum,
                "pattern": components.pattern,
            },
        }

        return Vote(
            module="Orion",
            direction=direction,
            confidence=confidence,
            score=total,
            reasons=reasons,
            metadata=metadata,
        )

    def _score_structure(
        self,
        price: float,
        sma50_last: Optional[float],
        sma200_last: Optional[float],
        bb_lower_last: Optional[float],
        bb_upper_last: Optional[float],
    ) -> float:
        score = 0.0

        if sma50_last is not None and sma200_last is not None:
            if price > sma50_last and price > sma200_last:
                score += 15.0
            if sma50_last > sma200_last:
                score += 10.0

        # Oversold opportunity near lower band, with mild bonus for upper-band strength.
        if bb_lower_last is not None and price < bb_lower_last:
            score += 10.0
        elif bb_upper_last is not None and price > bb_upper_last:
            score += 5.0

        return max(0.0, min(35.0, score))

    def _score_trend(self, adx_last: float, ema12_last: float, ema26_last: float, price: float) -> float:
        score = 0.0

        if adx_last >= 25.0:
            score += 12.0
        elif adx_last >= 20.0:
            score += 8.0
        elif adx_last >= 15.0:
            score += 4.0

        if ema12_last > ema26_last:
            score += 8.0
        if price > ema12_last:
            score += 5.0

        return max(0.0, min(25.0, score))

    def _score_momentum(
        self,
        rsi_last: float,
        macd_hist_last: float,
        stoch_k_last: float,
        stoch_d_last: float,
    ) -> float:
        score = 0.0

        if rsi_last < 30.0:
            score += 10.0
        elif rsi_last > 70.0:
            score -= 5.0
        elif 45.0 <= rsi_last <= 65.0:
            score += 3.0

        if macd_hist_last > 0.0:
            score += 8.0

        if stoch_k_last > stoch_d_last:
            score += 7.0

        return max(0.0, min(25.0, score))

    def _detect_divergence(self, closes: List[float], rsi: List[Optional[float]]) -> float:
        if len(closes) < 10 or len(rsi) < 10:
            return 0.0

        recent_prices = closes[-8:]
        recent_rsi = [x for x in rsi[-8:] if x is not None]
        if len(recent_rsi) < 6:
            return 0.0

        price_delta = recent_prices[-1] - recent_prices[0]
        rsi_delta = recent_rsi[-1] - recent_rsi[0]

        # Bullish divergence: price down while RSI up.
        if price_delta < 0 and rsi_delta > 0:
            return 15.0

        # Bearish divergence mildly penalizes by giving no pattern credit.
        return 0.0

    def _to_vote_direction(self, total_score: float) -> tuple[str, float]:
        if total_score >= 60.0:
            confidence = min(1.0, (total_score - 50.0) / 50.0)
            return "LONG", confidence
        if total_score <= 40.0:
            confidence = min(1.0, (50.0 - total_score) / 50.0)
            return "SHORT", confidence
        return "FLAT", 0.2

    def _last_valid(self, values: List[Optional[float]], default: Optional[float] = None) -> Optional[float]:
        for value in reversed(values):
            if value is not None:
                return value
        return default


# Backward-compatible type alias used by council integration contracts.
OrionVote = Vote
