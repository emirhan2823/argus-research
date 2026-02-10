from __future__ import annotations

from src.core.constants import REGIME_RANGING, REGIME_TRENDING
from src.engines.nautilus.engine import NautilusEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def test_nautilus_only_active_in_ranging() -> None:
    engine = NautilusEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(adx_14=15.0),
    )
    assert sig is None


def test_nautilus_bb_reversion_long_signal() -> None:
    engine = NautilusEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(bb_pct_b=0.02, rsi_14=25.0, adx_14=14.0),
    )
    assert sig is not None
    assert sig.sub_strategy == "bb_reversion"
    assert sig.bias == "long"


def test_nautilus_funding_reversion_signal_for_crypto() -> None:
    engine = NautilusEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            bb_pct_b=0.50,
            rsi_14=50.0,
            funding_pctile_30d=96.0,
            adx_14=15.0,
        ),
    )
    assert sig is not None
    assert sig.sub_strategy == "funding_reversion"
    assert sig.bias == "short"


def test_nautilus_no_funding_reversion_for_non_crypto() -> None:
    engine = NautilusEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(
            asset_class="us_equity",
            symbol="AAPL",
            funding_pctile_30d=99.0,
            bb_pct_b=0.50,
            rsi_14=50.0,
            adx_14=15.0,
        ),
    )
    assert sig is None
