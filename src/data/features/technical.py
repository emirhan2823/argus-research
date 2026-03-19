"""ARGUS v2.0 technical features (17).

The implementation supports two paths:
- Preferred: `pandas_ta` when available.
- Fallback: dependency-free pandas/numpy formulas.

This avoids test collection failures on environments without pandas_ta.
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


def _ema(series: pd.Series, length: int) -> pd.Series:
    s = _as_float_series(series)
    w = max(1, int(length))
    return s.ewm(span=w, adjust=False, min_periods=w).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    h = _as_float_series(high)
    l = _as_float_series(low)
    c = _as_float_series(close)
    w = max(1, int(length))
    prev_close = c.shift(1)
    tr = pd.concat(
        [
            (h - l),
            (h - prev_close).abs(),
            (l - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    c = _as_float_series(close)
    w = max(1, int(length))
    delta = c.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    avg_loss = loss.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(avg_gain != 0.0, 0.0)
    return out


def _roc(close: pd.Series, length: int = 10) -> pd.Series:
    c = _as_float_series(close)
    w = max(1, int(length))
    return (c / c.shift(w) - 1.0) * 100.0


def _bbands(close: pd.Series, length: int = 20, std_mult: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    c = _as_float_series(close)
    w = max(1, int(length))
    mid = c.rolling(window=w, min_periods=w).mean()
    std = c.rolling(window=w, min_periods=w).std(ddof=0)
    upper = mid + float(std_mult) * std
    lower = mid - float(std_mult) * std
    return upper, mid, lower


def _adx_wilder(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    h = _as_float_series(high)
    l = _as_float_series(low)
    c = _as_float_series(close)
    w = max(1, int(length))

    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)

    tr = pd.concat(
        [
            (h - l),
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_w = tr.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean() / atr_w.replace(0.0, np.nan))
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean() / atr_w.replace(0.0, np.nan))
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)).fillna(0.0)
    return dx.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()


def _willr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    h = _as_float_series(high)
    l = _as_float_series(low)
    c = _as_float_series(close)
    w = max(1, int(length))
    highest = h.rolling(window=w, min_periods=w).max()
    lowest = l.rolling(window=w, min_periods=w).min()
    denom = (highest - lowest).replace(0.0, np.nan)
    return -100.0 * (highest - c) / denom


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 20) -> pd.Series:
    h = _as_float_series(high)
    l = _as_float_series(low)
    c = _as_float_series(close)
    tp = (h + l + c) / 3.0
    w = max(1, int(length))
    sma_tp = tp.rolling(window=w, min_periods=w).mean()
    mad = tp.rolling(window=w, min_periods=w).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    denom = (0.015 * mad).replace(0.0, np.nan)
    return (tp - sma_tp) / denom


def _atr_percentile(atr_series: pd.Series | None, lookback: int = 100) -> float | None:
    """Rolling percentile rank of current ATR within last `lookback` bars."""
    if atr_series is None or atr_series.empty:
        return None
    tail = atr_series.dropna().tail(lookback)
    if len(tail) < 20:
        return None
    current = float(tail.iloc[-1])
    return float((tail < current).sum() / len(tail))


def _aroon_oscillator(high: pd.Series, low: pd.Series, length: int = 14) -> float | None:
    w = max(2, int(length))
    h = _as_float_series(high).dropna().tail(w)
    l = _as_float_series(low).dropna().tail(w)
    if len(h) < 2 or len(l) < 2:
        return None
    periods_since_high = (len(h) - 1) - int(np.argmax(h.values))
    periods_since_low = (len(l) - 1) - int(np.argmin(l.values))
    aroon_up = 100.0 * (w - periods_since_high) / w
    aroon_down = 100.0 * (w - periods_since_low) / w
    return float(aroon_up - aroon_down)


def _supertrend_dir_fallback(close: pd.Series) -> int:
    ema_fast = _ema(close, 10)
    if ema_fast.empty:
        return 1
    c = float(close.iloc[-1])
    e = float(ema_fast.dropna().iloc[-1]) if not ema_fast.dropna().empty else c
    return 1 if c >= e else -1


def compute_technical_features(df: pd.DataFrame) -> dict[str, Optional[float]]:
    """Compute 17 technical features from OHLCV frame."""
    if len(df) < 20:
        raise ValueError(f"Need at least 20 rows, got {len(df)}")

    close = _as_float_series(df["close"])
    high = _as_float_series(df["high"])
    low = _as_float_series(df["low"])

    features: dict[str, Optional[float]] = {}
    last_close = float(close.iloc[-1])

    # Volatility (6)
    if ta is not None:
        atr_14_series = ta.atr(high, low, close, length=14)
    else:
        atr_14_series = _atr(high, low, close, length=14)
    features["atr_14"] = _last_valid(atr_14_series)

    atr_val = features["atr_14"]
    features["atr_14_pct"] = (atr_val / last_close) if atr_val is not None and last_close > 0.0 else None

    # ATR percentile rank over last 100 bars
    features["atr_pctl"] = _atr_percentile(atr_14_series)

    if ta is not None:
        atr_5 = _last_valid(ta.atr(high, low, close, length=5))
        atr_20 = _last_valid(ta.atr(high, low, close, length=20))
    else:
        atr_5 = _last_valid(_atr(high, low, close, length=5))
        atr_20 = _last_valid(_atr(high, low, close, length=20))
    features["atr_ratio_5_20"] = (atr_5 / atr_20) if atr_5 is not None and atr_20 is not None and atr_20 > 0.0 else None

    log_ret = np.log(close / close.shift(1)).dropna()
    features["realized_vol_20d"] = float(log_ret.tail(20).std() * np.sqrt(365.0)) if len(log_ret) >= 20 else None

    if len(df) >= 20:
        hl_ratio = np.log((high / low).replace([np.inf, -np.inf], np.nan)).dropna().tail(20)
        features["parkinson_vol"] = float(np.sqrt((1.0 / (4.0 * 20.0 * np.log(2.0))) * (hl_ratio.pow(2).sum()))) if len(hl_ratio) >= 2 else None
    else:
        features["parkinson_vol"] = None

    if ta is not None:
        bb = ta.bbands(close, length=20)
        if bb is not None and len(bb.columns) >= 3:
            bbu = float(bb.iloc[-1, 0])
            bbm = float(bb.iloc[-1, 1])
            bbl = float(bb.iloc[-1, 2])
        else:
            bbu = bbm = bbl = float("nan")
    else:
        bbu_s, bbm_s, bbl_s = _bbands(close, length=20, std_mult=2.0)
        bbu = float(bbu_s.iloc[-1]) if not bbu_s.empty else float("nan")
        bbm = float(bbm_s.iloc[-1]) if not bbm_s.empty else float("nan")
        bbl = float(bbl_s.iloc[-1]) if not bbl_s.empty else float("nan")
    features["bb_width"] = float((bbu - bbl) / bbm) if math.isfinite(bbm) and bbm > 0.0 and math.isfinite(bbu) and math.isfinite(bbl) else None

    # Trend (6)
    if ta is not None:
        adx_series = ta.adx(high, low, close, length=14)
        if adx_series is not None and "ADX_14" in adx_series.columns:
            features["adx_14"] = _last_valid(adx_series["ADX_14"])
        else:
            features["adx_14"] = None
    else:
        features["adx_14"] = _last_valid(_adx_wilder(high, low, close, length=14))

    if len(close) >= 200:
        ma200 = float(close.tail(200).mean())
    else:
        ma200 = float(close.mean())
    features["price_vs_ma200"] = (last_close / ma200 - 1.0) if ma200 > 0.0 else None

    if ta is not None:
        ema21 = ta.ema(close, length=21)
        ema55 = ta.ema(close, length=55)
    else:
        ema21 = _ema(close, 21)
        ema55 = _ema(close, 55)
    e21 = _last_valid(ema21)
    e55 = _last_valid(ema55)
    features["ema_21_vs_55"] = (e21 / e55 - 1.0) if e21 is not None and e55 is not None and e55 > 0.0 else None

    if len(close) >= 20:
        y = close.tail(20).values.astype(float)
        x = np.arange(len(y), dtype=float)
        slope = np.polyfit(x, y, 1)[0]
        features["lr_slope_20"] = float(slope / last_close) if last_close > 0.0 else None
    else:
        features["lr_slope_20"] = None

    if ta is not None:
        st = ta.supertrend(high, low, close, length=10, multiplier=3.0)
        if st is not None:
            d_col = [c for c in st.columns if c.startswith("SUPERTd")]
            if d_col:
                features["supertrend_dir"] = int(st[d_col[0]].iloc[-1])
            else:
                features["supertrend_dir"] = 1
        else:
            features["supertrend_dir"] = 1
    else:
        features["supertrend_dir"] = _supertrend_dir_fallback(close)

    if ta is not None:
        aroon = ta.aroon(high, low, length=14)
        if aroon is not None:
            up_col = [c for c in aroon.columns if "AROONU" in c]
            dn_col = [c for c in aroon.columns if "AROOND" in c]
            if up_col and dn_col:
                features["aroon_osc"] = float(aroon[up_col[0]].iloc[-1] - aroon[dn_col[0]].iloc[-1])
            else:
                features["aroon_osc"] = None
        else:
            features["aroon_osc"] = None
    else:
        features["aroon_osc"] = _aroon_oscillator(high, low, length=14)

    # Momentum (5)
    if ta is not None:
        rsi = ta.rsi(close, length=14)
    else:
        rsi = _rsi(close, length=14)
    features["rsi_14"] = _last_valid(rsi)

    if math.isfinite(bbu) and math.isfinite(bbl):
        denom = bbu - bbl
        features["bb_pct_b"] = float((last_close - bbl) / denom) if denom > 0.0 else 0.5
    else:
        features["bb_pct_b"] = None

    if ta is not None:
        roc = ta.roc(close, length=10)
    else:
        roc = _roc(close, length=10)
    features["roc_10"] = _last_valid(roc)

    if ta is not None:
        willr = ta.willr(high, low, close, length=14)
    else:
        willr = _willr(high, low, close, length=14)
    features["willr_14"] = _last_valid(willr)

    if ta is not None:
        cci = ta.cci(high, low, close, length=20)
    else:
        cci = _cci(high, low, close, length=20)
    features["cci_20"] = _last_valid(cci)

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
