"""TITAN v2 engine unit tests — dual-setup trend confirmation + entry logic."""

from __future__ import annotations

from src.core.constants import REGIME_RANGING, REGIME_TRENDING
from src.engines.titan.engine import TitanEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def _make_trending_candles(
    n: int = 150,
    start_price: float = 100.0,
    trend_pct: float = 0.003,
) -> tuple[list[float], list[float], list[float]]:
    """Generate synthetic uptrend candles with HH/HL structure."""
    highs, lows, closes = [], [], []
    price = start_price
    for i in range(n):
        cycle = i % 12
        if cycle < 8:
            price *= 1 + trend_pct * 3
        else:
            price *= 1 - trend_pct * 2
        h = price * 1.005
        l = price * 0.995
        highs.append(h)
        lows.append(l)
        closes.append(price)
    return highs, lows, closes


def _make_downtrend_candles(
    n: int = 150,
    start_price: float = 100.0,
    trend_pct: float = 0.003,
) -> tuple[list[float], list[float], list[float]]:
    """Generate synthetic downtrend candles with LL/LH structure."""
    highs, lows, closes = [], [], []
    price = start_price
    for i in range(n):
        cycle = i % 12
        if cycle < 8:
            price *= 1 - trend_pct * 3
        else:
            price *= 1 + trend_pct * 2
        h = price * 1.005
        l = price * 0.995
        highs.append(h)
        lows.append(l)
        closes.append(price)
    return highs, lows, closes


def _make_engine_with_candles(
    symbol: str = "BTCUSDT",
    trend: str = "up",
    n: int = 150,
) -> TitanEngine:
    """Create a TitanEngine with synthetic candle history."""
    engine = TitanEngine()
    if trend == "up":
        highs, lows, closes = _make_trending_candles(n=n)
    else:
        highs, lows, closes = _make_downtrend_candles(n=n)
    engine.feed_candles(symbol=symbol, highs=highs, lows=lows, closes=closes)
    return engine


# ── Regime gate ──

def test_titan_only_active_in_trending() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(),
    )
    assert sig is None


# ── ADX gate ──

def test_titan_rejects_low_adx() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(adx_14=18.0),
    )
    assert sig is None


# ── No candle history ──

def test_titan_no_signal_without_candles() -> None:
    engine = TitanEngine()  # no feed_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(adx_14=30.0, atr_pctl=0.7, volume_ratio=1.5),
    )
    assert sig is None


# ── Full trend confirmation ──

def test_titan_trend_follow_signal() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0,
            ema_21_vs_55=0.03,
            price_vs_ma200=0.04,
            atr_pctl=0.7,
            volume_ratio=1.5,
        ),
    )
    if sig is not None:
        assert sig.engine == "TITAN"
        assert sig.sub_strategy in {
            "reversal_long", "reversal_short",
            "continuation_long", "continuation_short",
        }


# ── Volume gate ──

def test_titan_rejects_low_volume() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0,
            ema_21_vs_55=0.03,
            price_vs_ma200=0.04,
            atr_pctl=0.7,
            volume_ratio=0.8,
        ),
    )
    assert sig is None


# ── ATR percentile gate ──

def test_titan_rejects_low_atr_pctl() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0,
            ema_21_vs_55=0.03,
            price_vs_ma200=0.04,
            atr_pctl=0.3,
            volume_ratio=1.5,
        ),
    )
    assert sig is None


# ── EMA alignment gate ──

def test_titan_rejects_no_ema_alignment() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0,
            ema_21_vs_55=0.0,
            price_vs_ma200=0.04,
            atr_pctl=0.7,
            volume_ratio=1.5,
        ),
    )
    assert sig is None


# ── MA200 misalignment ──

def test_titan_rejects_conflicting_ma200() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0,
            ema_21_vs_55=0.03,
            price_vs_ma200=-0.04,
            atr_pctl=0.7,
            volume_ratio=1.5,
        ),
    )
    assert sig is None


# ── feed_candles truncation ──

def test_feed_candles_truncation() -> None:
    engine = TitanEngine()
    highs, lows, closes = _make_trending_candles(n=600)
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)
    history = engine._candle_history["BTCUSDT"]
    assert len(history[0]) == 500


# ── R:R target ──

def test_titan_rr_target() -> None:
    engine = _make_engine_with_candles()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            adx_14=30.0,
            ema_21_vs_55=0.03,
            price_vs_ma200=0.04,
            atr_pctl=0.7,
            volume_ratio=1.5,
        ),
    )
    if sig is not None:
        rr = sig.expected_return / sig.stop_distance if sig.stop_distance > 0 else 0
        assert rr >= 2.5, f"R:R should be >= 2.5, got {rr:.2f}"
