from __future__ import annotations

from argus_py.risk.execution_quality_gate import ExecutionQualityGate, ExecutionQualityInput


def test_execution_quality_gate_passes_high_quality_signal() -> None:
    gate = ExecutionQualityGate(threshold=0.55)
    result = gate.evaluate(
        ExecutionQualityInput(
            adx=38.0,
            expected_move_bps=24.0,
            volume_ratio=1.4,
            regime_confidence=0.85,
            aegean_confidence=0.82,
            orion_confidence=0.79,
            slippage_bps_estimate=1.5,
            spread_bps_estimate=0.8,
        )
    )
    assert result.passed
    assert result.score >= 0.55
    assert ExecutionQualityGate.quality_grade(result.score) in {"A", "B", "C"}


def test_execution_quality_gate_blocks_cost_pressure() -> None:
    gate = ExecutionQualityGate(threshold=0.60, max_slippage_bps=4.0, max_spread_bps=2.0)
    result = gate.evaluate(
        ExecutionQualityInput(
            adx=30.0,
            expected_move_bps=10.0,
            volume_ratio=1.0,
            regime_confidence=0.7,
            aegean_confidence=0.7,
            orion_confidence=0.7,
            slippage_bps_estimate=6.0,
            spread_bps_estimate=3.5,
        )
    )
    assert not result.passed
    assert result.reason.startswith("WEAK_") or result.reason == "COST_PRESSURE_HIGH"
