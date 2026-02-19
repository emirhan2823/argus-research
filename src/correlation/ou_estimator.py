"""Ornstein-Uhlenbeck process estimation (A-05, A-06)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_half_life(spread: pd.Series) -> float | None:
    """Estimate the half-life of mean reversion via AR(1) regression.

    Fits  spread[t] - spread[t-1] = phi * spread[t-1] + eps
    and computes half-life = -log(2) / log(1 + phi).

    Returns
    -------
    float | None
        Half-life in bars, or ``None`` if the series is not mean-reverting
        (phi >= 0 or half-life is non-positive / undefined).
    """
    spread = spread.dropna()
    if len(spread) < 10:
        return None

    y = np.array(spread.iloc[1:] - spread.iloc[:-1].values, dtype=float)
    x = np.array(spread.iloc[:-1], dtype=float)

    # OLS: y = phi * x + eps  =>  phi = (x'y) / (x'x)
    x_dot_x = float(np.dot(x, x))
    if x_dot_x == 0:
        return None
    phi = float(np.dot(x, y)) / x_dot_x

    # Mean-reverting requires phi < 0
    if phi >= 0:
        return None

    # half_life = -log(2) / log(1 + phi)
    inner = 1.0 + phi
    if inner <= 0:
        return None

    log_inner = np.log(inner)
    if log_inner == 0:
        return None

    half_life = -np.log(2) / log_inner
    if half_life <= 0:
        return None

    return float(half_life)


def fit_ou_process(spread: pd.Series) -> tuple[float, float, float]:
    """Fit an Ornstein-Uhlenbeck process to the spread.

    The discrete OU model is:
        dX = theta * (mu - X) * dt + sigma * dW

    We estimate via AR(1) regression:
        X[t] = a + b * X[t-1] + eps

    Then:
        theta = -log(b)          (speed of reversion)
        mu    = a / (1 - b)      (long-run mean)
        sigma = std(eps) * sqrt(-2 * log(b) / (1 - b^2))

    Returns
    -------
    tuple[float, float, float]
        (theta, mu, sigma).  If estimation fails, returns (0.0, 0.0, 0.0).
    """
    spread = spread.dropna()
    if len(spread) < 10:
        return (0.0, 0.0, 0.0)

    y = np.array(spread.iloc[1:], dtype=float)
    x = np.array(spread.iloc[:-1], dtype=float)

    n = len(x)
    # OLS: y = a + b * x
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))

    ss_xx = float(np.dot(x - x_mean, x - x_mean))
    if ss_xx == 0:
        return (0.0, 0.0, 0.0)

    ss_xy = float(np.dot(x - x_mean, y - y_mean))
    b = ss_xy / ss_xx
    a = y_mean - b * x_mean

    # b must be in (0, 1) for a stationary OU
    if b <= 0 or b >= 1:
        return (0.0, 0.0, 0.0)

    theta = -np.log(b)
    mu = a / (1.0 - b)

    residuals = y - (a + b * x)
    eps_std = float(np.std(residuals, ddof=1)) if n > 2 else float(np.std(residuals))

    denom = 1.0 - b**2
    if denom <= 0:
        return (float(theta), float(mu), 0.0)

    sigma = eps_std * np.sqrt(2.0 * theta / denom)

    return (float(theta), float(mu), float(sigma))
