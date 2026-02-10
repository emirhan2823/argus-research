from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.data_manager import BacktestDataManager
from src.backtest.lab.asset_tester import run_asset_backtest
from src.backtest.lab.portfolio_tester import run_portfolio_backtest
from src.backtest.lab.report import write_report


def _ohlcv(n: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.normal(0.0, 0.8, n))
    high = close + np.abs(rng.normal(0.3, 0.1, n))
    low = close - np.abs(rng.normal(0.3, 0.1, n))
    open_ = close + rng.normal(0.0, 0.1, n)
    volume = rng.uniform(200, 1500, n)
    return pd.DataFrame(
        {
            "timestamp": np.arange(n),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_asset_and_portfolio_backtest_flow(tmp_path) -> None:
    frame = _ohlcv(180)
    csv_path = tmp_path / "ohlcv.csv"
    frame.to_csv(csv_path, index=False)

    loaded = BacktestDataManager().load(str(csv_path))
    result, summary = run_asset_backtest(
        symbol="BTCUSDT",
        candles=loaded,
        signal_fn=lambda row: 1 if row["close"] >= row["open"] else -1,
    )
    assert summary.trades >= 0
    assert len(result.equity_curve) == len(loaded)

    curve, p_summary = run_portfolio_backtest(
        asset_returns={"BTCUSDT": list(result.returns), "ETHUSDT": list(result.returns)},
        weights={"BTCUSDT": 0.5, "ETHUSDT": 0.5},
    )
    assert len(curve) >= 2
    assert isinstance(p_summary.total_return, float)

    report_path = write_report(
        str(tmp_path / "report.md"),
        title="Backtest Report",
        sections={"asset": summary, "portfolio": p_summary},
    )
    assert report_path.endswith("report.md")
