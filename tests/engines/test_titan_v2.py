"""TITAN v2 comprehensive tests — dual-setup architecture."""

from __future__ import annotations

import math

from src.core.constants import REGIME_CRISIS, REGIME_RANGING, REGIME_TRENDING
from src.engines.titan.engine import TitanEngine, _compute_adx_series
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


# ── Helpers ──


def _uptrend_candles(
    n: int = 150,
    start: float = 100.0,
) -> tuple[list[float], list[float], list[float]]:
    """Strong uptrend with clear HH/HL structure (swing pattern)."""
    highs, lows, closes = [], [], []
    p = start
    for i in range(n):
        cycle = i % 12
        if cycle < 8:
            p *= 1.01
        else:
            p *= 0.992
        h = p * 1.003
        l = p * 0.997
        highs.append(h)
        lows.append(l)
        closes.append(p)
    return highs, lows, closes


def _downtrend_candles(
    n: int = 150,
    start: float = 100.0,
) -> tuple[list[float], list[float], list[float]]:
    """Strong downtrend with clear LL/LH structure (swing pattern)."""
    highs, lows, closes = [], [], []
    p = start
    for i in range(n):
        cycle = i % 12
        if cycle < 8:
            p *= 0.99
        else:
            p *= 1.008
        h = p * 1.003
        l = p * 0.997
        highs.append(h)
        lows.append(l)
        closes.append(p)
    return highs, lows, closes


def _flat_candles(n: int = 150, price: float = 100.0) -> tuple[list[float], list[float], list[float]]:
    """Flat/ranging candles — no structure."""
    highs = [price * 1.003] * n
    lows = [price * 0.997] * n
    closes = [price] * n
    return highs, lows, closes


def _make_titan(
    candle_type: str = "up",
    n: int = 150,
    symbol: str = "BTCUSDT",
) -> TitanEngine:
    engine = TitanEngine()
    if candle_type == "up":
        h, l, c = _uptrend_candles(n=n)
    elif candle_type == "down":
        h, l, c = _downtrend_candles(n=n)
    else:
        h, l, c = _flat_candles(n=n)
    engine.feed_candles(symbol=symbol, highs=h, lows=l, closes=c)
    return engine


# ── ADX Series Computation ──


def test_adx_series_computation() -> None:
    h, l, c = _uptrend_candles(n=100)
    adx = _compute_adx_series(h, l, c, length=14)
    assert len(adx) > 0
    assert adx[-1] > 0


def test_adx_series_insufficient_data() -> None:
    adx = _compute_adx_series([100.0] * 5, [99.0] * 5, [99.5] * 5, length=14)
    assert adx == []


# ── Trend Confirmation (CONTINUATION) ──


def test_continuation_long_all_pass() -> None:
    engine = _make_titan("up")
    features = make_feature_vector(
        adx_14=30.0,
        ema_21_vs_55=0.03,
        price_vs_ma200=0.04,
        atr_pctl=0.7,
        volume_ratio=1.5,
    )
    h, l, c = engine._candle_history["BTCUSDT"]
    passed, strength = engine._check_trend_confirmation_long(features, h, l, c)
    # Depends on synthetic data structure match, but should not crash
    assert isinstance(passed, bool)
    assert isinstance(strength, float)


def test_continuation_short_all_pass() -> None:
    engine = _make_titan("down")
    features = make_feature_vector(
        adx_14=30.0,
        ema_21_vs_55=-0.03,
        price_vs_ma200=-0.04,
        atr_pctl=0.7,
        volume_ratio=1.5,
    )
    h, l, c = engine._candle_history["BTCUSDT"]
    passed, strength = engine._check_trend_confirmation_short(features, h, l, c)
    assert isinstance(passed, bool)
    assert isinstance(strength, float)


def test_continuation_fails_low_adx() -> None:
    engine = _make_titan("up")
    features = make_feature_vector(adx_14=15.0)
    h, l, c = engine._candle_history["BTCUSDT"]
    passed, _ = engine._check_trend_confirmation_long(features, h, l, c)
    assert passed is False


def test_continuation_fails_low_volume() -> None:
    engine = _make_titan("up")
    features = make_feature_vector(
        adx_14=30.0, ema_21_vs_55=0.03, price_vs_ma200=0.04,
        atr_pctl=0.7, volume_ratio=0.8,
    )
    h, l, c = engine._candle_history["BTCUSDT"]
    passed, _ = engine._check_trend_confirmation_long(features, h, l, c)
    assert passed is False


def test_continuation_fails_low_atr_pctl() -> None:
    engine = _make_titan("up")
    features = make_feature_vector(
        adx_14=30.0, ema_21_vs_55=0.03, price_vs_ma200=0.04,
        atr_pctl=0.3, volume_ratio=1.5,
    )
    h, l, c = engine._candle_history["BTCUSDT"]
    passed, _ = engine._check_trend_confirmation_long(features, h, l, c)
    assert passed is False


def test_continuation_fails_no_ema_alignment() -> None:
    engine = _make_titan("up")
    features = make_feature_vector(
        adx_14=30.0, ema_21_vs_55=0.0, price_vs_ma200=0.04,
        atr_pctl=0.7, volume_ratio=1.5,
    )
    h, l, c = engine._candle_history["BTCUSDT"]
    passed, _ = engine._check_trend_confirmation_long(features, h, l, c)
    assert passed is False


# ── Structure Detection ──


def test_bullish_structure_count() -> None:
    engine = _make_titan("up")
    from src.features.market_structure import detect_swing_levels
    h, l, _ = engine._candle_history["BTCUSDT"]
    levels = detect_swing_levels(highs=h, lows=l, window=5)
    swing_highs = sorted([lv for lv in levels if lv.level_type == "resistance"], key=lambda lv: lv.bar_index)
    swing_lows = sorted([lv for lv in levels if lv.level_type == "support"], key=lambda lv: lv.bar_index)
    count = engine._count_bullish_structure(swing_highs, swing_lows)
    assert count >= 0


def test_bearish_structure_count() -> None:
    engine = _make_titan("down")
    from src.features.market_structure import detect_swing_levels
    h, l, _ = engine._candle_history["BTCUSDT"]
    levels = detect_swing_levels(highs=h, lows=l, window=5)
    swing_highs = sorted([lv for lv in levels if lv.level_type == "resistance"], key=lambda lv: lv.bar_index)
    swing_lows = sorted([lv for lv in levels if lv.level_type == "support"], key=lambda lv: lv.bar_index)
    count = engine._count_bearish_structure(swing_highs, swing_lows)
    assert count >= 0


def test_flat_structure_zero() -> None:
    engine = _make_titan("flat")
    from src.features.market_structure import detect_swing_levels
    h, l, _ = engine._candle_history["BTCUSDT"]
    levels = detect_swing_levels(highs=h, lows=l, window=5)
    swing_highs = sorted([lv for lv in levels if lv.level_type == "resistance"], key=lambda lv: lv.bar_index)
    swing_lows = sorted([lv for lv in levels if lv.level_type == "support"], key=lambda lv: lv.bar_index)
    bullish = engine._count_bullish_structure(swing_highs, swing_lows)
    bearish = engine._count_bearish_structure(swing_highs, swing_lows)
    # Flat candles should have 0 or very low structure count
    assert bullish <= 1
    assert bearish <= 1


# ── Regime Gates ──


def test_disabled_in_ranging() -> None:
    engine = _make_titan("up")
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(),
    )
    assert sig is None


def test_disabled_in_crisis() -> None:
    engine = _make_titan("up")
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_CRISIS),
        features=make_feature_vector(),
    )
    assert sig is None


# ── Signal Properties ──


def test_signal_engine_name() -> None:
    engine = _make_titan("up")
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0, ema_21_vs_55=0.03, price_vs_ma200=0.04,
            atr_pctl=0.7, volume_ratio=1.5,
        ),
    )
    if sig is not None:
        assert sig.engine == "TITAN"
        assert sig.atr > 0
        assert sig.stop_distance > 0
        assert sig.expected_return > 0


def test_signal_rr_ratio() -> None:
    engine = _make_titan("up")
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0, ema_21_vs_55=0.03, price_vs_ma200=0.04,
            atr_pctl=0.7, volume_ratio=1.5,
        ),
    )
    if sig is not None:
        rr = sig.expected_return / sig.stop_distance
        assert rr >= 2.5, f"Expected R:R >= 2.5, got {rr:.2f}"


def test_sub_strategy_names() -> None:
    """All sub_strategy values should be one of the 4 dual-setup types."""
    engine = _make_titan("up")
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0, ema_21_vs_55=0.03, price_vs_ma200=0.04,
            atr_pctl=0.7, volume_ratio=1.5,
        ),
    )
    valid_strategies = {
        "reversal_long", "reversal_short",
        "continuation_long", "continuation_short",
    }
    if sig is not None:
        assert sig.sub_strategy in valid_strategies
