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


def profit_factor(pnls: Iterable[float]) -> float:
    """Compute profit factor: gross profit / gross loss."""
    values = list(pnls)
    gains = sum(p for p in values if p > 0)
    losses = abs(sum(p for p in values if p < 0))
    if losses < 1e-9:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def win_rate_by_group(
    pnls: Iterable[float],
    groups: Iterable[str],
) -> dict[str, float]:
    """Compute win rate grouped by a categorical key.

    Parameters
    ----------
    pnls : PnL values per trade.
    groups : Group label per trade (must be same length as pnls).

    Returns
    -------
    dict mapping group label to win rate (0-1).
    """
    from collections import defaultdict

    buckets: dict[str, list[float]] = defaultdict(list)
    for pnl, grp in zip(pnls, groups):
        buckets[grp].append(pnl)

    result = {}
    for grp, vals in buckets.items():
        wins = sum(1 for v in vals if v > 0)
        result[grp] = wins / len(vals) if vals else 0.0
    return result
