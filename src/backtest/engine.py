"""Simple event-driven backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class SimTrade:
    index: int
    side: str
    entry_price: float
    exit_price: float
    pnl: float


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[SimTrade, ...]
    equity_curve: tuple[float, ...]
    returns: tuple[float, ...]


@dataclass
class BacktestEngine:
    initial_equity: float = 10_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 3.0

    def run(
        self,
        candles: pd.DataFrame,
        signal_fn: Callable[[pd.Series], int],
    ) -> BacktestResult:
        equity = self.initial_equity
        equity_curve: list[float] = [equity]
        returns: list[float] = []
        trades: list[SimTrade] = []

        for i in range(1, len(candles)):
            prev = candles.iloc[i - 1]
            row = candles.iloc[i]
            signal = int(signal_fn(prev))  # -1, 0, 1
            if signal == 0:
                equity_curve.append(equity)
                returns.append(0.0)
                continue

            entry = float(prev["close"])
            exit_ = float(row["close"])
            gross_ret = ((exit_ - entry) / max(entry, 1e-9)) * signal
            costs = (self.fee_bps + self.slippage_bps) / 10_000.0
            net_ret = gross_ret - costs
            pnl = equity * net_ret
            equity += pnl

            trades.append(
                SimTrade(
                    index=i,
                    side="long" if signal > 0 else "short",
                    entry_price=entry,
                    exit_price=exit_,
                    pnl=pnl,
                )
            )
            returns.append(net_ret)
            equity_curve.append(equity)

        return BacktestResult(
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            returns=tuple(returns),
        )
