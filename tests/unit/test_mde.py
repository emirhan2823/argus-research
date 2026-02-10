from __future__ import annotations

from src.core.constants import ENGINE_HERMES, ENGINE_NAUTILUS, ENGINE_PHOENIX, ENGINE_TITAN, REGIME_RANGING, REGIME_TRENDING
from src.core.types import EngineSignal
from src.mde.execution_router import get_execution_mode
from src.mde.gates import GateInput, evaluate_gates
from src.mde.router import RegimeRouter
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


class _DummyEngine:
    def __init__(self, signal: EngineSignal | None) -> None:
        self.signal = signal

    def generate_signal(self, *, regime, features):
        return self.signal


def _sig(engine: str, bias: str = "long", confidence: float = 0.7, expected_return: float = 0.02) -> EngineSignal:
    fv = make_feature_vector()
    return EngineSignal(
        engine=engine,
        sub_strategy="test",
        asset_class=fv.asset_class,
        symbol=fv.symbol,
        bias=bias,
        confidence=confidence,
        stop_distance=0.01,
        expected_return=expected_return,
        atr=fv.atr_14,
    )


def test_router_lead_engine_signal() -> None:
    router = RegimeRouter(
        engines={
            ENGINE_TITAN: _DummyEngine(_sig(ENGINE_TITAN)),
            ENGINE_PHOENIX: _DummyEngine(_sig(ENGINE_PHOENIX)),
            ENGINE_HERMES: _DummyEngine(None),
        }
    )
    signal = router.route(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(),
    )
    assert signal is not None
    assert signal.engine == ENGINE_TITAN


def test_router_fallback_to_phoenix() -> None:
    router = RegimeRouter(
        engines={
            ENGINE_NAUTILUS: _DummyEngine(None),
            ENGINE_PHOENIX: _DummyEngine(_sig(ENGINE_PHOENIX)),
            ENGINE_HERMES: _DummyEngine(None),
        }
    )
    signal = router.route(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(),
    )
    assert signal is not None
    assert signal.engine == ENGINE_PHOENIX


def test_router_hermes_override_on_opposite_stronger_signal() -> None:
    router = RegimeRouter(
        engines={
            ENGINE_TITAN: _DummyEngine(_sig(ENGINE_TITAN, bias="long", confidence=0.60)),
            ENGINE_PHOENIX: _DummyEngine(None),
            ENGINE_HERMES: _DummyEngine(_sig(ENGINE_HERMES, bias="short", confidence=0.85)),
        }
    )
    signal = router.route(
        regime=make_regime_state(REGIME_TRENDING),
        features=make_feature_vector(),
    )
    assert signal is not None
    assert signal.engine == ENGINE_HERMES
    assert signal.bias == "short"


def test_gates_reject_on_sentinel() -> None:
    result = evaluate_gates(
        GateInput(
            sentinel_score=0.2,
            regime=make_regime_state(REGIME_TRENDING),
            rsl_level=0,
            signal=_sig(ENGINE_TITAN),
            features=make_feature_vector(),
        )
    )
    assert result.approved is False
    assert result.gate_number == 0


def test_gates_allow_only_phoenix_on_defensive() -> None:
    denied = evaluate_gates(
        GateInput(
            sentinel_score=0.9,
            regime=make_regime_state(REGIME_TRENDING),
            rsl_level=2,
            signal=_sig(ENGINE_TITAN),
            features=make_feature_vector(),
        )
    )
    allowed = evaluate_gates(
        GateInput(
            sentinel_score=0.9,
            regime=make_regime_state(REGIME_TRENDING),
            rsl_level=2,
            signal=_sig(ENGINE_PHOENIX),
            features=make_feature_vector(),
        )
    )
    assert denied.approved is False
    assert denied.gate_number == 3
    assert allowed.approved is True


def test_gates_pass_happy_path() -> None:
    result = evaluate_gates(
        GateInput(
            sentinel_score=0.95,
            regime=make_regime_state(REGIME_TRENDING),
            rsl_level=0,
            signal=_sig(ENGINE_TITAN, confidence=0.8, expected_return=0.03),
            features=make_feature_vector(),
        )
    )
    assert result.approved is True
    assert result.action == "proceed"


def test_execution_mode_router() -> None:
    cfg = {
        "asset_classes": {
            "crypto": {"execution_mode": "auto"},
            "bist": {"execution_mode": "advisory"},
        }
    }
    assert get_execution_mode("crypto", cfg) == "auto"
    assert get_execution_mode("bist", cfg) == "advisory"
    assert get_execution_mode("unknown", cfg) == "advisory"
