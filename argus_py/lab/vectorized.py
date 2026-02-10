from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: np.ndarray
    returns: np.ndarray
    trades: int
    total_return: float
    max_drawdown: float
    sharpe: float



def _validate_inputs(prices: np.ndarray, signal: np.ndarray) -> None:
    if prices.ndim != 1 or signal.ndim != 1:
        raise ValueError("prices and signal must be 1D arrays")
    if prices.size != signal.size:
        raise ValueError("prices and signal lengths must match")
    if prices.size < 2:
        raise ValueError("prices must contain at least 2 points")
    if np.any(prices <= 0):
        raise ValueError("prices must be positive")



def _compute_stats(equity_curve: np.ndarray, rets: np.ndarray, trades: int) -> BacktestResult:
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = np.divide(
        running_max - equity_curve,
        running_max,
        out=np.zeros_like(equity_curve),
        where=running_max > 0,
    )
    max_dd = float(np.max(drawdowns)) if drawdowns.size else 0.0

    mean_ret = float(np.mean(rets)) if rets.size else 0.0
    std_ret = float(np.std(rets, ddof=1)) if rets.size > 1 else 0.0
    sharpe = 0.0
    if std_ret > 1e-12:
        sharpe = (mean_ret / std_ret) * float(np.sqrt(rets.size))

    total_return = float(equity_curve[-1] / equity_curve[0] - 1.0)

    return BacktestResult(
        equity_curve=equity_curve,
        returns=rets,
        trades=int(trades),
        total_return=total_return,
        max_drawdown=max_dd,
        sharpe=sharpe,
    )



def run_iterative_backtest(
    prices: Iterable[float],
    signal: Iterable[float],
    fee_bps: float = 4.0,
    slippage_bps: float = 2.0,
    starting_equity: float = 1.0,
) -> BacktestResult:
    px = np.asarray(list(prices), dtype=float)
    sig = np.asarray(list(signal), dtype=float)
    _validate_inputs(px, sig)

    fee = fee_bps / 10000.0
    slip = slippage_bps / 10000.0

    equity = np.empty_like(px)
    equity[0] = starting_equity
    rets = np.zeros_like(px)
    trades = 0

    prev_pos = float(sig[0])
    for i in range(1, px.size):
        pos = float(sig[i - 1])
        ret = pos * (px[i] / px[i - 1] - 1.0)

        if float(sig[i]) != prev_pos:
            ret -= (fee + slip) * abs(float(sig[i]) - prev_pos)
            trades += 1
            prev_pos = float(sig[i])

        rets[i] = ret
        equity[i] = equity[i - 1] * (1.0 + ret)

    return _compute_stats(equity, rets[1:], trades)



def run_vectorized_backtest(
    prices: Iterable[float],
    signal: Iterable[float],
    fee_bps: float = 4.0,
    slippage_bps: float = 2.0,
    starting_equity: float = 1.0,
) -> BacktestResult:
    px = np.asarray(list(prices), dtype=float)
    sig = np.asarray(list(signal), dtype=float)
    _validate_inputs(px, sig)

    fee = fee_bps / 10000.0
    slip = slippage_bps / 10000.0

    # Bar return attributed to previous bar position.
    asset_rets = np.diff(px) / px[:-1]
    positions = sig[:-1]
    gross_rets = positions * asset_rets

    # Position transitions incur fee/slippage in the bar they are changed.
    pos_diff = np.abs(np.diff(sig))
    trade_cost = (fee + slip) * pos_diff
    net_rets = gross_rets.copy()
    if trade_cost.size:
        net_rets -= trade_cost

    equity_curve = np.empty(px.size, dtype=float)
    equity_curve[0] = starting_equity
    if net_rets.size:
        equity_curve[1:] = starting_equity * np.cumprod(1.0 + net_rets)

    trades = int(np.sum(pos_diff > 0))
    return _compute_stats(equity_curve, net_rets, trades)
