"""Tests for correlation tracker module (Phase A)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.correlation.tracker import (
    CorrelationTracker,
    calculate_correlation,
    calculate_spread,
)


# ---------------------------------------------------------------------------
# calculate_correlation
# ---------------------------------------------------------------------------


class TestCalculateCorrelation:
    def test_perfectly_correlated(self):
        x = pd.Series(range(1, 201), dtype=float)
        y = pd.Series(range(1, 201), dtype=float)
        corr = calculate_correlation(x, y, window=100)
        assert abs(corr - 1.0) < 1e-6

    def test_negatively_correlated(self):
        x = pd.Series(range(1, 201), dtype=float)
        y = pd.Series(range(200, 0, -1), dtype=float)
        corr = calculate_correlation(x, y, window=100)
        assert abs(corr - (-1.0)) < 1e-6

    def test_short_series_fallback(self):
        """Series shorter than window should still return a valid value."""
        x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        y = pd.Series([2.0, 4.0, 6.0, 8.0, 10.0])
        corr = calculate_correlation(x, y, window=100)
        assert abs(corr - 1.0) < 1e-6

    def test_too_short_returns_zero(self):
        x = pd.Series([1.0])
        y = pd.Series([2.0])
        assert calculate_correlation(x, y) == 0.0

    def test_uncorrelated_noise(self):
        """Random noise should produce a correlation near zero."""
        rng = np.random.RandomState(42)
        x = pd.Series(rng.randn(500))
        y = pd.Series(rng.randn(500))
        corr = calculate_correlation(x, y, window=100)
        assert abs(corr) < 0.3


# ---------------------------------------------------------------------------
# calculate_spread
# ---------------------------------------------------------------------------


class TestCalculateSpread:
    def test_log_ratio_basic(self):
        a = pd.Series([100.0, 110.0, 105.0])
        b = pd.Series([50.0, 55.0, 52.5])
        spread = calculate_spread(a, b, method="log_ratio")
        expected = np.log(a / b)
        pd.testing.assert_series_equal(spread, expected)

    def test_zscore_method(self):
        a = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
        b = pd.Series([50.0, 55.0, 60.0, 65.0, 70.0])
        spread = calculate_spread(a, b, method="zscore")
        assert len(spread) == 5
        # Last value should be finite
        assert np.isfinite(spread.iloc[-1])

    def test_invalid_method_raises(self):
        a = pd.Series([1.0, 2.0])
        b = pd.Series([1.0, 2.0])
        with pytest.raises(ValueError, match="Unknown spread method"):
            calculate_spread(a, b, method="invalid")

    def test_log_ratio_equal_prices(self):
        """Equal prices should give spread of zero."""
        a = pd.Series([100.0, 100.0, 100.0])
        b = pd.Series([100.0, 100.0, 100.0])
        spread = calculate_spread(a, b, method="log_ratio")
        assert all(abs(s) < 1e-12 for s in spread)


# ---------------------------------------------------------------------------
# CorrelationTracker
# ---------------------------------------------------------------------------


class TestCorrelationTracker:
    @pytest.fixture()
    def tracker(self):
        config = [
            {"symbol_a": "BTCUSDT", "symbol_b": "ETHUSDT"},
            {"symbol_a": "BTCUSDT", "symbol_b": "SOLUSDT"},
        ]
        return CorrelationTracker(config, window=50)

    def test_pair_ids_auto_generated(self, tracker: CorrelationTracker):
        assert tracker.get_pair("BTCUSDT_ETHUSDT") is not None
        assert tracker.get_pair("BTCUSDT_SOLUSDT") is not None

    def test_get_pair_unknown_returns_none(self, tracker: CorrelationTracker):
        assert tracker.get_pair("UNKNOWN") is None

    def test_update_computes_correlations(self, tracker: CorrelationTracker):
        rng = np.random.RandomState(123)
        base = np.cumsum(rng.randn(200))
        prices = {
            "BTCUSDT": pd.Series(100 + base),
            "ETHUSDT": pd.Series(50 + base * 0.8 + rng.randn(200) * 0.5),
            "SOLUSDT": pd.Series(10 + rng.randn(200) * 5),
        }
        results = tracker.update(prices)
        assert len(results) == 2

        # BTC/ETH should be highly correlated (shared base trend)
        btc_eth = [r for r in results if r["pair_id"] == "BTCUSDT_ETHUSDT"][0]
        assert btc_eth["correlation"] > 0.5

    def test_update_missing_symbol_keeps_defaults(self, tracker: CorrelationTracker):
        """If a symbol is missing from prices, pair state is unchanged."""
        prices = {
            "BTCUSDT": pd.Series([100.0, 101.0, 102.0]),
            # ETHUSDT missing, SOLUSDT missing
        }
        results = tracker.update(prices)
        assert len(results) == 2
        for r in results:
            # Correlation should stay at default 0.0
            assert r["correlation"] == 0.0

    def test_custom_pair_id(self):
        config = [{"pair_id": "custom_id", "symbol_a": "A", "symbol_b": "B"}]
        tracker = CorrelationTracker(config)
        assert tracker.get_pair("custom_id") is not None
        assert tracker.get_pair("A_B") is None
