from __future__ import annotations

from src.core.constants import REGIME_CRISIS, REGIME_VOLATILE
from src.engines.phoenix.engine import PhoenixEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def test_phoenix_inactive_in_crisis() -> None:
    engine = PhoenixEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_CRISIS),
        features=make_feature_vector(funding_pctile_30d=99.0),
    )
    assert sig is None


def test_phoenix_funding_harvest_signal() -> None:
    engine = PhoenixEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_VOLATILE),
        features=make_feature_vector(funding_pctile_30d=97.0, basis_pct=0.001),
    )
    assert sig is not None
    assert sig.sub_strategy == "funding_harvest"
    assert sig.engine == "PHOENIX"


def test_phoenix_basis_trade_signal() -> None:
    engine = PhoenixEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_VOLATILE),
        features=make_feature_vector(funding_pctile_30d=50.0, basis_pct=0.004),
    )
    assert sig is not None
    assert sig.sub_strategy == "basis_trade"


def test_phoenix_non_crypto_carry_proxy() -> None:
    engine = PhoenixEngine()
    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_VOLATILE),
        features=make_feature_vector(
            asset_class="us_equity",
            symbol="AAPL",
            funding_pctile_30d=None,
            basis_pct=None,
            volume_delta=0.6,
            spread_pct=0.001,
        ),
    )
    assert sig is not None
    assert sig.sub_strategy == "carry_proxy"
