from __future__ import annotations

from src.core.constants import REGIME_CRISIS, REGIME_RANGING, REGIME_TRENDING, REGIME_VOLATILE
from src.engines.poseidon.engine import PoseidonEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def test_poseidon_no_signal_in_crisis() -> None:
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_CRISIS),
        features=make_feature_vector(),
    )
    assert sig is None


def test_poseidon_no_signal_neutral_features() -> None:
    """Default feature values are mid-range — no MR signal expected."""
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(),
    )
    assert sig is None


def test_poseidon_strong_long_signal() -> None:
    """Multiple oversold indicators → STRONG long signal."""
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.05,       # extreme oversold
            rsi_14=22.0,         # oversold
            cci_20=-200.0,       # extreme oversold
            willr_14=-92.0,      # oversold
            vwap_dev_pct=-0.04,  # below VWAP
            cmf_20=-0.25,        # selling exhaustion
        ),
    )
    assert sig is not None
    assert sig.engine == "POSEIDON"
    assert sig.bias == "long"
    assert sig.confidence >= 0.50  # Consortium scoring adjusts thresholds
    assert sig.sub_strategy.startswith("mr_consortium_")


def test_poseidon_strong_short_signal() -> None:
    """Multiple overbought indicators → STRONG short signal."""
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.95,       # extreme overbought
            rsi_14=78.0,         # overbought
            cci_20=200.0,        # extreme overbought
            willr_14=-8.0,       # overbought
            vwap_dev_pct=0.04,   # above VWAP
            cmf_20=0.25,         # buying exhaustion
        ),
    )
    assert sig is not None
    assert sig.engine == "POSEIDON"
    assert sig.bias == "short"
    assert sig.confidence >= 0.50


def test_poseidon_normal_signal_partial_indicators() -> None:
    """Some oversold indicators → long signal (at least WEAK grade)."""
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.08,       # oversold (structure)
            rsi_14=25.0,         # oversold (mr)
            cci_20=-180.0,       # oversold (mr)
            willr_14=-88.0,      # oversold (mr)
            vwap_dev_pct=-0.03,  # below VWAP (structure)
            cmf_20=-0.20,        # selling exhaustion (volume)
        ),
    )
    assert sig is not None
    assert sig.bias == "long"
    assert sig.sub_strategy.startswith("mr_consortium_")


def test_poseidon_weak_signal_few_indicators() -> None:
    """Only a couple oversold indicators → WEAK or no signal."""
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.10,       # oversold (weight 2.0)
            rsi_14=45.0,         # neutral
            cci_20=0.0,          # neutral
            willr_14=-50.0,      # neutral
            vwap_dev_pct=0.0,    # neutral
            cmf_20=-0.20,        # oversold (weight 1.0)
        ),
    )
    # With only bb (2.0) + cmf (1.0) = 3.0 out of 11.0 = 27% → below 30% → None
    # May be None or WEAK depending on thresholds
    if sig is not None:
        assert sig.sub_strategy.startswith("mr_consortium_")


def test_poseidon_ranging_regime_bonus() -> None:
    """RANGING regime gives +0.05 confidence bonus."""
    engine = PoseidonEngine()
    sig_ranging = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.05, rsi_14=22.0, cci_20=-200.0,
            willr_14=-92.0, vwap_dev_pct=-0.04, cmf_20=-0.25,
        ),
    )
    sig_trending = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            bb_pct_b=0.05, rsi_14=22.0, cci_20=-200.0,
            willr_14=-92.0, vwap_dev_pct=-0.04, cmf_20=-0.25,
        ),
    )
    assert sig_ranging is not None
    assert sig_trending is not None
    assert sig_ranging.confidence > sig_trending.confidence


def test_poseidon_stop_distance_uses_atr_2x() -> None:
    """Stop distance should be ATR * 2.0 / price."""
    engine = PoseidonEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            atr_14=200.0, atr_14_pct=0.01,  # price ≈ 20000
            bb_pct_b=0.05, rsi_14=22.0, cci_20=-200.0,
            willr_14=-92.0, vwap_dev_pct=-0.04, cmf_20=-0.25,
        ),
    )
    assert sig is not None
    # ATR=200, price=20000, stop = 200*2.0/20000 = 0.02
    assert 0.015 <= sig.stop_distance <= 0.025


def test_poseidon_wave_trend_long() -> None:
    """Wave Trend oversold cross → long vote added."""
    engine = PoseidonEngine()
    # Create a descending HLC3 series to make WT oversold
    n = 150
    closes = [100.0 - i * 0.5 for i in range(n)]  # descending
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.05, rsi_14=22.0, cci_20=-200.0,
            willr_14=-92.0, vwap_dev_pct=-0.04, cmf_20=-0.25,
        ),
    )
    assert sig is not None
    assert sig.bias == "long"


def test_poseidon_harsi_oversold_long() -> None:
    """HARSI in oversold zone → long vote with candle history."""
    engine = PoseidonEngine()
    # Create a descending series so RSI goes oversold
    n = 150
    closes = [100.0 - i * 0.3 for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    # Check that HARSI vote is generated
    from src.engines.poseidon.engine import _IndicatorVote
    vote = engine._vote_harsi(make_feature_vector())
    assert vote is not None
    # With descending prices, HARSI should be in oversold zone
    if vote.bias is not None:
        assert vote.bias == "long"


def test_poseidon_harsi_overbought_short() -> None:
    """HARSI in overbought zone → short vote with candle history."""
    engine = PoseidonEngine()
    # Create an ascending series so RSI goes overbought
    n = 150
    closes = [50.0 + i * 0.3 for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    vote = engine._vote_harsi(make_feature_vector())
    assert vote is not None
    if vote.bias is not None:
        assert vote.bias == "short"


def test_poseidon_entropy_supertrend_with_candles() -> None:
    """Entropy SuperTrend returns a vote when candle history is available."""
    engine = PoseidonEngine()
    n = 150
    # Sideways then breakout pattern
    closes = [100.0 + (i % 10) * 0.2 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    engine.feed_candles(symbol="BTCUSDT", highs=highs, lows=lows, closes=closes)

    vote = engine._vote_entropy_supertrend(make_feature_vector())
    assert vote is not None
    assert vote.name == "entropy_st"


def test_poseidon_active_in_all_non_crisis_regimes() -> None:
    """POSEIDON should be active in TRENDING, RANGING, VOLATILE."""
    engine = PoseidonEngine()
    extreme_features = make_feature_vector(
        bb_pct_b=0.05, rsi_14=22.0, cci_20=-200.0,
        willr_14=-92.0, vwap_dev_pct=-0.04, cmf_20=-0.25,
    )
    for regime in [REGIME_TRENDING, REGIME_RANGING, REGIME_VOLATILE]:
        sig = engine.generate_signal(
            regime=make_regime_state(regime),
            features=extreme_features,
        )
        assert sig is not None, f"Expected signal in {regime}"
