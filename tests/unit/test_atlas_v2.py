from __future__ import annotations

from src.core.constants import REGIME_CRISIS, REGIME_RANGING
from src.engines.atlas.risk_overlay import AtlasRiskOverlay


def test_atlas_crisis_multiplier_zero() -> None:
    overlay = AtlasRiskOverlay()
    mult = overlay.compute_multiplier(
        regime=REGIME_CRISIS,
        asset_class="crypto",
        btc_dominance_delta_24h=0.5,
        total_mcap_momentum=0.1,
        stablecoin_flow=2_000_000.0,
    )
    assert mult == 0.0


def test_atlas_crypto_risk_on_and_risk_off() -> None:
    overlay = AtlasRiskOverlay()
    risk_on = overlay.compute_multiplier(
        regime=REGIME_RANGING,
        asset_class="crypto",
        btc_dominance_delta_24h=-0.4,
        total_mcap_momentum=0.08,
        stablecoin_flow=3_000_000.0,
    )
    risk_off = overlay.compute_multiplier(
        regime=REGIME_RANGING,
        asset_class="crypto",
        btc_dominance_delta_24h=0.6,
        total_mcap_momentum=-0.08,
        stablecoin_flow=-2_000_000.0,
    )
    assert risk_on > 1.0
    assert risk_off < 0.7


def test_atlas_macro_path_for_non_crypto() -> None:
    overlay = AtlasRiskOverlay()
    calm = overlay.compute_multiplier(
        regime=REGIME_RANGING,
        asset_class="us_equity",
        vix_level=15.0,
        yield_curve_slope=0.3,
    )
    stress = overlay.compute_multiplier(
        regime=REGIME_RANGING,
        asset_class="us_equity",
        vix_level=35.0,
        yield_curve_slope=-0.4,
    )
    assert calm > 1.0
    assert stress < 0.7
