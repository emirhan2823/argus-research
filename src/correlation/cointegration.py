"""Cointegration testing for asset pairs (A-03)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _adf_simple(series: np.ndarray, max_lags: int = 1) -> float:
    """Simplified ADF test returning an approximate p-value.

    This is a lightweight fallback when ``statsmodels`` is not available.
    Runs a Dickey-Fuller regression (no augmented lags) and maps the
    test statistic to an approximate p-value using critical-value
    interpolation from MacKinnon (1994) for the 'c' (constant) model.
    """
    y = series[1:]
    x = series[:-1]
    dy = y - x

    n = len(x)
    if n < 10:
        return 1.0  # not enough data

    # OLS: dy = alpha + phi * x[t-1] + eps
    ones = np.ones(n)
    X = np.column_stack([ones, x])
    try:
        beta = np.linalg.lstsq(X, dy, rcond=None)[0]
    except np.linalg.LinAlgError:
        return 1.0

    phi = beta[1]
    residuals = dy - X @ beta
    se_resid = float(np.sqrt(np.sum(residuals**2) / max(n - 2, 1)))
    if se_resid == 0:
        return 1.0

    se_phi = se_resid / float(np.sqrt(np.sum((x - np.mean(x)) ** 2)))
    if se_phi == 0:
        return 1.0

    adf_stat = phi / se_phi

    # Approximate p-value mapping (constant, no trend, MacKinnon 1994)
    # Critical values for n ~ 100: 1% = -3.51, 5% = -2.89, 10% = -2.58
    if adf_stat < -3.51:
        return 0.005
    elif adf_stat < -2.89:
        return 0.03
    elif adf_stat < -2.58:
        return 0.07
    elif adf_stat < -1.95:
        return 0.15
    else:
        return 0.50


def test_cointegration(
    prices_a: pd.Series,
    prices_b: pd.Series,
    significance: float = 0.05,
) -> tuple[bool, float]:
    """Engle-Granger two-step cointegration test.

    1. Regress ``prices_a`` on ``prices_b`` via OLS to get residuals.
    2. Run ADF test on residuals; if p-value < ``significance`` the pair
       is cointegrated.

    If ``statsmodels`` is available its ``adfuller`` implementation is
    used.  Otherwise a simplified ADF is employed.

    Returns
    -------
    tuple[bool, float]
        (is_cointegrated, p_value)
    """
    a = np.array(prices_a.dropna(), dtype=float)
    b = np.array(prices_b.dropna(), dtype=float)

    min_len = min(len(a), len(b))
    if min_len < 20:
        return (False, 1.0)

    a = a[:min_len]
    b = b[:min_len]

    # Step 1: OLS   a = alpha + beta * b + residual
    ones = np.ones(min_len)
    X = np.column_stack([ones, b])
    try:
        beta = np.linalg.lstsq(X, a, rcond=None)[0]
    except np.linalg.LinAlgError:
        return (False, 1.0)

    residuals = a - X @ beta

    # Step 2: ADF on residuals
    try:
        from statsmodels.tsa.stattools import adfuller  # type: ignore[import-untyped]

        adf_result = adfuller(residuals, autolag="AIC")
        pvalue = float(adf_result[1])
    except (ImportError, Exception):
        pvalue = _adf_simple(residuals)

    return (pvalue < significance, pvalue)
