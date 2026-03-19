from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass(frozen=True)
class ExecutionQualityInput:
    adx: float
    expected_move_bps: float
    volume_ratio: float
    regime_confidence: float
    aegean_confidence: float
    orion_confidence: float
    slippage_bps_estimate: float = 0.0
    spread_bps_estimate: float = 0.0


@dataclass(frozen=True)
class ExecutionQualityResult:
    score: float
    passed: bool
    threshold: float
    reason: str
    components: Dict[str, float]


class ExecutionQualityGate:
    """
    Lightweight pre-trade quality gate.

    Intended usage:
    - Score every GO signal with market-structure + confirmation + cost pressure.
    - Block low-quality entries in v2 runtime.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.55,
        min_expected_move_bps: float = 3.0,
        max_slippage_bps: float = 8.0,
        max_spread_bps: float = 6.0,
    ) -> None:
        self.threshold = _clamp(threshold)
        self.min_expected_move_bps = max(0.0, float(min_expected_move_bps))
        self.max_slippage_bps = max(0.1, float(max_slippage_bps))
        self.max_spread_bps = max(0.1, float(max_spread_bps))

    def evaluate(self, quality_in: ExecutionQualityInput) -> ExecutionQualityResult:
        trend_strength = _clamp((float(quality_in.adx) - 15.0) / 35.0)
        confirmation = _clamp((float(quality_in.aegean_confidence) + float(quality_in.orion_confidence)) / 2.0)
        volume = _clamp(float(quality_in.volume_ratio) / 1.5)
        regime = _clamp(float(quality_in.regime_confidence))

        move_denom = max(10.0, self.min_expected_move_bps * 4.0)
        move = _clamp((float(quality_in.expected_move_bps) - self.min_expected_move_bps) / move_denom)

        slip_penalty = _clamp(float(quality_in.slippage_bps_estimate) / self.max_slippage_bps)
        spread_penalty = _clamp(float(quality_in.spread_bps_estimate) / self.max_spread_bps)
        cost_penalty = _clamp((slip_penalty + spread_penalty) / 2.0)

        base = (
            (0.25 * trend_strength)
            + (0.25 * confirmation)
            + (0.20 * regime)
            + (0.15 * volume)
            + (0.15 * move)
        )
        score = _clamp(base * (1.0 - (0.45 * cost_penalty)))

        passed = bool(score >= self.threshold)
        reason = "PASS"
        if not passed:
            weakest = min(
                [
                    ("TREND", trend_strength),
                    ("CONFIRMATION", confirmation),
                    ("REGIME", regime),
                    ("VOLUME", volume),
                    ("EXPECTED_MOVE", move),
                ],
                key=lambda x: x[1],
            )[0]
            if cost_penalty >= 0.75:
                reason = "COST_PRESSURE_HIGH"
            else:
                reason = f"WEAK_{weakest}"

        components = {
            "trend_strength": trend_strength,
            "confirmation": confirmation,
            "volume": volume,
            "regime": regime,
            "expected_move": move,
            "cost_penalty": cost_penalty,
        }
        return ExecutionQualityResult(
            score=score,
            passed=passed,
            threshold=self.threshold,
            reason=reason,
            components=components,
        )

    @staticmethod
    def quality_grade(score: float) -> str:
        v = _clamp(score)
        if v >= 0.85:
            return "A"
        if v >= 0.70:
            return "B"
        if v >= 0.55:
            return "C"
        return "D"


__all__ = [
    "ExecutionQualityGate",
    "ExecutionQualityInput",
    "ExecutionQualityResult",
]
