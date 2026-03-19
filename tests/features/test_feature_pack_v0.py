"""Unit tests for Feature Pack v0 — trade-level feature snapshot."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.feature_pack_v0 import compute_feature_pack_v0


# ---------------------------------------------------------------------------
# Synthetic OHLCV helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(
    n: int = 120,
    base: float = 100.0,
    trend: float = 0.0,
    vol: float = 0.5,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV with controllable trend and noise.

    Parameters
    ----------
    trend : float
        Per-bar drift.  >0 = uptrend, <0 = downtrend, 0 = random walk.
    vol : float
        Noise magnitude (std of per-bar Gaussian increments).
    """
    rng = np.random.RandomState(seed)
    drift = np.arange(n) * trend
    noise = np.cumsum(rng.randn(n) * vol)
    close = base + drift + noise
    # Ensure positive prices
    close = np.maximum(close, 1.0)
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    low = np.maximum(low, 0.5)
    return pd.DataFrame({
        "open": close + rng.randn(n) * 0.1,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.uniform(100, 1000, n),
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFeaturePackV0:
    def test_returns_version_key(self) -> None:
        result = compute_feature_pack_v0(_make_ohlcv(120))
        assert result["_version"] == 0

    def test_all_fields_present(self) -> None:
        result = compute_feature_pack_v0(_make_ohlcv(120))
        expected_keys = {
            "_version",
            "ema_21", "ema_55", "ema_spread_pct",
            "adx_14", "adx_slope",
            "atr_14_pct", "atr_percentile_rank",
            "rsi_14", "rsi_smooth",
            "ll_streak", "hh_streak",
        }
        assert set(result.keys()) == expected_keys

    def test_ema_spread_sign_uptrend(self) -> None:
        """In a strong uptrend, EMA21 > EMA55 → spread > 0."""
        df = _make_ohlcv(120, trend=0.5, vol=0.2, seed=7)
        result = compute_feature_pack_v0(df)
        assert result["ema_spread_pct"] is not None
        assert result["ema_spread_pct"] > 0

    def test_ema_spread_sign_downtrend(self) -> None:
        """In a strong downtrend, EMA21 < EMA55 → spread < 0."""
        df = _make_ohlcv(120, base=200.0, trend=-0.5, vol=0.2, seed=7)
        result = compute_feature_pack_v0(df)
        assert result["ema_spread_pct"] is not None
        assert result["ema_spread_pct"] < 0

    def test_adx_higher_in_trending(self) -> None:
        """ADX should be higher in strongly trending data vs random walk."""
        trending = compute_feature_pack_v0(_make_ohlcv(120, trend=0.8, vol=0.1, seed=99))
        random_walk = compute_feature_pack_v0(_make_ohlcv(120, trend=0.0, vol=0.5, seed=99))
        assert trending["adx_14"] is not None
        assert random_walk["adx_14"] is not None
        assert trending["adx_14"] > random_walk["adx_14"]

    def test_adx_slope_computed(self) -> None:
        result = compute_feature_pack_v0(_make_ohlcv(120))
        assert result["adx_slope"] is not None
        assert isinstance(result["adx_slope"], float)

    def test_atr_percentile_increases_with_volatility(self) -> None:
        """Higher vol data should yield higher ATR percentile rank."""
        low_vol = compute_feature_pack_v0(_make_ohlcv(120, vol=0.1, seed=5))
        high_vol = compute_feature_pack_v0(_make_ohlcv(120, vol=2.0, seed=5))
        # At least one should be non-None
        if low_vol["atr_percentile_rank"] is not None and high_vol["atr_percentile_rank"] is not None:
            assert high_vol["atr_percentile_rank"] >= low_vol["atr_percentile_rank"]

    def test_atr_percentile_bounded(self) -> None:
        result = compute_feature_pack_v0(_make_ohlcv(120))
        rank = result["atr_percentile_rank"]
        if rank is not None:
            assert 0.0 <= rank <= 1.0

    def test_rsi_smooth_bounded(self) -> None:
        result = compute_feature_pack_v0(_make_ohlcv(120))
        rsi_s = result["rsi_smooth"]
        assert rsi_s is not None
        assert 0.0 <= rsi_s <= 100.0

    def test_ll_streak_known_sequence(self) -> None:
        """Lows [12, 10, 9, 8, 7, 6] → 5 consecutive lower-lows."""
        df = _make_ohlcv(120)
        df.iloc[-6:, df.columns.get_loc("low")] = [12.0, 10.0, 9.0, 8.0, 7.0, 6.0]
        result = compute_feature_pack_v0(df)
        assert result["ll_streak"] == 5

    def test_hh_streak_known_sequence(self) -> None:
        """Highs [100, 101, 102, 103, 104, 105] → 5 consecutive higher-highs."""
        df = _make_ohlcv(120)
        df.iloc[-6:, df.columns.get_loc("high")] = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        result = compute_feature_pack_v0(df)
        assert result["hh_streak"] == 5

    def test_no_streak_alternating(self) -> None:
        """Alternating lows [10, 12, 10, 12, 10, 12] → streak = 0."""
        df = _make_ohlcv(120)
        df.iloc[-6:, df.columns.get_loc("low")] = [10.0, 12.0, 10.0, 12.0, 10.0, 12.0]
        result = compute_feature_pack_v0(df)
        assert result["ll_streak"] == 0

    def test_minimum_bars_raises(self) -> None:
        df = _make_ohlcv(15)
        with pytest.raises(ValueError, match="Need >= 20"):
            compute_feature_pack_v0(df)

    def test_no_nan_or_inf_in_output(self) -> None:
        result = compute_feature_pack_v0(_make_ohlcv(120))
        for k, v in result.items():
            if k == "_version":
                continue
            if v is not None and isinstance(v, float):
                assert np.isfinite(v), f"{k} is not finite: {v}"

    def test_short_data_graceful(self) -> None:
        """With 25 bars, core fields compute; percentile may be None."""
        df = _make_ohlcv(25)
        result = compute_feature_pack_v0(df)
        assert result["ema_21"] is not None
        assert result["rsi_14"] is not None
        # atr_percentile_rank needs >=20 clean ATR values — may or may not compute
        # Just verify no crash and it's either None or in [0, 1]
        rank = result["atr_percentile_rank"]
        assert rank is None or (0.0 <= rank <= 1.0)
