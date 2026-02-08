from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class IndicatorResult:
    value: float
    signal: str  # BULLISH|BEARISH|NEUTRAL
    strength: float  # 0-100


class IndicatorService:
    """Technical indicators matching Swift TechnicalAnalysisEngine."""

    @staticmethod
    def sma(closes: List[float], period: int = 20) -> List[Optional[float]]:
        if period <= 0:
            raise ValueError("period must be > 0")
        s = pd.Series(closes, dtype="float64")
        values = s.rolling(window=period, min_periods=period).mean().tolist()
        return [float(v) if pd.notna(v) else None for v in values]

    @staticmethod
    def ema(closes: List[float], period: int = 20) -> List[float]:
        if period <= 0:
            raise ValueError("period must be > 0")
        s = pd.Series(closes, dtype="float64")
        return s.ewm(span=period, adjust=False).mean().astype(float).tolist()

    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
        """Relative Strength Index."""
        if period <= 0:
            raise ValueError("period must be > 0")
        if len(closes) == 0:
            return []

        s = pd.Series(closes, dtype="float64")
        delta = s.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)

        avg_gain = gains.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        avg_loss = losses.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # If loss is exactly zero after warmup, RSI is 100.
        rsi = rsi.where(~((avg_loss == 0.0) & avg_loss.notna()), 100.0)
        return [float(v) if pd.notna(v) else None for v in rsi.tolist()]

    @staticmethod
    def macd(
        closes: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[List[float], List[float], List[float]]:
        """MACD (line, signal, histogram)."""
        if min(fast, slow, signal) <= 0:
            raise ValueError("periods must be > 0")
        s = pd.Series(closes, dtype="float64")
        fast_ema = s.ewm(span=fast, adjust=False).mean()
        slow_ema = s.ewm(span=slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return (
            macd_line.astype(float).tolist(),
            signal_line.astype(float).tolist(),
            histogram.astype(float).tolist(),
        )

    @staticmethod
    def macd_crossover(macd_line: List[float], signal_line: List[float]) -> str:
        """Return BULLISH, BEARISH, NEUTRAL for latest MACD crossover."""
        if len(macd_line) < 2 or len(signal_line) < 2:
            return "NEUTRAL"

        prev_diff = macd_line[-2] - signal_line[-2]
        last_diff = macd_line[-1] - signal_line[-1]

        if prev_diff <= 0.0 and last_diff > 0.0:
            return "BULLISH"
        if prev_diff >= 0.0 and last_diff < 0.0:
            return "BEARISH"
        return "NEUTRAL"

    @staticmethod
    def bollinger(
        closes: List[float],
        period: int = 20,
        std_mult: float = 2.0,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Bollinger Bands (upper, middle, lower)."""
        if period <= 0:
            raise ValueError("period must be > 0")
        s = pd.Series(closes, dtype="float64")
        middle = s.rolling(window=period, min_periods=period).mean()
        std = s.rolling(window=period, min_periods=period).std(ddof=0)
        upper = middle + (std * std_mult)
        lower = middle - (std * std_mult)
        return (
            upper.astype(float).tolist(),
            middle.astype(float).tolist(),
            lower.astype(float).tolist(),
        )

    @staticmethod
    def bollinger_squeeze(
        upper: List[float],
        middle: List[float],
        lower: List[float],
        window: int = 20,
        percentile: float = 0.2,
    ) -> bool:
        """True when latest band width is in lower percentile of recent widths."""
        if len(upper) == 0 or len(middle) == 0 or len(lower) == 0:
            return False

        widths: List[float] = []
        for u, m, l in zip(upper, middle, lower):
            if any(pd.isna(x) for x in (u, m, l)):
                continue
            if m == 0:
                continue
            widths.append((u - l) / abs(m))

        if len(widths) < max(5, window):
            return False

        recent = widths[-window:]
        threshold = float(np.quantile(recent, percentile))
        return recent[-1] <= threshold

    @staticmethod
    def stochastic(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        k_period: int = 14,
        d_period: int = 3,
    ) -> Tuple[List[float], List[float]]:
        """Stochastic (%K, %D)."""
        if min(k_period, d_period) <= 0:
            raise ValueError("periods must be > 0")

        h = pd.Series(highs, dtype="float64")
        l = pd.Series(lows, dtype="float64")
        c = pd.Series(closes, dtype="float64")

        ll = l.rolling(window=k_period, min_periods=k_period).min()
        hh = h.rolling(window=k_period, min_periods=k_period).max()
        denom = (hh - ll).replace(0.0, np.nan)
        k = ((c - ll) / denom) * 100.0
        k = k.fillna(50.0)
        d = k.rolling(window=d_period, min_periods=d_period).mean().fillna(50.0)

        return k.astype(float).tolist(), d.astype(float).tolist()

    @staticmethod
    def atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> List[Optional[float]]:
        """Average True Range (Wilder smoothing)."""
        if period <= 0:
            raise ValueError("period must be > 0")
        if len(closes) == 0:
            return []

        h = pd.Series(highs, dtype="float64")
        l = pd.Series(lows, dtype="float64")
        c = pd.Series(closes, dtype="float64")

        tr0 = (h - l).abs()
        tr1 = (h - c.shift(1)).abs()
        tr2 = (l - c.shift(1)).abs()
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        return [float(v) if pd.notna(v) else None for v in atr.tolist()]

    @staticmethod
    def cci(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 20,
    ) -> List[Optional[float]]:
        """Commodity Channel Index."""
        if period <= 0:
            raise ValueError("period must be > 0")

        h = pd.Series(highs, dtype="float64")
        l = pd.Series(lows, dtype="float64")
        c = pd.Series(closes, dtype="float64")

        tp = (h + l + c) / 3.0
        tp_sma = tp.rolling(window=period, min_periods=period).mean()
        mad = tp.rolling(window=period, min_periods=period).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )
        denom = (0.015 * mad).replace(0.0, np.nan)
        cci = (tp - tp_sma) / denom

        return [float(v) if pd.notna(v) else None for v in cci.tolist()]

    @staticmethod
    def adx(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> List[Optional[float]]:
        """Average Directional Index."""
        if period <= 0:
            raise ValueError("period must be > 0")
        if len(closes) == 0:
            return []

        h = pd.Series(highs, dtype="float64")
        l = pd.Series(lows, dtype="float64")
        c = pd.Series(closes, dtype="float64")

        up_move = h.diff()
        down_move = -l.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)

        tr0 = (h - l).abs()
        tr1 = (h - c.shift(1)).abs()
        tr2 = (l - c.shift(1)).abs()
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        plus_di = 100.0 * pd.Series(plus_dm).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr
        minus_di = 100.0 * pd.Series(minus_dm).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr

        denom = (plus_di + minus_di).replace(0.0, np.nan)
        dx = ((plus_di - minus_di).abs() / denom) * 100.0
        adx = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

        return [float(v) if pd.notna(v) else None for v in adx.tolist()]
