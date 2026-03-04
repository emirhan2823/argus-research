"""ARGUS v2.0 volume features (5).

Uses `pandas_ta` when present, otherwise deterministic pandas/numpy fallback.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

try:  # pragma: no cover - import availability depends on environment
    import pandas_ta as ta
except ModuleNotFoundError:  # pragma: no cover
    ta = None


def _as_float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    c = _as_float_series(close)
    v = _as_float_series(volume)
    direction = np.sign(c.diff().fillna(0.0))
    return (direction * v).cumsum()


def _cmf(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int = 20) -> pd.Series:
    h = _as_float_series(high)
    l = _as_float_series(low)
    c = _as_float_series(close)
    v = _as_float_series(volume)
    w = max(1, int(length))

    denom = (h - l).replace(0.0, np.nan)
    mfm = ((c - l) - (h - c)) / denom
    mfv = mfm.fillna(0.0) * v
    return mfv.rolling(window=w, min_periods=w).sum() / v.rolling(window=w, min_periods=w).sum().replace(0.0, np.nan)


def compute_volume_features(df: pd.DataFrame) -> dict[str, Optional[float]]:
    """Compute 5 volume features from OHLCV DataFrame."""
    close = _as_float_series(df["close"])
    high = _as_float_series(df["high"])
    low = _as_float_series(df["low"])
    volume = _as_float_series(df["volume"])

    features: dict[str, Optional[float]] = {}

    # 1) Volume ratio
    vol_sma = volume.rolling(20).mean()
    if not vol_sma.empty and not pd.isna(vol_sma.iloc[-1]) and vol_sma.iloc[-1] > 0.0:
        features["volume_ratio"] = float(volume.iloc[-1] / vol_sma.iloc[-1])
    else:
        features["volume_ratio"] = None

    # 2) OBV slope 10
    if ta is not None:
        obv = ta.obv(close, volume)
    else:
        obv = _obv(close, volume)
    if obv is not None and len(obv) >= 10:
        obv_tail = _as_float_series(obv.tail(10)).values.astype(float)
        x = np.arange(len(obv_tail), dtype=float)
        slope = np.polyfit(x, obv_tail, 1)[0]
        avg_obv = np.mean(np.abs(obv_tail))
        features["obv_slope_10"] = float(slope / avg_obv) if avg_obv > 0.0 else 0.0
    else:
        features["obv_slope_10"] = None

    # 3) VWAP deviation %
    typical_price = (high + low + close) / 3.0
    cum_tpv = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    vwap = cum_tpv / cum_vol.replace(0.0, np.nan)
    if not vwap.empty and not pd.isna(vwap.iloc[-1]) and vwap.iloc[-1] > 0.0:
        features["vwap_dev_pct"] = float((close.iloc[-1] - vwap.iloc[-1]) / vwap.iloc[-1])
    else:
        features["vwap_dev_pct"] = None

    # 4) CMF 20
    if ta is not None:
        cmf = ta.cmf(high, low, close, volume, length=20)
    else:
        cmf = _cmf(high, low, close, volume, length=20)
    features["cmf_20"] = _last_valid(cmf)

    # 5) Volume delta
    buy_vol = volume.where(close >= _as_float_series(df["open"]), 0.0)
    sell_vol = volume.where(close < _as_float_series(df["open"]), 0.0)
    total = volume.rolling(20).sum()
    if not total.empty and not pd.isna(total.iloc[-1]) and total.iloc[-1] > 0.0:
        net_delta = buy_vol.rolling(20).sum().iloc[-1] - sell_vol.rolling(20).sum().iloc[-1]
        features["volume_delta"] = float(net_delta / total.iloc[-1])
    else:
        features["volume_delta"] = None

    for key, value in list(features.items()):
        if value is not None and isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            features[key] = None
    return features


def _last_valid(series: Optional[pd.Series]) -> Optional[float]:
    """Extract last valid (non-NaN) value from a pandas Series."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        valid = series.dropna()
        if valid.empty:
            return None
        val = valid.iloc[-1]
    return float(val)
