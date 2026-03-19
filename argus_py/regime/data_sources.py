from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from argus_py.data.market_state import Bar


@dataclass(frozen=True)
class RegimeFeatureSet:
    adx: float
    atr_ratio: float
    bb_width: float
    realized_vol: float
    slope_bps: float


class RegimeFeatureSource:
    """Computes deterministic market features from recent bars."""

    def __init__(self, lookback: int = 120) -> None:
        if lookback < 30:
            raise ValueError("lookback must be >= 30")
        self.lookback = int(lookback)

    def from_bars(self, bars: Sequence[Bar]) -> RegimeFeatureSet:
        if len(bars) < 30:
            raise ValueError("insufficient bars for regime features")

        subset = list(bars)[-self.lookback :]
        closes = [float(b.close) for b in subset]
        highs = [float(b.high) for b in subset]
        lows = [float(b.low) for b in subset]

        adx_series = self._adx(highs, lows, closes, period=14)
        atr_series = self._atr(highs, lows, closes, period=14)
        bb_u, bb_m, bb_l = self._bollinger(closes, period=20, std_mult=2.0)

        adx = self._last_valid(adx_series, default=15.0)
        atr = self._last_valid(atr_series, default=0.0)

        price = closes[-1]
        atr_ratio = (atr / price) if price > 0 else 0.0

        bb_u_last = self._last_valid(bb_u, default=price)
        bb_m_last = self._last_valid(bb_m, default=price)
        bb_l_last = self._last_valid(bb_l, default=price)
        bb_width = ((bb_u_last - bb_l_last) / abs(bb_m_last)) if bb_m_last else 0.0

        returns = np.diff(np.log(np.asarray(closes, dtype=float)))
        realized_vol = float(np.std(returns, ddof=1) * np.sqrt(len(returns))) if len(returns) > 1 else 0.0

        slope = self._linear_slope(closes[-40:]) if len(closes) >= 40 else self._linear_slope(closes)
        slope_bps = (slope / price) * 10000.0 if price > 0 else 0.0

        return RegimeFeatureSet(
            adx=float(adx),
            atr_ratio=float(atr_ratio),
            bb_width=float(bb_width),
            realized_vol=float(realized_vol),
            slope_bps=float(slope_bps),
        )

    @staticmethod
    def _last_valid(values: Sequence[float | None], default: float) -> float:
        for value in reversed(values):
            if value is not None:
                return float(value)
        return float(default)

    @staticmethod
    def _linear_slope(values: Sequence[float]) -> float:
        if len(values) < 2:
            return 0.0
        y = np.asarray(values, dtype=float)
        x = np.arange(y.size, dtype=float)
        x_mean = float(np.mean(x))
        y_mean = float(np.mean(y))
        denom = float(np.sum((x - x_mean) ** 2))
        if denom <= 0.0:
            return 0.0
        return float(np.sum((x - x_mean) * (y - y_mean)) / denom)

    @staticmethod
    def _bollinger(
        closes: Sequence[float],
        period: int = 20,
        std_mult: float = 2.0,
    ) -> tuple[list[float], list[float], list[float]]:
        s = pd.Series(list(closes), dtype="float64")
        middle = s.rolling(window=period, min_periods=period).mean()
        std = s.rolling(window=period, min_periods=period).std(ddof=0)
        upper = middle + (std * std_mult)
        lower = middle - (std * std_mult)
        return upper.astype(float).tolist(), middle.astype(float).tolist(), lower.astype(float).tolist()

    @staticmethod
    def _atr(
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        period: int = 14,
    ) -> list[float]:
        h = pd.Series(list(highs), dtype="float64")
        l = pd.Series(list(lows), dtype="float64")
        c = pd.Series(list(closes), dtype="float64")

        tr0 = (h - l).abs()
        tr1 = (h - c.shift(1)).abs()
        tr2 = (l - c.shift(1)).abs()
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        return [float(v) if pd.notna(v) else float("nan") for v in atr.tolist()]

    @staticmethod
    def _adx(
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        period: int = 14,
    ) -> list[float]:
        h = pd.Series(list(highs), dtype="float64")
        l = pd.Series(list(lows), dtype="float64")
        c = pd.Series(list(closes), dtype="float64")

        up_move = h.diff()
        down_move = -l.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)

        tr0 = (h - l).abs()
        tr1 = (h - c.shift(1)).abs()
        tr2 = (l - c.shift(1)).abs()
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        plus_di = (
            100.0
            * pd.Series(plus_dm).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
            / atr
        )
        minus_di = (
            100.0
            * pd.Series(minus_dm).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
            / atr
        )

        denom = (plus_di + minus_di).replace(0.0, np.nan)
        dx = ((plus_di - minus_di).abs() / denom) * 100.0
        adx = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        return [float(v) if pd.notna(v) else float("nan") for v in adx.tolist()]
