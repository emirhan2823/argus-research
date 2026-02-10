"""ARGUS v2.0 — Statistical features (4).

ALL asset classes use these features.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def compute_statistical_features(df: pd.DataFrame) -> dict[str, Optional[float]]:
    """Compute 4 statistical features from OHLCV DataFrame.

    Args:
        df: DataFrame with at least a 'close' column. Needs 50+ rows ideally.

    Returns:
        Dict with 4 statistical feature keys.
    """
    close = df["close"]
    features: dict[str, Optional[float]] = {}

    log_ret = np.log(close / close.shift(1)).dropna()

    # 1. Return autocorrelation (lag-1, 20 period window)
    if len(log_ret) >= 20:
        features["return_autocorr_20"] = float(log_ret.tail(20).autocorr(lag=1))
    else:
        features["return_autocorr_20"] = None

    # 2. Hurst exponent (rescaled range method, simplified)
    if len(log_ret) >= 50:
        features["hurst_exponent"] = _hurst_rs(log_ret.tail(100).values if len(log_ret) >= 100 else log_ret.values)
    else:
        features["hurst_exponent"] = None

    # 3. Entropy (Shannon entropy of return distribution, 50 bins)
    if len(log_ret) >= 50:
        features["entropy_50"] = _shannon_entropy(log_ret.tail(50).values)
    else:
        features["entropy_50"] = None

    # 4. Fractional differentiation of price (simplified: d=0.5 fracdiff)
    if len(close) >= 50:
        features["frac_diff_price"] = _frac_diff_last(close.values, d=0.5)
    else:
        features["frac_diff_price"] = None

    # Sanitize
    for k, v in features.items():
        if v is not None and isinstance(v, float) and math.isnan(v):
            features[k] = None

    return features


def _hurst_rs(data: np.ndarray) -> Optional[float]:
    """Estimate Hurst exponent using rescaled range (R/S) method."""
    n = len(data)
    if n < 20:
        return None

    max_k = min(n // 2, 100)
    sizes = []
    rs_values = []

    for size in [16, 32, 64]:
        if size > max_k:
            continue
        n_chunks = n // size
        if n_chunks < 1:
            continue

        rs_list = []
        for i in range(n_chunks):
            chunk = data[i * size : (i + 1) * size]
            mean_c = np.mean(chunk)
            deviations = np.cumsum(chunk - mean_c)
            r = np.max(deviations) - np.min(deviations)
            s = np.std(chunk, ddof=1)
            if s > 0:
                rs_list.append(r / s)

        if rs_list:
            sizes.append(np.log(size))
            rs_values.append(np.log(np.mean(rs_list)))

    if len(sizes) < 2:
        return 0.5  # default: random walk

    slope = np.polyfit(sizes, rs_values, 1)[0]
    return float(np.clip(slope, 0.0, 1.0))


def _shannon_entropy(data: np.ndarray, bins: int = 50) -> float:
    """Compute Shannon entropy of a distribution."""
    counts, _ = np.histogram(data, bins=bins)
    probs = counts / counts.sum()
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))


def _frac_diff_last(prices: np.ndarray, d: float = 0.5, threshold: float = 1e-5) -> Optional[float]:
    """Compute the last value of fractionally differentiated price series.

    Uses fixed-width window fractional differentiation (from mlfinlab).
    """
    n = len(prices)
    if n < 10:
        return None

    # Compute weights
    weights = [1.0]
    for k in range(1, n):
        w = -weights[-1] * (d - k + 1) / k
        if abs(w) < threshold:
            break
        weights.append(w)

    weights = np.array(weights[::-1])  # reverse for convolution
    w_len = len(weights)

    if w_len > n:
        return None

    # Apply to the last window
    window = prices[n - w_len : n]
    result = float(np.dot(weights, window))
    return result
