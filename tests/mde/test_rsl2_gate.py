"""Tests for RSL2 defensive gate: only TITAN allowed at risk-switch level 2."""

from __future__ import annotations

import pytest

from tests.unit._v2_helpers import make_feature_vector, make_regime_state
from src.core.types import EngineSignal
from src.mde.gates import GateInput, evaluate_gates


def _make_signal(engine: str = "AEGEAN", **kwargs) -> EngineSignal:
    defaults = dict(
        engine=engine,
        sub_strategy="test",
        asset_class="crypto",
        symbol="BTCUSDT",
        bias="long",
        confidence=0.70,
        expected_return=0.03,
        stop_distance=0.015,
        atr=200.0,
    )
    defaults.update(kwargs)
    return EngineSignal(**defaults)


def _make_gate_input(rsl_level: int, engine: str) -> GateInput:
    return GateInput(
        sentinel_score=0.8,
        regime=make_regime_state("RANGING"),
        rsl_level=rsl_level,
        signal=_make_signal(engine=engine),
        features=make_feature_vector(),
    )


class TestRSL2DefensiveGate:
    """RSL2 policy: only TITAN allowed; all others blocked."""

    # ── RSL2: TITAN allowed ──

    def test_titan_allowed_at_rsl2(self):
        result = evaluate_gates(_make_gate_input(rsl_level=2, engine="TITAN"))
        assert result.approved is True
        assert result.gate_number == 8

    # ── RSL2: AEGEAN blocked ──

    def test_aegean_blocked_at_rsl2(self):
        result = evaluate_gates(_make_gate_input(rsl_level=2, engine="AEGEAN"))
        assert result.approved is False
        assert result.gate_number == 3
        assert "rsl2_defensive_only_titan" in result.reason

    # ── RSL2: other engines blocked ──

    @pytest.mark.parametrize("engine", ["POSEIDON", "NAUTILUS", "HYDRA", "HERMES", "GEMINI"])
    def test_other_engines_blocked_at_rsl2(self, engine: str):
        result = evaluate_gates(_make_gate_input(rsl_level=2, engine=engine))
        assert result.approved is False
        assert result.gate_number == 3
        assert "rsl2_defensive_only_titan" in result.reason

    # ── RSL3: everything blocked (unchanged) ──

    @pytest.mark.parametrize("engine", ["TITAN", "AEGEAN", "POSEIDON"])
    def test_all_blocked_at_rsl3(self, engine: str):
        result = evaluate_gates(_make_gate_input(rsl_level=3, engine=engine))
        assert result.approved is False
        assert result.gate_number == 3
        assert "rsl_halt" in result.reason

    # ── RSL0/RSL1: all active engines pass (unchanged behavior) ──

    @pytest.mark.parametrize("engine", ["TITAN", "AEGEAN"])
    def test_active_engines_pass_at_rsl0(self, engine: str):
        result = evaluate_gates(_make_gate_input(rsl_level=0, engine=engine))
        assert result.approved is True

    @pytest.mark.parametrize("engine", ["TITAN", "AEGEAN"])
    def test_active_engines_pass_at_rsl1(self, engine: str):
        result = evaluate_gates(_make_gate_input(rsl_level=1, engine=engine))
        assert result.approved is True

    # ── No accidental unblock of PHOENIX ──

    def test_phoenix_blocked_at_rsl2(self):
        result = evaluate_gates(_make_gate_input(rsl_level=2, engine="PHOENIX"))
        assert result.approved is False
        assert result.gate_number == 3
