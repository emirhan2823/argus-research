from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class ChannelLevels:
    upper: float
    middle: float
    lower: float
    slope: float
    r_squared: float


@dataclass
class PhoenixSignals:
    touch_lower_band: bool
    rsi_reversal: bool
    bullish_divergence: bool
    trend_ok: bool


@dataclass
class PhoenixAdvice:
    score: float
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    channel: ChannelLevels
    signals: PhoenixSignals
    reason: str
    r_squared: float


class PhoenixEngine:
    """Linear Regression Channel Mean Reversion."""

    def __init__(self, lookback: int = 60, channel_k: float = 2.0):
        self.lookback = lookback
        self.channel_k = channel_k

    def analyze(self, closes: List[float], highs: List[float], lows: List[float]) -> Optional[PhoenixAdvice]:
        if len(closes) < self.lookback or len(highs) < self.lookback or len(lows) < self.lookback:
            return None

        channel = self._calculate_channel(closes[-self.lookback :])

        if channel.r_squared < 0.25:
            return PhoenixAdvice(
                score=0.0,
                entry_price=closes[-1],
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                channel=channel,
                signals=PhoenixSignals(False, False, False, False),
                reason="Channel weak (R² < 0.25)",
                r_squared=channel.r_squared,
            )

        rsi = self._calculate_rsi(closes, 14)
        current_rsi = rsi[-1] if rsi else 50.0

        price = closes[-1]
        signals = PhoenixSignals(
            touch_lower_band=price <= channel.lower * 1.005,
            rsi_reversal=(current_rsi < 35 and len(rsi) > 1 and rsi[-2] < current_rsi),
            bullish_divergence=self._check_divergence(closes, rsi),
            trend_ok=channel.slope > -(channel.middle * 0.0005),
        )

        score = self._calculate_score(signals, current_rsi, channel)

        atr = self._calculate_atr(highs, lows, closes, 14)
        stop_loss = (
            channel.lower - (1.25 * atr)
            if signals.touch_lower_band
            else price - (2.0 * atr)
        )

        target_2 = (
            channel.upper
            if channel.slope > 0
            else channel.middle + (channel.upper - channel.middle) * 0.5
        )

        return PhoenixAdvice(
            score=score,
            entry_price=price,
            stop_loss=stop_loss,
            target_1=channel.middle,
            target_2=target_2,
            channel=channel,
            signals=signals,
            reason=self._generate_reason(score, signals, channel.slope),
            r_squared=channel.r_squared,
        )

    def _calculate_channel(self, closes: List[float]) -> ChannelLevels:
        n = len(closes)
        x = np.arange(n, dtype=float)
        y = np.array(closes, dtype=float)

        x_mean = float(x.mean())
        y_mean = float(y.mean())

        denom = float(np.sum((x - x_mean) ** 2))
        if denom == 0:
            return ChannelLevels(upper=y[-1], middle=y[-1], lower=y[-1], slope=0.0, r_squared=0.0)

        slope = float(np.sum((x - x_mean) * (y - y_mean)) / denom)
        intercept = y_mean - (slope * x_mean)

        y_pred = slope * x + intercept

        residuals = y - y_pred
        sigma = float(np.std(residuals))

        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - y_mean) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        mid = float(y_pred[-1])
        upper = mid + (self.channel_k * sigma)
        lower = mid - (self.channel_k * sigma)

        return ChannelLevels(
            upper=float(upper),
            middle=float(mid),
            lower=float(lower),
            slope=float(slope),
            r_squared=max(0.0, min(1.0, float(r_squared))),
        )

    def _calculate_score(self, signals: PhoenixSignals, rsi: float, channel: ChannelLevels) -> float:
        score = 50.0

        if signals.touch_lower_band:
            score += 20.0
        if signals.rsi_reversal:
            score += 15.0
        if signals.bullish_divergence:
            score += 15.0
        if rsi < 35.0:
            score += 10.0
        if signals.trend_ok:
            score += 5.0

        if channel.slope < 0:
            score -= 15.0

        sigma_pct = (channel.upper - channel.lower) / channel.middle / 2.0 if channel.middle != 0 else 0.0
        if sigma_pct > 0.08:
            score -= 10.0

        if rsi > 50.0:
            score -= 15.0

        return max(0.0, min(100.0, score))

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> List[float]:
        if period <= 0 or len(closes) < period + 1:
            return []

        values = np.array(closes, dtype=float)
        delta = np.diff(values)
        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        rsi: List[float] = []

        for i in range(period, len(delta)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100.0 - (100.0 / (1.0 + rs)))

        return rsi

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 0.0

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        if len(trs) < period:
            return float(np.mean(trs)) if trs else 0.0

        return float(np.mean(trs[-period:]))

    def _check_divergence(self, closes: List[float], rsi: List[float]) -> bool:
        if len(closes) < 6 or len(rsi) < 4:
            return False

        recent_prices = closes[-6:]
        price_now = recent_prices[-1]
        price_prev = recent_prices[0]

        recent_rsi = rsi[-4:]
        rsi_now = recent_rsi[-1]
        rsi_prev = recent_rsi[0]

        # Bullish divergence: price down, RSI up.
        return price_now < price_prev and rsi_now > rsi_prev

    def _generate_reason(self, score: float, signals: PhoenixSignals, slope: float) -> str:
        tags = []
        if signals.touch_lower_band:
            tags.append("lower_band_touch")
        if signals.rsi_reversal:
            tags.append("rsi_reversal")
        if signals.bullish_divergence:
            tags.append("bullish_divergence")
        if signals.trend_ok:
            tags.append("trend_ok")

        if not tags:
            tags.append("no_edge")

        return f"score={score:.1f}; slope={slope:.6f}; signals=" + ",".join(tags)
