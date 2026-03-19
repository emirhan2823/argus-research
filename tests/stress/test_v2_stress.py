from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_HERMES,
    ENGINE_NAUTILUS,
    ENGINE_PHOENIX,
    ENGINE_TITAN,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)
from src.core.types import Decision, EngineSignal
from src.execution.executor import Executor
from src.mde.gates import GateInput, evaluate_gates
from src.mde.router import RegimeRouter
from src.risk.pre_trade import PreTradeChecker, PreTradeInput
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


class _Engine:
    def __init__(self, signal: EngineSignal | None) -> None:
        self._signal = signal

    def generate_signal(self, *, regime, features):
        return self._signal


def _sig(engine: str, *, confidence: float = 0.7, bias: str = "long") -> EngineSignal:
    fv = make_feature_vector()
    return EngineSignal(
        engine=engine,
        sub_strategy="stress",
        asset_class=fv.asset_class,
        symbol=fv.symbol,
        bias=bias,
        confidence=confidence,
        stop_distance=0.01,
        expected_return=0.02,
        atr=fv.atr_14,
    )


def _decision(mode: str = "auto") -> Decision:
    return Decision(
        action="long",
        asset_class="crypto",
        symbol="BTCUSDT",
        execution_mode=mode,
        position_size=0.05,
        leverage=1.0,
        stop_loss=0.02,
        take_profit=0.04,
        confidence=0.8,
        engine="TITAN",
        reason="stress_test",
        timestamp=datetime.now(timezone.utc),
    )


def test_stress_router_handles_regime_flapping() -> None:
    router = RegimeRouter(
        engines={
            ENGINE_AEGEAN: _Engine(_sig(ENGINE_AEGEAN)),
            ENGINE_TITAN: _Engine(_sig(ENGINE_TITAN)),
            ENGINE_NAUTILUS: _Engine(_sig(ENGINE_NAUTILUS)),
            ENGINE_PHOENIX: _Engine(_sig(ENGINE_PHOENIX)),
            ENGINE_HERMES: _Engine(None),
        }
    )
    regimes = [REGIME_TRENDING, REGIME_RANGING, REGIME_VOLATILE] * 60
    outputs = []
    fv = make_feature_vector()
    for regime in regimes:
        outputs.append(router.route(regime=make_regime_state(regime), features=fv))
    assert len(outputs) == len(regimes)
    assert any(sig is not None for sig in outputs)


def test_stress_nan_feature_vector_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_feature_vector(atr_14=float("nan"))


def test_stress_hermes_block_gate_is_stable_over_iterations() -> None:
    fv = make_feature_vector()
    regime = make_regime_state(REGIME_TRENDING)
    for _ in range(200):
        result = evaluate_gates(
            GateInput(
                sentinel_score=0.95,
                regime=regime,
                rsl_level=0,
                signal=_sig(ENGINE_TITAN),
                features=fv,
                hermes_block_active=True,
            )
        )
        assert result.approved is False
        assert result.reason == "hermes_block_active"
        assert result.gate_number == 2


def test_stress_pre_trade_correlation_guard_blocks() -> None:
    checker = PreTradeChecker()
    for corr in (0.61, 0.75, 0.95):
        res = checker.check(
            PreTradeInput(
                asset_class="crypto",
                position_size=0.05,
                leverage=1.0,
                trades_today=1,
                stop_loss=0.02,
                correlation_with_book=corr,
            )
        )
        assert res.approved is False
        assert "correlation_limit" in res.violations


def test_stress_executor_survives_flaky_broker() -> None:
    class _FlakyBroker:
        def __init__(self) -> None:
            self.calls = 0

        def place_order(self, *, symbol: str, side: str, size: float, order_type: str, urgency: str):
            self.calls += 1
            if self.calls % 2 == 0:
                raise RuntimeError("simulated_exchange_error")
            return {
                "order_id": f"ord-{self.calls}",
                "fill_price": 100.0,
                "fill_quantity": size,
                "slippage": 0.0,
                "fees": 0.0,
            }

    broker = _FlakyBroker()
    executor = Executor(broker=broker)
    results = [executor.execute(decision=_decision("auto"), urgency="HIGH") for _ in range(30)]
    assert any(r.success for r in results)
    assert any((not r.success) and "execution_failed" in r.reason for r in results)


def test_stress_advisory_mode_never_calls_broker() -> None:
    class _CrashBroker:
        def place_order(self, *, symbol: str, side: str, size: float, order_type: str, urgency: str):
            raise AssertionError("broker should not be called in advisory mode")

    executor = Executor(broker=_CrashBroker())
    for _ in range(30):
        result = executor.execute(decision=_decision("advisory"))
        assert result.success is True
        assert result.execution_mode == "advisory"
        assert result.advisory_message is not None
