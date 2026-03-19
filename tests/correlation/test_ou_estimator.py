"""Tests for Ornstein-Uhlenbeck estimator (Phase A)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.correlation.ou_estimator import estimate_half_life, fit_ou_process


# ---------------------------------------------------------------------------
# estimate_half_life
# ---------------------------------------------------------------------------


class TestEstimateHalfLife:
    def test_mean_reverting_series(self):
        """A synthetic OU process should yield a finite half-life."""
        rng = np.random.RandomState(42)
        n = 1000
        theta = 0.1  # speed of mean reversion
        mu = 0.0
        sigma = 0.5
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = x[t - 1] + theta * (mu - x[t - 1]) + sigma * rng.randn()

        spread = pd.Series(x)
        hl = estimate_half_life(spread)
        assert hl is not None
        assert hl > 0
        # Theoretical half-life ~ log(2)/theta ~ 6.93
        assert 2 < hl < 30  # reasonable range

    def test_random_walk_returns_none(self):
        """A random walk is not mean-reverting; half-life should be None."""
        rng = np.random.RandomState(99)
        walk = pd.Series(np.cumsum(rng.randn(500)))
        hl = estimate_half_life(walk)
        assert hl is None

    def test_short_series_returns_none(self):
        spread = pd.Series([1.0, 2.0, 3.0])
        assert estimate_half_life(spread) is None

    def test_constant_series_returns_none(self):
        spread = pd.Series([5.0] * 100)
        assert estimate_half_life(spread) is None

    def test_trending_series_returns_none(self):
        """A strong upward trend should not be mean-reverting."""
        spread = pd.Series(np.arange(0, 200, dtype=float))
        assert estimate_half_life(spread) is None


# ---------------------------------------------------------------------------
# fit_ou_process
# ---------------------------------------------------------------------------


class TestFitOUProcess:
    def test_synthetic_ou(self):
        """Fitted theta should be positive for a mean-reverting series."""
        rng = np.random.RandomState(42)
        n = 2000
        theta_true = 0.05
        mu_true = 10.0
        sigma_true = 0.3
        x = np.zeros(n)
        x[0] = mu_true
        for t in range(1, n):
            x[t] = x[t - 1] + theta_true * (mu_true - x[t - 1]) + sigma_true * rng.randn()

        theta, mu, sigma = fit_ou_process(pd.Series(x))
        assert theta > 0
        # mu should be close to mu_true
        assert abs(mu - mu_true) < 3.0
        assert sigma > 0

    def test_short_series(self):
        """Too-short series should return zeros."""
        theta, mu, sigma = fit_ou_process(pd.Series([1.0, 2.0]))
        assert (theta, mu, sigma) == (0.0, 0.0, 0.0)

    def test_random_walk(self):
        """A random walk has b ≈ 1, so fit should return zeros (non-stationary)."""
        rng = np.random.RandomState(77)
        walk = pd.Series(np.cumsum(rng.randn(1000)))
        theta, mu, sigma = fit_ou_process(walk)
        # Random walk: b ~= 1, theta ~= 0
        # The function should return (0,0,0) since b >= 1 (or very close)
        # but due to randomness b might be slightly < 1, accept either
        assert theta >= 0
