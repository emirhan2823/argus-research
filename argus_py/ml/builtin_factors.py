from __future__ import annotations

from typing import Callable, Dict

import numpy as np
import pandas as pd

FactorFn = Callable[[pd.DataFrame], pd.Series]


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def factor_return_1(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change(1)


def factor_return_5(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change(5)


def factor_rsi_14(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def factor_macd_hist(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    return macd - signal


def factor_bb_pctb_20(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    mean = close.rolling(window=20, min_periods=20).mean()
    std = close.rolling(window=20, min_periods=20).std(ddof=0)
    upper = mean + (2.0 * std)
    lower = mean - (2.0 * std)
    band = (upper - lower).replace(0.0, np.nan)
    pctb = (close - lower) / band
    return pctb.clip(lower=0.0, upper=1.0)


def factor_atr_pct_14(df: pd.DataFrame) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean()
    return (atr / close.replace(0.0, np.nan)) * 100.0


def factor_volume_zscore_20(df: pd.DataFrame) -> pd.Series:
    vol = df["volume"].astype(float)
    mean = vol.rolling(window=20, min_periods=20).mean()
    std = vol.rolling(window=20, min_periods=20).std(ddof=0).replace(0.0, np.nan)
    return (vol - mean) / std


def builtin_factor_map() -> Dict[str, FactorFn]:
    return {
        "ret_1": factor_return_1,
        "ret_5": factor_return_5,
        "rsi_14": factor_rsi_14,
        "macd_hist": factor_macd_hist,
        "bb_pctb_20": factor_bb_pctb_20,
        "atr_pct_14": factor_atr_pct_14,
        "vol_z_20": factor_volume_zscore_20,
    }
