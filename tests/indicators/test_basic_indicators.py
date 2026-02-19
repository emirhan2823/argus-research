from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators.basic_indicators import (
    atr,
    bollinger,
    ema,
    log_returns,
    returns,
    rolling_vol,
    rsi,
    sma,
    zscore,
)


def _sample_ohlcv(n: int = 400) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    rng = np.random.default_rng(42)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0.0, 0.5, n)))
    high = close + np.abs(pd.Series(rng.normal(0.6, 0.15, n)))
    low = close - np.abs(pd.Series(rng.normal(0.6, 0.15, n)))
    open_ = close + pd.Series(rng.normal(0.0, 0.2, n))
    volume = pd.Series(rng.uniform(1_000, 10_000, n))
    return open_, high, low, close, volume


def test_sma_ema_shapes() -> None:
    _, _, _, close, _ = _sample_ohlcv()
    s = sma(close, 20)
    e = ema(close, 20)
    assert len(s) == len(close)
    assert len(e) == len(close)
    assert pd.notna(s.iloc[-1])
    assert pd.notna(e.iloc[-1])


def test_rsi_bounds_and_tail_not_nan() -> None:
    _, _, _, close, _ = _sample_ohlcv()
    out = rsi(close, 14)
    tail = out.tail(20).dropna()
    assert not tail.empty
    assert float(tail.min()) >= 0.0
    assert float(tail.max()) <= 100.0


def test_atr_positive_tail_not_nan() -> None:
    _, high, low, close, _ = _sample_ohlcv()
    out = atr(high, low, close, 14)
    tail = out.tail(20).dropna()
    assert not tail.empty
    assert float(tail.min()) > 0.0


def test_bollinger_ordering() -> None:
    _, _, _, close, _ = _sample_ohlcv()
    mid, upper, lower = bollinger(close, 20, 2.0)
    tail = pd.DataFrame({"m": mid, "u": upper, "l": lower}).tail(20).dropna()
    assert not tail.empty
    assert bool((tail["l"] <= tail["m"]).all())
    assert bool((tail["m"] <= tail["u"]).all())


def test_returns_vol_zscore_tail_not_nan() -> None:
    _, _, _, close, _ = _sample_ohlcv()
    r = returns(close)
    lr = log_returns(close)
    vol = rolling_vol(r, 20)
    z = zscore(close, 20)

    assert len(r) == len(close)
    assert len(lr) == len(close)
    assert len(vol) == len(close)
    assert len(z) == len(close)

    assert not vol.tail(20).dropna().empty
    assert not z.tail(20).dropna().empty
