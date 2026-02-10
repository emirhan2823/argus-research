"""Backtest metrics utilities."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def max_drawdown(equity_curve: Iterable[float]) -> float:
    arr = np.array(list(equity_curve), dtype=float)
    if arr.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(arr)
    drawdowns = (arr - peaks) / np.maximum(peaks, 1e-9)
    return float(abs(np.min(drawdowns)))


def win_rate(pnls: Iterable[float]) -> float:
    values = [x for x in pnls]
    if not values:
        return 0.0
    wins = sum(1 for x in values if x > 0)
    return wins / len(values)


def sharpe_ratio(returns: Iterable[float], periods_per_year: int = 365 * 24) -> float:
    arr = np.array(list(returns), dtype=float)
    if arr.size < 2:
        return 0.0
    std = float(np.std(arr, ddof=1))
    if std <= 1e-12:
        return 0.0
    return float(np.mean(arr) / std * math.sqrt(periods_per_year))


def sortino_ratio(returns: Iterable[float], periods_per_year: int = 365 * 24) -> float:
    arr = np.array(list(returns), dtype=float)
    if arr.size < 2:
        return 0.0
    downside = arr[arr < 0]
    if downside.size == 0:
        return float(np.mean(arr) * math.sqrt(periods_per_year))
    downside_std = float(np.std(downside, ddof=1))
    if downside_std <= 1e-12:
        return 0.0
    return float(np.mean(arr) / downside_std * math.sqrt(periods_per_year))


def calmar_ratio(returns: Iterable[float], equity_curve: Iterable[float], periods_per_year: int = 365 * 24) -> float:
    arr = np.array(list(returns), dtype=float)
    if arr.size == 0:
        return 0.0
    annualized = float(np.mean(arr) * periods_per_year)
    dd = max_drawdown(equity_curve)
    if dd <= 1e-12:
        return 0.0
    return annualized / dd
