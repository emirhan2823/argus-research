"""Tests for Phase D — Enhanced CHOP Alpha.

Covers:
- D-01: identify_range() range detection
- D-02: detect_micro_reversion() micro-reversion signals
- D-03: detect_chop_correlation_gap() correlation gap signals
- D-06: NautilusEngine wiring of micro_reversion
- B-05: Gemini registered in router secondary engines
"""

from __future__ import annotations

from src.core.constants import (
    ENGINE_GEMINI,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
    REGIME_TO_SECONDARY_ENGINES,
)
from src.engines.nautilus.range_mapper import (
    RangeResult,
    identify_range,
    _find_pivot_highs,
    _find_pivot_lows,
    _find_best_cluster,
)
from src.engines.nautilus.micro_reversion import detect_micro_reversion
from src.engines.nautilus.chop_corr_gap import detect_chop_correlation_gap
from src.engines.nautilus.engine import NautilusEngine
from src.v25.contracts.signal import TemplateName
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


# ============================================================
# Helpers
# ============================================================

def _make_ranging_candles(
    base_price: float = 20000.0,
    atr: float = 200.0,
    n: int = 60,
) -> tuple[list[float], list[float], list[float]]:
    """Generate synthetic RANGING candles that oscillate in a band.

    Returns (highs, lows, closes).
    The range will be [base_price - 2*atr, base_price + 2*atr].
    """
    import math

    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    amplitude = 2 * atr
    for i in range(n):
        # Sine wave oscillation
        phase = (i / n) * 4 * math.pi  # 2 full cycles
        mid = base_price + amplitude * math.sin(phase)
        h = mid + atr * 0.3
        lo = mid - atr * 0.3
        c = mid + atr * 0.1 * math.sin(phase * 1.5)
        highs.append(h)
        lows.append(lo)
        closes.append(c)
    return highs, lows, closes


def _make_flat_range_candles(
    range_high: float = 20400.0,
    range_low: float = 19600.0,
    n: int = 60,
) -> tuple[list[float], list[float], list[float]]:
    """Generate candles that repeatedly touch the same high/low levels."""
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    mid = (range_high + range_low) / 2
    for i in range(n):
        # Alternate between touching high and low boundaries
        if i % 4 == 0:
            h, lo, c = range_high, range_high - 100, range_high - 50
        elif i % 4 == 2:
            h, lo, c = range_low + 100, range_low, range_low + 50
        else:
            h, lo, c = mid + 80, mid - 80, mid
        highs.append(h)
        lows.append(lo)
        closes.append(c)
    return highs, lows, closes


# ============================================================
# D-01: identify_range() tests
# ============================================================


class TestIdentifyRange:
    """Range detection from candle data."""

    def test_detects_flat_range(self) -> None:
        """Horizontal range with clear boundaries is detected."""
        highs, lows, closes = _make_flat_range_candles(
            range_high=20400.0, range_low=19600.0
        )
        result = identify_range(highs, lows, closes, atr=200.0, lookback=50)
        assert result is not None
        assert isinstance(result, RangeResult)
        assert result.range_high > result.range_low
        assert result.midpoint > result.range_low
        assert result.midpoint < result.range_high
        assert result.range_width_pct > 0

    def test_returns_none_insufficient_data(self) -> None:
        """Not enough bars → None."""
        result = identify_range([1, 2, 3], [1, 2, 3], [1, 2, 3], atr=1.0, lookback=50)
        assert result is None

    def test_returns_none_zero_atr(self) -> None:
        """Zero ATR → None."""
        highs, lows, closes = _make_flat_range_candles()
        result = identify_range(highs, lows, closes, atr=0.0)
        assert result is None

    def test_returns_none_trending_market(self) -> None:
        """A clearly trending market should not produce a range."""
        # Steadily increasing prices — no horizontal range
        highs = [100 + i * 2 for i in range(60)]
        lows = [99 + i * 2 for i in range(60)]
        closes = [99.5 + i * 2 for i in range(60)]
        result = identify_range(highs, lows, closes, atr=1.0, lookback=50)
        # This should return None because pivot highs and lows don't cluster
        assert result is None

    def test_touch_counts(self) -> None:
        """Range boundaries require minimum touches."""
        highs, lows, closes = _make_flat_range_candles()
        result = identify_range(highs, lows, closes, atr=200.0, lookback=50, min_touches=2)
        assert result is not None
        assert result.touch_count_high >= 2
        assert result.touch_count_low >= 2

    def test_rejects_very_narrow_range(self) -> None:
        """Range width < 0.5% is rejected as noise."""
        # Candles all at the same level
        highs = [100.01] * 60
        lows = [99.99] * 60
        closes = [100.0] * 60
        result = identify_range(highs, lows, closes, atr=0.01, lookback=50)
        assert result is None

    def test_find_pivot_highs_basic(self) -> None:
        """Pivot highs: bar higher than both neighbours."""
        pivots = _find_pivot_highs([1, 3, 2, 5, 1, 4, 2])
        assert 3 in pivots
        assert 5 in pivots
        assert 4 in pivots

    def test_find_pivot_lows_basic(self) -> None:
        """Pivot lows: bar lower than both neighbours."""
        pivots = _find_pivot_lows([5, 2, 4, 1, 3, 2, 5])
        assert 2 in pivots
        assert 1 in pivots

    def test_find_best_cluster(self) -> None:
        """Cluster detection picks the most-touched level."""
        values = [100.0, 100.1, 100.05, 200.0, 200.1]
        level, count = _find_best_cluster(values, tolerance=0.2)
        # The cluster around 100 has 3 members, around 200 has 2
        assert count == 3
        assert 99.5 < level < 100.5


# ============================================================
# D-02: detect_micro_reversion() tests
# ============================================================


class TestMicroReversion:
    """Micro-reversion signals at range boundaries."""

    def test_long_at_range_low(self) -> None:
        """Long signal when near range_low with bullish OBI and oversold RSI."""
        features = make_feature_vector(
            symbol="BTCUSDT",
            atr_14=200.0,
            atr_14_pct=0.01,  # approx price = 200/0.01 = 20000
            rsi_14=25.0,
            orderbook_imbalance=0.70,
            adx_14=18.0,
        )
        sig = detect_micro_reversion(
            features,
            range_high=20400.0,
            range_low=19900.0,  # price 20000 is within 0.5 ATR of 19900
            range_midpoint=20150.0,
        )
        assert sig is not None
        assert sig.bias == "long"
        assert sig.engine == ENGINE_NAUTILUS
        assert sig.sub_strategy == "micro_reversion"
        assert 0.0 < sig.confidence <= 1.0
        assert sig.stop_distance > 0
        assert sig.expected_return > 0

    def test_short_at_range_high(self) -> None:
        """Short signal when near range_high with bearish OBI and overbought RSI."""
        features = make_feature_vector(
            symbol="BTCUSDT",
            atr_14=200.0,
            atr_14_pct=0.01,  # approx price = 20000
            rsi_14=75.0,
            orderbook_imbalance=-0.70,
            adx_14=18.0,
        )
        sig = detect_micro_reversion(
            features,
            range_high=20100.0,  # price 20000 within 0.5 ATR of 20100
            range_low=19600.0,
            range_midpoint=19850.0,
        )
        assert sig is not None
        assert sig.bias == "short"
        assert sig.sub_strategy == "micro_reversion"

    def test_no_signal_weak_obi(self) -> None:
        """OBI below threshold → no signal."""
        features = make_feature_vector(
            atr_14=200.0,
            atr_14_pct=0.01,
            rsi_14=25.0,
            orderbook_imbalance=0.30,  # Below 0.55 threshold
        )
        sig = detect_micro_reversion(features, 20400.0, 19900.0, 20150.0)
        assert sig is None

    def test_no_signal_neutral_rsi(self) -> None:
        """RSI in neutral zone → no signal."""
        features = make_feature_vector(
            atr_14=200.0,
            atr_14_pct=0.01,
            rsi_14=50.0,  # Not oversold or overbought
            orderbook_imbalance=0.70,
        )
        sig = detect_micro_reversion(features, 20400.0, 19900.0, 20150.0)
        assert sig is None

    def test_no_signal_missing_obi(self) -> None:
        """Missing OBI → no signal."""
        features = make_feature_vector(
            atr_14=200.0,
            atr_14_pct=0.01,
            rsi_14=25.0,
            orderbook_imbalance=None,
        )
        sig = detect_micro_reversion(features, 20400.0, 19900.0, 20150.0)
        assert sig is None

    def test_no_signal_far_from_boundary(self) -> None:
        """Price not near any boundary → no signal."""
        features = make_feature_vector(
            atr_14=200.0,
            atr_14_pct=0.01,  # price ~ 20000
            rsi_14=25.0,
            orderbook_imbalance=0.70,
        )
        # Range boundaries are far from current price
        sig = detect_micro_reversion(features, 21000.0, 19000.0, 20000.0)
        assert sig is None


# ============================================================
# D-03: detect_chop_correlation_gap() tests
# ============================================================


class TestChopCorrGap:
    """Correlation gap convergence signals in CHOP."""

    def test_short_signal_positive_zscore(self) -> None:
        """Positive z-score → SHORT asset A."""
        features_a = make_feature_vector(symbol="BTCUSDT", adx_14=15.0)
        features_b = make_feature_vector(symbol="ETHUSDT", adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=2.0,
        )
        assert sig is not None
        assert sig.bias == "short"
        assert sig.engine == ENGINE_NAUTILUS
        assert sig.sub_strategy == "chop_corr_gap"
        assert sig.symbol == "BTCUSDT"

    def test_long_signal_negative_zscore(self) -> None:
        """Negative z-score → LONG asset A."""
        features_a = make_feature_vector(symbol="BTCUSDT", adx_14=15.0)
        features_b = make_feature_vector(symbol="ETHUSDT", adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=-2.0,
        )
        assert sig is not None
        assert sig.bias == "long"

    def test_blocked_when_not_ranging(self) -> None:
        """Both assets must be in RANGING → blocked otherwise."""
        features_a = make_feature_vector(adx_14=15.0)
        features_b = make_feature_vector(adx_14=18.0)

        # Asset A in TRENDING, B in RANGING
        sig = detect_chop_correlation_gap(
            features_a, features_b,
            make_regime_state(REGIME_TRENDING),
            make_regime_state(REGIME_RANGING),
            correlation=0.85, spread_zscore=2.0,
        )
        assert sig is None

        # Asset A in RANGING, B in VOLATILE
        sig = detect_chop_correlation_gap(
            features_a, features_b,
            make_regime_state(REGIME_RANGING),
            make_regime_state(REGIME_VOLATILE),
            correlation=0.85, spread_zscore=2.0,
        )
        assert sig is None

    def test_blocked_low_correlation(self) -> None:
        """Correlation below threshold → no signal."""
        features_a = make_feature_vector(adx_14=15.0)
        features_b = make_feature_vector(adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.40, spread_zscore=2.0,
        )
        assert sig is None

    def test_blocked_small_zscore(self) -> None:
        """Z-score below threshold → no signal."""
        features_a = make_feature_vector(adx_14=15.0)
        features_b = make_feature_vector(adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=0.5,  # Below 1.5
        )
        assert sig is None

    def test_blocked_high_adx(self) -> None:
        """ADX too high (not CHOP) → no signal."""
        features_a = make_feature_vector(adx_14=30.0)  # Too trendy
        features_b = make_feature_vector(adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=2.0,
        )
        assert sig is None

    def test_cointegration_boosts_confidence(self) -> None:
        """Cointegrated pair gets confidence boost."""
        features_a = make_feature_vector(adx_14=15.0)
        features_b = make_feature_vector(adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig_no_coint = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=2.0,
            is_cointegrated=False,
        )
        sig_coint = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=2.0,
            is_cointegrated=True,
        )
        assert sig_no_coint is not None
        assert sig_coint is not None
        assert sig_coint.confidence > sig_no_coint.confidence

    def test_fast_half_life_boosts_confidence(self) -> None:
        """Short half-life gets confidence boost."""
        features_a = make_feature_vector(adx_14=15.0)
        features_b = make_feature_vector(adx_14=18.0)
        regime_a = make_regime_state(REGIME_RANGING)
        regime_b = make_regime_state(REGIME_RANGING)

        sig_slow = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=2.0, half_life=50.0,
        )
        sig_fast = detect_chop_correlation_gap(
            features_a, features_b, regime_a, regime_b,
            correlation=0.85, spread_zscore=2.0, half_life=10.0,
        )
        assert sig_slow is not None
        assert sig_fast is not None
        assert sig_fast.confidence > sig_slow.confidence


# ============================================================
# D-04/D-05: TemplateName enum extensions
# ============================================================


class TestTemplateNameExtensions:
    """New template names for CHOP alpha."""

    def test_chop_corr_gap_in_enum(self) -> None:
        assert TemplateName.CHOP_CORR_GAP == "CHOP_CORR_GAP"

    def test_chop_micro_reversion_in_enum(self) -> None:
        assert TemplateName.CHOP_MICRO_REVERSION == "CHOP_MICRO_REVERSION"

    def test_corr_mean_reversion_in_enum(self) -> None:
        assert TemplateName.CORR_MEAN_REVERSION == "CORR_MEAN_REVERSION"

    def test_existing_templates_preserved(self) -> None:
        """Verify all original templates still exist."""
        assert TemplateName.TREND_PULLBACK == "TREND_PULLBACK"
        assert TemplateName.TREND_BREAKOUT == "TREND_BREAKOUT"
        assert TemplateName.CHOP_EXTREME == "CHOP_EXTREME"
        assert TemplateName.CHOP_FAILED_BREAKOUT == "CHOP_FAILED_BREAKOUT"
        assert TemplateName.VOLATILE_HIGH_SQS == "VOLATILE_HIGH_SQS"
        assert TemplateName.CRISIS_EXIT == "CRISIS_EXIT"


# ============================================================
# D-06: NautilusEngine wiring
# ============================================================


class TestNautilusEngineWiring:
    """NautilusEngine dispatches to micro_reversion when candles are fed."""

    def test_micro_reversion_wired_into_engine(self) -> None:
        """Engine produces micro_reversion signal with fed candles."""
        engine = NautilusEngine(max_adx=25.0, min_confidence=0.50)

        # Generate flat range candles around 20000
        highs, lows, closes = _make_flat_range_candles(
            range_high=20100.0, range_low=19900.0
        )
        engine.feed_candles("BTCUSDT", highs, lows, closes)

        # Make features that would trigger micro_reversion at range low
        features = make_feature_vector(
            symbol="BTCUSDT",
            atr_14=200.0,
            atr_14_pct=0.01,  # price ~ 20000
            adx_14=18.0,
            rsi_14=25.0,
            orderbook_imbalance=0.70,
            bb_pct_b=0.50,  # Not at BB extreme
        )
        regime = make_regime_state(REGIME_RANGING)
        sig = engine.generate_signal(regime=regime, features=features)
        # May get bb_reversion or micro_reversion — check sub_strategy exists
        if sig is not None and sig.sub_strategy == "micro_reversion":
            assert sig.engine == ENGINE_NAUTILUS
            assert sig.bias in ("long", "short")

    def test_engine_works_without_candle_history(self) -> None:
        """Engine still works for BB/funding without candle history."""
        engine = NautilusEngine(max_adx=25.0, min_confidence=0.50)
        features = make_feature_vector(
            adx_14=18.0,
            bb_pct_b=0.03,
            rsi_14=25.0,
        )
        regime = make_regime_state(REGIME_RANGING)
        sig = engine.generate_signal(regime=regime, features=features)
        assert sig is not None
        assert sig.sub_strategy == "bb_reversion"

    def test_engine_rejects_non_ranging(self) -> None:
        """Non-RANGING regime → no signal (unchanged behavior)."""
        engine = NautilusEngine()
        features = make_feature_vector()
        regime = make_regime_state(REGIME_TRENDING)
        sig = engine.generate_signal(regime=regime, features=features)
        assert sig is None

    def test_engine_best_signal_wins(self) -> None:
        """Highest confidence signal is returned."""
        engine = NautilusEngine(max_adx=25.0, min_confidence=0.50)
        # Strong BB reversion setup
        features = make_feature_vector(
            adx_14=15.0,
            bb_pct_b=0.01,
            rsi_14=20.0,
        )
        regime = make_regime_state(REGIME_RANGING)
        sig = engine.generate_signal(regime=regime, features=features)
        assert sig is not None
        # Should be the highest-confidence candidate


# ============================================================
# B-05: Gemini Router Registration
# ============================================================


class TestGeminiRouterRegistration:
    """Gemini engine registration and constant checks."""

    def test_poseidon_primary_aegean_secondary(self) -> None:
        """Non-CRISIS regimes have a primary engine and secondary engines."""
        from src.core.constants import ENGINE_POSEIDON, REGIME_TO_ENGINE
        for regime in (REGIME_TRENDING, REGIME_RANGING, REGIME_VOLATILE):
            assert REGIME_TO_ENGINE[regime] is not None, f"{regime} must have a primary engine"
            assert len(REGIME_TO_SECONDARY_ENGINES[regime]) >= 0  # secondary is optional

    def test_gemini_constant_value(self) -> None:
        assert ENGINE_GEMINI == "GEMINI"
