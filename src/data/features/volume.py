"""ARGUS v2.0 — Volume features (5).

ALL asset classes use these features.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta


def compute_volume_features(df: pd.DataFrame) -> dict[str, Optional[float]]:
    """Compute 5 volume features from OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume].

    Returns:
        Dict with 5 volume feature keys.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    features: dict[str, Optional[float]] = {}

    # 1. Volume ratio (current volume / 20-period SMA of volume)
    vol_sma = volume.rolling(20).mean()
    if not vol_sma.empty and not pd.isna(vol_sma.iloc[-1]) and vol_sma.iloc[-1] > 0:
        features["volume_ratio"] = float(volume.iloc[-1] / vol_sma.iloc[-1])
    else:
        features["volume_ratio"] = None

    # 2. OBV slope 10
    obv = ta.obv(close, volume)
    if obv is not None and len(obv) >= 10:
        obv_tail = obv.tail(10).values.astype(float)
        x = np.arange(len(obv_tail), dtype=float)
        slope = np.polyfit(x, obv_tail, 1)[0]
        # Normalize by average OBV magnitude
        avg_obv = np.mean(np.abs(obv_tail))
        features["obv_slope_10"] = float(slope / avg_obv) if avg_obv > 0 else 0.0
    else:
        features["obv_slope_10"] = None

    # 3. VWAP deviation %
    # Simple VWAP approximation: cumulative(price * volume) / cumulative(volume)
    typical_price = (high + low + close) / 3.0
    cum_tpv = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    vwap = cum_tpv / cum_vol
    if not vwap.empty and not pd.isna(vwap.iloc[-1]) and vwap.iloc[-1] > 0:
        features["vwap_dev_pct"] = float(
            (close.iloc[-1] - vwap.iloc[-1]) / vwap.iloc[-1]
        )
    else:
        features["vwap_dev_pct"] = None

    # 4. CMF 20 (Chaikin Money Flow)
    cmf = ta.cmf(high, low, close, volume, length=20)
    features["cmf_20"] = _last_valid(cmf)

    # 5. Volume delta (buy volume - sell volume estimate)
    # Approximation: if close > open, volume is "buy"; else "sell"
    buy_vol = volume.where(close >= df["open"], 0)
    sell_vol = volume.where(close < df["open"], 0)
    total = volume.rolling(20).sum()
    if not total.empty and not pd.isna(total.iloc[-1]) and total.iloc[-1] > 0:
        net_delta = buy_vol.rolling(20).sum().iloc[-1] - sell_vol.rolling(20).sum().iloc[-1]
        features["volume_delta"] = float(net_delta / total.iloc[-1])
    else:
        features["volume_delta"] = None

    # Sanitize NaN
    for k, v in features.items():
        if v is not None and isinstance(v, float) and math.isnan(v):
            features[k] = None

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
