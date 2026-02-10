"""ARGUS v2.0 — Technical features: Volatility(6) + Trend(6) + Momentum(5) = 17.

ALL asset classes use these features.
Input: pandas DataFrame with OHLCV columns (open, high, low, close, volume).
Output: dict of feature name → float value (latest bar).
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta


def compute_technical_features(df: pd.DataFrame) -> dict[str, Optional[float]]:
    """Compute 17 technical features from OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume].
            Must have at least 200 rows for MA200.

    Returns:
        Dict with 17 feature keys. Values are float or NaN if insufficient data.
    """
    if len(df) < 20:
        raise ValueError(f"Need at least 20 rows, got {len(df)}")

    close = df["close"]
    high = df["high"]
    low = df["low"]

    features: dict[str, Optional[float]] = {}

    # ── Volatility (6) ─────────────────────────────────────────────

    # ATR 14
    atr_14_series = ta.atr(high, low, close, length=14)
    features["atr_14"] = _last_valid(atr_14_series)

    # ATR 14 as % of price
    atr_val = features["atr_14"]
    last_close = float(close.iloc[-1])
    features["atr_14_pct"] = (
        (atr_val / last_close) if atr_val is not None and last_close > 0 else None
    )

    # ATR ratio 5/20
    atr_5 = _last_valid(ta.atr(high, low, close, length=5))
    atr_20 = _last_valid(ta.atr(high, low, close, length=20))
    features["atr_ratio_5_20"] = (
        (atr_5 / atr_20) if atr_5 is not None and atr_20 is not None and atr_20 > 0 else None
    )

    # Realized volatility 20d (annualized std of log returns)
    log_ret = np.log(close / close.shift(1)).dropna()
    if len(log_ret) >= 20:
        features["realized_vol_20d"] = float(log_ret.tail(20).std() * np.sqrt(365))
    else:
        features["realized_vol_20d"] = None

    # Parkinson volatility (uses high/low range)
    if len(df) >= 20:
        hl_ratio = np.log(high / low).tail(20)
        features["parkinson_vol"] = float(
            np.sqrt((1 / (4 * 20 * np.log(2))) * (hl_ratio**2).sum())
        )
    else:
        features["parkinson_vol"] = None

    # Bollinger Band width
    bb = ta.bbands(close, length=20)
    if bb is not None and len(bb.columns) >= 3:
        bbu = bb.iloc[-1, 0]  # upper
        bbl = bb.iloc[-1, 2]  # lower
        bbm = bb.iloc[-1, 1]  # mid
        features["bb_width"] = float((bbu - bbl) / bbm) if bbm > 0 else None
    else:
        features["bb_width"] = None

    # ── Trend (6) ──────────────────────────────────────────────────

    # ADX 14
    adx_series = ta.adx(high, low, close, length=14)
    if adx_series is not None and "ADX_14" in adx_series.columns:
        features["adx_14"] = _last_valid(adx_series["ADX_14"])
    else:
        features["adx_14"] = None

    # Price vs MA200
    if len(close) >= 200:
        ma200 = float(close.tail(200).mean())
        features["price_vs_ma200"] = (last_close / ma200 - 1.0) if ma200 > 0 else None
    else:
        # Use available data MA as fallback
        ma_n = float(close.mean())
        features["price_vs_ma200"] = (last_close / ma_n - 1.0) if ma_n > 0 else None

    # EMA 21 vs EMA 55
    ema21 = ta.ema(close, length=21)
    ema55 = ta.ema(close, length=55)
    if ema21 is not None and ema55 is not None:
        e21 = _last_valid(ema21)
        e55 = _last_valid(ema55)
        features["ema_21_vs_55"] = (
            (e21 / e55 - 1.0) if e21 is not None and e55 is not None and e55 > 0 else None
        )
    else:
        features["ema_21_vs_55"] = None

    # Linear regression slope 20
    if len(close) >= 20:
        y = close.tail(20).values.astype(float)
        x = np.arange(len(y), dtype=float)
        slope = np.polyfit(x, y, 1)[0]
        features["lr_slope_20"] = float(slope / last_close) if last_close > 0 else None
    else:
        features["lr_slope_20"] = None

    # Supertrend direction
    st = ta.supertrend(high, low, close, length=10, multiplier=3.0)
    if st is not None:
        # pandas_ta supertrend: SUPERTd_10_3.0 column, +1 or -1
        d_col = [c for c in st.columns if c.startswith("SUPERTd")]
        if d_col:
            features["supertrend_dir"] = int(st[d_col[0]].iloc[-1])
        else:
            features["supertrend_dir"] = 1
    else:
        features["supertrend_dir"] = 1

    # Aroon oscillator
    aroon = ta.aroon(high, low, length=14)
    if aroon is not None:
        up_col = [c for c in aroon.columns if "AROONU" in c]
        dn_col = [c for c in aroon.columns if "AROOND" in c]
        if up_col and dn_col:
            features["aroon_osc"] = float(
                aroon[up_col[0]].iloc[-1] - aroon[dn_col[0]].iloc[-1]
            )
        else:
            features["aroon_osc"] = None
    else:
        features["aroon_osc"] = None

    # ── Momentum (5) ───────────────────────────────────────────────

    # RSI 14
    rsi = ta.rsi(close, length=14)
    features["rsi_14"] = _last_valid(rsi)

    # Bollinger %B
    if bb is not None and len(bb.columns) >= 3:
        bbu_val = float(bb.iloc[-1, 0])
        bbl_val = float(bb.iloc[-1, 2])
        denom = bbu_val - bbl_val
        features["bb_pct_b"] = float((last_close - bbl_val) / denom) if denom > 0 else 0.5
    else:
        features["bb_pct_b"] = None

    # ROC 10
    roc = ta.roc(close, length=10)
    features["roc_10"] = _last_valid(roc)

    # Williams %R 14
    willr = ta.willr(high, low, close, length=14)
    features["willr_14"] = _last_valid(willr)

    # CCI 20
    cci = ta.cci(high, low, close, length=20)
    features["cci_20"] = _last_valid(cci)

    # ── Sanitize: replace NaN with None ────────────────────────────
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
        # Try last valid
        valid = series.dropna()
        if valid.empty:
            return None
        val = valid.iloc[-1]
    return float(val)
