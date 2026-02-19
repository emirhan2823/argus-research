"""Basic technical indicators implemented with pandas/numpy only.

These functions are intentionally lightweight and dependency-free so the
pipeline can run on Python 3.11 environments where ``pandas_ta`` is not
available.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _as_float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    s = _as_float_series(series)
    w = max(1, int(window))
    return s.rolling(window=w, min_periods=w).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential moving average (EMA)."""
    s = _as_float_series(series)
    w = max(1, int(window))
    return s.ewm(span=w, adjust=False, min_periods=w).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder RSI.

    Uses Wilder smoothing (alpha=1/window) for average gains/losses.
    """
    c = _as_float_series(close)
    w = max(1, int(window))

    delta = c.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    avg_loss = loss.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))

    # Edge cases: no losses => RSI 100, no gains => RSI 0
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(avg_gain != 0.0, 0.0)
    return out


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range with Wilder smoothing."""
    h = _as_float_series(high)
    l = _as_float_series(low)
    c = _as_float_series(close)
    w = max(1, int(window))

    prev_close = c.shift(1)
    tr1 = h - l
    tr2 = (h - prev_close).abs()
    tr3 = (l - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()


def bollinger(close: pd.Series, window: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger bands: (mid, upper, lower)."""
    c = _as_float_series(close)
    w = max(1, int(window))
    mid = sma(c, w)
    std = c.rolling(window=w, min_periods=w).std(ddof=0)
    upper = mid + float(k) * std
    lower = mid - float(k) * std
    return mid, upper, lower


def returns(close: pd.Series) -> pd.Series:
    """Simple returns."""
    c = _as_float_series(close)
    return c.pct_change()


def log_returns(close: pd.Series) -> pd.Series:
    """Log returns."""
    c = _as_float_series(close)
    return np.log(c / c.shift(1))


def rolling_vol(ret: pd.Series, window: int) -> pd.Series:
    """Rolling volatility (standard deviation)."""
    r = _as_float_series(ret)
    w = max(1, int(window))
    return r.rolling(window=w, min_periods=w).std(ddof=0)


def zscore(series: pd.Series, window: int) -> pd.Series:
    """Rolling z-score."""
    s = _as_float_series(series)
    w = max(1, int(window))
    mean = s.rolling(window=w, min_periods=w).mean()
    std = s.rolling(window=w, min_periods=w).std(ddof=0)
    return (s - mean) / std.replace(0.0, np.nan)
