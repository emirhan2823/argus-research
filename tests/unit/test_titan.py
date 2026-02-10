from __future__ import annotations

from src.core.constants import REGIME_RANGING, REGIME_TRENDING
from src.engines.titan.engine import TitanEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def test_titan_only_active_in_trending() -> None:
    engine = TitanEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(),
    )
    assert sig is None


def test_titan_trend_follow_signal() -> None:
    engine = TitanEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(adx_14=32.0, ema_21_vs_55=0.03, price_vs_ma200=0.04),
    )
    assert sig is not None
    assert sig.engine == "TITAN"
    assert sig.sub_strategy in {"trend_follow", "breakout"}


def test_titan_rejects_low_adx() -> None:
    engine = TitanEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(adx_14=18.0),
    )
    assert sig is None


def test_titan_breakout_preferred_when_volume_spike() -> None:
    engine = TitanEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(
            bb_pct_b=0.99,
            volume_ratio=2.0,
            ema_21_vs_55=0.0,
            price_vs_ma200=0.0,
            adx_14=28.0,
        ),
    )
    assert sig is not None
    assert sig.sub_strategy == "breakout"
