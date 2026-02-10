"""MDE sequential gate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.core.constants import ENGINE_PHOENIX, REGIME_CRISIS
from src.core.types import EngineSignal, FeatureVector, RegimeState


@dataclass(frozen=True)
class GateResult:
    approved: bool
    gate_number: int
    action: str  # hold|close_all|proceed
    reason: str
    features_snapshot: dict[str, Any]


@dataclass(frozen=True)
class GateInput:
    sentinel_score: float
    regime: RegimeState
    rsl_level: int
    signal: Optional[EngineSignal]
    features: FeatureVector
    hermes_block_active: bool = False
    min_confidence: float = 0.55
    min_net_expected_return: float = 0.001
    min_reward_risk: float = 1.5


def evaluate_gates(inp: GateInput) -> GateResult:
    snapshot = {
        "symbol": inp.features.symbol,
        "asset_class": inp.features.asset_class,
        "regime": inp.regime.regime,
        "sentinel_score": inp.sentinel_score,
        "rsl_level": inp.rsl_level,
    }

    # Gate 0: sentinel hard block
    if inp.sentinel_score < 0.4:
        return GateResult(False, 0, "hold", "sentinel_below_halt_threshold", snapshot)

    # Gate 1: crisis regime
    if inp.regime.regime == REGIME_CRISIS:
        return GateResult(False, 1, "close_all", "crisis_regime", snapshot)

    # Gate 2: HERMES block
    if inp.hermes_block_active:
        return GateResult(False, 2, "hold", "hermes_block_active", snapshot)

    # Gate 3: risk-switch level
    if inp.rsl_level >= 3:
        return GateResult(False, 3, "hold", "rsl_halt", snapshot)
    if inp.rsl_level >= 2 and (inp.signal is not None and inp.signal.engine != ENGINE_PHOENIX):
        return GateResult(False, 3, "hold", "rsl_defensive_only_phoenix", snapshot)

    # Gate 4: signal must exist
    if inp.signal is None:
        return GateResult(False, 4, "hold", "no_signal", snapshot)

    # Gate 5: confidence
    if inp.signal.confidence < inp.min_confidence:
        return GateResult(False, 5, "hold", "confidence_below_threshold", snapshot)

    # Gate 6: net expected return
    if inp.signal.expected_return < inp.min_net_expected_return:
        return GateResult(False, 6, "hold", "net_expected_return_too_low", snapshot)

    # Gate 7: reward/risk
    reward_risk_ratio = inp.signal.expected_return / max(inp.signal.stop_distance, 1e-9)
    if reward_risk_ratio < inp.min_reward_risk:
        return GateResult(False, 7, "hold", "reward_risk_below_threshold", snapshot)

    return GateResult(True, 8, "proceed", "all_gates_passed", snapshot)
