"""Portfolio-level simulator over multiple asset return streams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from src.backtest.metrics import max_drawdown, sharpe_ratio


@dataclass(frozen=True)
class PortfolioBacktestSummary:
    total_return: float
    sharpe: float
    max_drawdown: float


def run_portfolio_backtest(
    *,
    asset_returns: Mapping[str, list[float]],
    weights: Mapping[str, float],
    initial_equity: float = 10_000.0,
) -> tuple[list[float], PortfolioBacktestSummary]:
    if not asset_returns:
        return [initial_equity], PortfolioBacktestSummary(0.0, 0.0, 0.0)

    length = min(len(v) for v in asset_returns.values())
    portfolio_rets: list[float] = []
    for i in range(length):
        period_ret = 0.0
        for symbol, series in asset_returns.items():
            period_ret += float(series[i]) * float(weights.get(symbol, 0.0))
        portfolio_rets.append(period_ret)

    equity = initial_equity
    curve = [equity]
    for r in portfolio_rets:
        equity *= (1.0 + r)
        curve.append(equity)

    total_return = (curve[-1] / initial_equity) - 1.0
    summary = PortfolioBacktestSummary(
        total_return=float(total_return),
        sharpe=sharpe_ratio(portfolio_rets),
        max_drawdown=max_drawdown(curve),
    )
    return curve, summary
