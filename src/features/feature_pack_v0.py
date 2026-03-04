"""Feature Pack v0 — lightweight trade-level feature snapshot.

Computes 11 indicators from raw OHLCV and returns a versioned dict
suitable for stapling onto trade records.  Does **not** touch the
frozen FeatureVector; works directly on a pandas DataFrame.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from src.data.features.technical import (
    _adx_wilder,
    _as_float_series,
    _atr,
    _atr_percentile,
    _ema,
    _last_valid,
    _rsi,
)


# ---------------------------------------------------------------------------
# Streak helpers
# ---------------------------------------------------------------------------

def _ll_streak(lows: pd.Series, max_pairs: int = 5) -> int:
    """Count consecutive lower-lows from the most recent bar backward.

    Examines up to *max_pairs* comparisons (requires max_pairs + 1 data
    points).  Returns 0 when the most recent bar is not a lower-low.
    """
    vals = _as_float_series(lows).dropna().tail(max_pairs + 1).values
    if len(vals) < 2:
        return 0
    streak = 0
    for i in range(len(vals) - 1, 0, -1):
        if vals[i] < vals[i - 1]:
            streak += 1
        else:
            break
    return streak


def _hh_streak(highs: pd.Series, max_pairs: int = 5) -> int:
    """Count consecutive higher-highs from the most recent bar backward.

    Mirror of :func:`_ll_streak` using ``>`` comparison on highs.
    """
    vals = _as_float_series(highs).dropna().tail(max_pairs + 1).values
    if len(vals) < 2:
        return 0
    streak = 0
    for i in range(len(vals) - 1, 0, -1):
        if vals[i] > vals[i - 1]:
            streak += 1
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

def compute_feature_pack_v0(df: pd.DataFrame) -> dict[str, Any]:
    """Compute Feature Pack v0 from an OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain at least ``high``, ``low``, ``close`` columns.
        ``volume`` is optional (not used in v0).
        Must have **>= 20 rows**.

    Returns
    -------
    dict[str, Any]
        Versioned feature dict.  All numeric values are ``float | int``
        or ``None`` when the indicator cannot be computed (insufficient
        data).  Never contains ``NaN`` or ``inf``.

    Raises
    ------
    ValueError
        If fewer than 20 rows are supplied.
    """
    if len(df) < 20:
        raise ValueError(f"Need >= 20 rows, got {len(df)}")

    close = _as_float_series(df["close"])
    high = _as_float_series(df["high"])
    low = _as_float_series(df["low"])

    result: dict[str, Any] = {"_version": 0}

    # ── EMAs ──────────────────────────────────────────────────────────
    ema21_s = _ema(close, 21)
    ema55_s = _ema(close, 55)
    ema21 = _last_valid(ema21_s)
    ema55 = _last_valid(ema55_s)
    result["ema_21"] = ema21
    result["ema_55"] = ema55
    if ema21 is not None and ema55 is not None and ema55 > 0:
        result["ema_spread_pct"] = (ema21 - ema55) / ema55
    else:
        result["ema_spread_pct"] = None

    # ── ADX + slope ───────────────────────────────────────────────────
    adx_s = _adx_wilder(high, low, close, length=14)
    result["adx_14"] = _last_valid(adx_s)

    clean_adx = adx_s.dropna()
    if len(clean_adx) >= 4:
        result["adx_slope"] = float(clean_adx.iloc[-1] - clean_adx.iloc[-4]) / 3.0
    else:
        result["adx_slope"] = None

    # ── ATR + percentile rank ─────────────────────────────────────────
    atr_s = _atr(high, low, close, length=14)
    atr_val = _last_valid(atr_s)
    last_close = float(close.iloc[-1])
    if atr_val is not None and last_close > 0:
        result["atr_14_pct"] = atr_val / last_close
    else:
        result["atr_14_pct"] = None

    # _atr_percentile already returns value in [0.0, 1.0] or None
    result["atr_percentile_rank"] = _atr_percentile(atr_s, lookback=100)

    # ── RSI + smooth ──────────────────────────────────────────────────
    rsi_s = _rsi(close, length=14)
    result["rsi_14"] = _last_valid(rsi_s)

    rsi_clean = rsi_s.dropna()
    if len(rsi_clean) >= 3:
        rsi_smooth_s = _ema(rsi_clean, 3)
        result["rsi_smooth"] = _last_valid(rsi_smooth_s)
    else:
        result["rsi_smooth"] = None

    # ── Streaks ───────────────────────────────────────────────────────
    result["ll_streak"] = _ll_streak(low, max_pairs=5)
    result["hh_streak"] = _hh_streak(high, max_pairs=5)

    # ── Sanitise: replace NaN / inf with None ─────────────────────────
    for k, v in list(result.items()):
        if k == "_version":
            continue
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            result[k] = None

    return result
