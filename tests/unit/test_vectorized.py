from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.vectorized import run_iterative_backtest, run_vectorized_backtest



def _sample_data(n: int = 20000) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(123)
    rets = rng.normal(0.0001, 0.01, n)
    prices = 100.0 * np.cumprod(1.0 + rets)
    raw = rng.normal(0.0, 1.0, n)
    signal = np.where(raw > 0.15, 1.0, np.where(raw < -0.15, -1.0, 0.0))
    return prices, signal



def test_vectorized_backtest_matches_iterative() -> None:
    prices, signal = _sample_data(5000)

    iter_res = run_iterative_backtest(prices, signal, fee_bps=4.0, slippage_bps=2.0)
    vec_res = run_vectorized_backtest(prices, signal, fee_bps=4.0, slippage_bps=2.0)

    assert np.isclose(iter_res.total_return, vec_res.total_return, atol=1e-10)
    assert np.isclose(iter_res.max_drawdown, vec_res.max_drawdown, atol=1e-10)
    assert np.isclose(iter_res.sharpe, vec_res.sharpe, atol=1e-9)
    assert iter_res.trades == vec_res.trades
    assert np.allclose(iter_res.equity_curve, vec_res.equity_curve, atol=1e-10)



def test_vectorized_handles_flat_signal() -> None:
    prices = np.linspace(100.0, 120.0, 1200)
    signal = np.zeros_like(prices)
    res = run_vectorized_backtest(prices, signal)
    assert np.isclose(res.total_return, 0.0, atol=1e-12)
    assert res.trades == 0
