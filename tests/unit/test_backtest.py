from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestEngine
from src.backtest.lab.walk_forward import generate_windows
from src.backtest.metrics import max_drawdown, sharpe_ratio, win_rate
from src.backtest.ml_data.labeler import triple_barrier_label
from src.backtest.ml_data.splitter import purged_kfold_indices


def _ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.normal(0.0, 1.0, n))
    high = close + np.abs(rng.normal(0.4, 0.1, n))
    low = close - np.abs(rng.normal(0.4, 0.1, n))
    open_ = close + rng.normal(0.0, 0.1, n)
    vol = rng.uniform(100, 1000, n)
    return pd.DataFrame(
        {
            "timestamp": np.arange(n),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )


def test_backtest_engine_runs() -> None:
    df = _ohlcv(120)
    engine = BacktestEngine()
    result = engine.run(df, signal_fn=lambda row: 1 if row["close"] > row["open"] else -1)
    assert len(result.equity_curve) == len(df)
    assert len(result.trades) > 0


def test_metrics_functions() -> None:
    rets = [0.01, -0.02, 0.015, 0.0, 0.02]
    eq = [100, 101, 99, 100.5, 100.5, 102.5]
    assert 0 <= win_rate(rets) <= 1
    assert max_drawdown(eq) >= 0
    assert isinstance(sharpe_ratio(rets), float)


def test_walk_forward_windows() -> None:
    windows = generate_windows(n_rows=200, train_size=100, test_size=20, step_size=20, expanding=False)
    assert windows
    assert windows[0].train_start == 0
    assert windows[0].train_end == 100
    assert windows[0].test_start == 100


def test_triple_barrier_label() -> None:
    close = pd.Series([100, 101, 102, 99, 98, 103, 104])
    labels = triple_barrier_label(close, take_profit_pct=0.015, stop_loss_pct=0.015, horizon=3)
    assert len(labels) == len(close)
    assert set(labels.unique()).issubset({-1, 0, 1})


def test_purged_kfold_indices() -> None:
    folds = purged_kfold_indices(100, k=5, purge=2)
    assert len(folds) == 5
    for fold in folds:
        assert len(set(fold.train_idx).intersection(set(fold.test_idx))) == 0
