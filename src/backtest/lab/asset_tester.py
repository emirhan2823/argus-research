"""Per-asset backtest runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.metrics import calmar_ratio, max_drawdown, sharpe_ratio, sortino_ratio, win_rate


@dataclass(frozen=True)
class AssetBacktestSummary:
    symbol: str
    trades: int
    win_rate: float
    max_drawdown: float
    sharpe: float
    sortino: float
    calmar: float


def run_asset_backtest(
    *,
    symbol: str,
    candles: pd.DataFrame,
    signal_fn: Callable[[pd.Series], int],
    engine: BacktestEngine | None = None,
) -> tuple[BacktestResult, AssetBacktestSummary]:
    bt = engine or BacktestEngine()
    result = bt.run(candles, signal_fn)
    pnls = [t.pnl for t in result.trades]
    summary = AssetBacktestSummary(
        symbol=symbol,
        trades=len(result.trades),
        win_rate=win_rate(pnls),
        max_drawdown=max_drawdown(result.equity_curve),
        sharpe=sharpe_ratio(result.returns),
        sortino=sortino_ratio(result.returns),
        calmar=calmar_ratio(result.returns, result.equity_curve),
    )
    return result, summary
