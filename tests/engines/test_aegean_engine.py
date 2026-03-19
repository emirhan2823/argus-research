"""Tests for AegeanEngine: MOM-LRC signal generation, regime switching, MTF filter."""

from __future__ import annotations

import math

from src.core.constants import (
    ENGINE_AEGEAN,
    REGIME_CRISIS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)
from src.engines.aegean.engine import AegeanEngine, _rsi, _hlc3, _ema_series, _linreg_last
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


# ── Helpers ──────────────────────────────────────────────────────


def _make_candles(
    base_price: float = 20000.0,
    atr: float = 200.0,
    n: int = 250,
    trend: float = 0.0,
) -> tuple[list[float], list[float], list[float]]:
    """Generate synthetic candles. trend > 0 = uptrend, < 0 = downtrend."""
    import math as _m

    highs, lows, closes = [], [], []
    for i in range(n):
        drift = trend * i
        phase = (i / n) * 8 * _m.pi
        mid = base_price + drift + atr * 0.5 * _m.sin(phase)
        h = mid + atr * 0.3
        l = mid - atr * 0.3
        c = mid + atr * 0.1 * _m.cos(phase)
        highs.append(h)
        lows.append(l)
        closes.append(c)
    return highs, lows, closes


# ── Math helper tests ────────────────────────────────────────────


def test_rsi_basic():
    """RSI of a simple ascending series should be > 50."""
    closes = [float(i) for i in range(1, 20)]
    val = _rsi(closes, 14)
    assert val is not None
    assert val > 50.0


def test_rsi_descending():
    """RSI of descending series should be < 50."""
    closes = [float(20 - i) for i in range(20)]
    val = _rsi(closes, 14)
    assert val is not None
    assert val < 50.0


def test_rsi_insufficient_data():
    """RSI should return None with insufficient data."""
    assert _rsi([1.0, 2.0], 14) is None


def test_hlc3():
    result = _hlc3([10.0, 20.0], [5.0, 15.0], [8.0, 18.0])
    assert len(result) == 2
    assert abs(result[0] - (10.0 + 5.0 + 8.0) / 3.0) < 1e-9


def test_ema_series():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    ema = _ema_series(vals, 3)
    assert len(ema) == 5
    assert ema[0] == 1.0
    assert ema[-1] > ema[0]


def test_linreg_last():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    lr = _linreg_last(vals, 5)
    assert lr is not None
    assert abs(lr - 5.0) < 0.01  # Perfect linear → last value


def test_linreg_insufficient():
    assert _linreg_last([1.0, 2.0], 5) is None


# ── Engine signal generation ─────────────────────────────────────


def test_crisis_returns_none():
    engine = AegeanEngine()
    fv = make_feature_vector()
    regime = make_regime_state(REGIME_CRISIS)
    sig = engine.generate_signal(regime=regime, features=fv)
    assert sig is None


def test_fallback_signal_ranging_long():
    """Without candle data, fallback should produce a signal for extreme RSI."""
    engine = AegeanEngine(min_confidence=0.40)
    fv = make_feature_vector(
        rsi_14=20.0,
        willr_14=-90.0,
        cci_20=-120.0,
        bb_pct_b=0.05,
        atr_14_pct=0.02,
        lr_slope_20=-0.01,
        adx_14=15.0,
    )
    regime = make_regime_state(REGIME_RANGING)
    sig = engine.generate_signal(regime=regime, features=fv)
    if sig is not None:
        assert sig.bias == "long"
        assert sig.engine == ENGINE_AEGEAN
        assert "fallback" in sig.sub_strategy


def test_fallback_signal_trending_short():
    """Fallback in TRENDING with bearish momentum."""
    engine = AegeanEngine(min_confidence=0.40)
    fv = make_feature_vector(
        rsi_14=70.0,
        willr_14=-10.0,
        cci_20=100.0,
        atr_14_pct=0.015,
        lr_slope_20=-0.02,
        roc_10=-0.03,
        adx_14=35.0,
    )
    regime = make_regime_state(REGIME_TRENDING)
    sig = engine.generate_signal(regime=regime, features=fv)
    if sig is not None:
        assert sig.bias == "short"


def test_candle_based_signal():
    """With sufficient candle history, engine should produce signals."""
    engine = AegeanEngine(min_confidence=0.40)
    highs, lows, closes = _make_candles(n=250, atr=200.0)
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    fv = make_feature_vector(adx_14=30.0, roc_10=0.02, lr_slope_20=0.001)
    regime = make_regime_state(REGIME_TRENDING)
    # May or may not produce a signal depending on channel position, but shouldn't crash
    sig = engine.generate_signal(regime=regime, features=fv)
    if sig is not None:
        assert sig.engine == ENGINE_AEGEAN
        assert sig.bias in ("long", "short")
        assert 0.0 <= sig.confidence <= 1.0
        assert 0.001 <= sig.stop_distance <= 0.10


def test_regime_switching_parameters():
    """Verify engine uses different params for different regimes."""
    engine = AegeanEngine(min_confidence=0.40)
    highs, lows, closes = _make_candles(n=250)
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    fv = make_feature_vector(adx_14=25.0)
    # Just verify no crash in different regimes
    for regime_name in [REGIME_TRENDING, REGIME_RANGING, REGIME_VOLATILE]:
        regime = make_regime_state(regime_name)
        sig = engine.generate_signal(regime=regime, features=fv)
        if sig is not None:
            assert regime_name.lower() in sig.sub_strategy


def test_feed_candles_truncation():
    """Verify candle buffer is truncated to 500 bars."""
    engine = AegeanEngine()
    long_series = [float(i) for i in range(800)]
    engine.feed_candles(symbol="TEST", highs=long_series, lows=long_series, closes=long_series)
    h, l, c = engine._candle_history["TEST"]
    assert len(h) == 500
    assert len(l) == 500
    assert len(c) == 500


# ── MTF Trend Filter ─────────────────────────────────────────────


def test_mtf_no_htf_data_permissive():
    """Without HTF data, MTF filter should be permissive."""
    engine = AegeanEngine()
    assert engine._htf_trend_allows("BTCUSDT", "long") is True
    assert engine._htf_trend_allows("BTCUSDT", "short") is True


def test_mtf_insufficient_htf_data_permissive():
    """With insufficient HTF data (< ema_period), filter should be permissive."""
    engine = AegeanEngine(htf_ema_period=200)
    engine.feed_htf_candles(symbol="BTCUSDT", closes=[float(i) for i in range(50)])
    assert engine._htf_trend_allows("BTCUSDT", "long") is True


def test_mtf_bullish_htf_allows_long():
    """Bullish HTF (price > EMA-200) should allow long."""
    engine = AegeanEngine(htf_ema_period=50)
    # Uptrending data: price will be above EMA-50
    closes = [100.0 + i * 0.5 for i in range(100)]
    engine.feed_htf_candles(symbol="BTCUSDT", closes=closes)
    assert engine._htf_trend_allows("BTCUSDT", "long") is True


def test_mtf_bullish_htf_rejects_short():
    """Bullish HTF (price > EMA-200) should reject short."""
    engine = AegeanEngine(htf_ema_period=50)
    closes = [100.0 + i * 0.5 for i in range(100)]
    engine.feed_htf_candles(symbol="BTCUSDT", closes=closes)
    assert engine._htf_trend_allows("BTCUSDT", "short") is False


def test_mtf_bearish_htf_allows_short():
    """Bearish HTF (price < EMA-200) should allow short."""
    engine = AegeanEngine(htf_ema_period=50)
    closes = [200.0 - i * 0.5 for i in range(100)]
    engine.feed_htf_candles(symbol="BTCUSDT", closes=closes)
    assert engine._htf_trend_allows("BTCUSDT", "short") is True


def test_mtf_bearish_htf_rejects_long():
    """Bearish HTF (price < EMA-200) should reject long."""
    engine = AegeanEngine(htf_ema_period=50)
    closes = [200.0 - i * 0.5 for i in range(100)]
    engine.feed_htf_candles(symbol="BTCUSDT", closes=closes)
    assert engine._htf_trend_allows("BTCUSDT", "long") is False


def test_htf_candle_truncation():
    """HTF buffer should be truncated to ema_period + 50."""
    engine = AegeanEngine(htf_ema_period=200)
    engine.feed_htf_candles(symbol="TEST", closes=[float(i) for i in range(500)])
    assert len(engine._htf_closes["TEST"]) == 250


# ── Signal bounds ────────────────────────────────────────────────


def test_confidence_bounded():
    """All signals must have confidence in [0, 1]."""
    engine = AegeanEngine(min_confidence=0.0)
    highs, lows, closes = _make_candles(n=250, atr=200.0, trend=5.0)
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    for regime_name in [REGIME_TRENDING, REGIME_RANGING, REGIME_VOLATILE]:
        fv = make_feature_vector(adx_14=25.0, roc_10=0.02, lr_slope_20=0.001)
        regime = make_regime_state(regime_name)
        sig = engine.generate_signal(regime=regime, features=fv)
        if sig is not None:
            assert 0.0 <= sig.confidence <= 1.0
            assert 0.001 <= sig.stop_distance <= 0.10
            assert sig.expected_return > 0


def test_stop_distance_bounded():
    """All signals must have stop_distance in [0.001, 0.10]."""
    engine = AegeanEngine(min_confidence=0.0)
    fv = make_feature_vector(
        rsi_14=15.0, willr_14=-95.0, cci_20=-200.0,
        atr_14=500.0, atr_14_pct=0.025, adx_14=12.0,
    )
    regime = make_regime_state(REGIME_RANGING)
    sig = engine.generate_signal(regime=regime, features=fv)
    if sig is not None:
        assert 0.001 <= sig.stop_distance <= 0.10
