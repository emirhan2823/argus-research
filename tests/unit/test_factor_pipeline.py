from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ml.factor_pipeline import FactorPipeline


def _ohlcv(n: int = 220) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 200 + np.cumsum(rng.normal(0.0, 1.0, size=n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + rng.uniform(0.2, 1.0, size=n)
    low = np.minimum(open_, close) - rng.uniform(0.2, 1.0, size=n)
    volume = rng.uniform(1000, 5000, size=n)
    idx = pd.date_range("2026-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )


def test_factor_pipeline_default_factors_compute() -> None:
    df = _ohlcv(240)
    pipe = FactorPipeline()
    out = pipe.compute(df)
    assert len(out) > 120
    assert "rsi_14" in out.columns
    assert "macd_hist" in out.columns
    assert "vol_z_20" in out.columns
    assert not out.isna().any().any()


def test_factor_pipeline_build_dataset_returns_aligned_target() -> None:
    df = _ohlcv(260)
    pipe = FactorPipeline()
    ds = pipe.build_dataset(df, horizon=3)
    assert ds.target is not None
    assert len(ds.factors) == len(ds.target)
    assert "ret_1" in ds.factors.columns
    assert ds.target.name == "target_ret"


def test_factor_pipeline_supports_custom_factor() -> None:
    df = _ohlcv(120)
    pipe = FactorPipeline()

    def custom_factor(frame: pd.DataFrame) -> pd.Series:
        return frame["close"].rolling(10, min_periods=10).mean()

    pipe.register("ma10", custom_factor)
    out = pipe.compute(df, factor_names=["ma10"], dropna=True)
    assert list(out.columns) == ["ma10"]
    assert len(out) > 0
