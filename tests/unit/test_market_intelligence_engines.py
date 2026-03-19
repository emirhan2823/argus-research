from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.aether.aether_c import AetherCEngine, AetherCInputs, MacroRegimeC
from argus_py.models.atlas.atlas_c import AtlasCEngine, AtlasCInputs



def test_atlas_c_outputs_bounded_score() -> None:
    engine = AtlasCEngine()
    result = engine.evaluate(
        AtlasCInputs(
            nvt_ratio=45.0,
            mvrv_ratio=1.2,
            exchange_reserve_change_7d=-1.8,
            active_address_change_7d=3.2,
            funding_rate=0.0002,
        )
    )
    assert 0.0 <= result.score <= 100.0
    assert result.regime_bias in {"RISK_ON", "NEUTRAL", "RISK_OFF"}



def test_aether_c_outputs_macro_regime() -> None:
    engine = AetherCEngine()
    result = engine.evaluate(
        AetherCInputs(
            fear_greed=58.0,
            btc_dominance=46.0,
            total_market_cap_change_24h=2.4,
            dxy_trend="DOWN",
        )
    )
    assert 0.0 <= result.score <= 100.0
    assert result.regime in {MacroRegimeC.RISK_ON, MacroRegimeC.NEUTRAL, MacroRegimeC.RISK_OFF}
