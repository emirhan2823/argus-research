import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.chiron.chiron import ChironRegimeEngine, MarketRegime, RegimeContext
from argus_py.models.chiron.indicators import calculate_chop_index


def _ctx(**kwargs):
    base = {
        "orion_score": 50.0,
        "aether_score": 50.0,
        "hermes_score": 50.0,
        "adx": 20.0,
        "chop_index": 50.0,
        "recent_volatility": 2.0,
    }
    base.update(kwargs)
    return RegimeContext(**base)


def test_detect_news_shock():
    e = ChironRegimeEngine()
    r = e.evaluate(_ctx(hermes_score=10.0))
    assert r.regime == MarketRegime.NEWS_SHOCK


def test_detect_risk_off():
    e = ChironRegimeEngine()
    r = e.evaluate(_ctx(aether_score=30.0, hermes_score=50.0))
    assert r.regime == MarketRegime.RISK_OFF


def test_detect_trend():
    e = ChironRegimeEngine()
    r = e.evaluate(_ctx(adx=30.0, chop_index=40.0, aether_score=60.0))
    assert r.regime == MarketRegime.TREND


def test_detect_chop():
    e = ChironRegimeEngine()
    r = e.evaluate(_ctx(adx=15.0, chop_index=65.0, orion_score=50.0))
    assert r.regime == MarketRegime.CHOP


def test_detect_neutral():
    e = ChironRegimeEngine()
    r = e.evaluate(_ctx(adx=22.0, chop_index=50.0, aether_score=50.0, hermes_score=50.0))
    assert r.regime == MarketRegime.NEUTRAL


def test_weight_table_matches_swift_example_for_risk_off():
    e = ChironRegimeEngine()
    core, pulse = e._get_base_weights(MarketRegime.RISK_OFF)
    assert core["aether"] == 0.40
    assert core["hermes"] == 0.30
    assert pulse["hermes"] == 0.50


def test_missing_module_adjustment_redistributes():
    e = ChironRegimeEngine()
    ctx = _ctx(orion_score=None, aether_score=60, hermes_score=60)
    adjusted = e._adjust_for_missing({"orion": 0.5, "aether": 0.25, "hermes": 0.25}, ctx)
    assert adjusted["orion"] == 0.0
    assert abs(sum(adjusted.values()) - 1.0) < 1e-9


def test_state_persistence(tmp_path):
    path = tmp_path / "chiron_state.json"
    e = ChironRegimeEngine(state_path=path)
    e.evaluate(_ctx(aether_score=30.0))  # RISK_OFF
    assert path.exists()

    e2 = ChironRegimeEngine(state_path=path)
    e2.load_state()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["last_regime"] == "RISK_OFF"


def test_choppiness_index_range_and_behavior():
    highs = [10 + (i % 2) * 2 for i in range(40)]
    lows = [8 - (i % 2) * 1 for i in range(40)]
    closes = [9 + ((-1) ** i) * 0.5 for i in range(40)]

    chop = calculate_chop_index(highs, lows, closes, period=14)
    assert 0.0 <= chop <= 100.0


def test_evaluate_returns_weights_normalized():
    e = ChironRegimeEngine()
    result = e.evaluate(_ctx(orion_score=None, aether_score=40, hermes_score=50))
    assert abs(sum(result.core_weights.values()) - 1.0) < 1e-9
    assert abs(sum(result.pulse_weights.values()) - 1.0) < 1e-9
    assert 0.0 <= result.confidence <= 1.0
