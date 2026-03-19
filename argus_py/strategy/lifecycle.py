from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StrategyState(str, Enum):
    CANDIDATE = "CANDIDATE"
    PAPER = "PAPER"
    MICRO_LIVE = "MICRO_LIVE"
    LIVE = "LIVE"
    FROZEN = "FROZEN"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class StrategyPerformanceSnapshot:
    strategy_id: str
    trades: int
    expectancy: float
    sharpe: float
    max_dd_pct: float
    error_rate_pct: float
    telemetry_stale_sec: float
    hard_risk_violations: int
    consecutive_loss_days: int


@dataclass(frozen=True)
class LifecycleDecision:
    current_state: StrategyState
    next_state: StrategyState
    action: str
    reason: str
    requires_manual_approval: bool = False


class StrategyLifecycleManager:
    """Promote / Freeze / Retire decision engine for strategy governance."""

    def __init__(
        self,
        freeze_error_rate_pct: float = 5.0,
        freeze_telemetry_stale_sec: float = 900.0,
        paper_to_micro_min_trades: int = 120,
        micro_to_live_min_trades: int = 300,
    ) -> None:
        self.freeze_error_rate_pct = float(freeze_error_rate_pct)
        self.freeze_telemetry_stale_sec = float(freeze_telemetry_stale_sec)
        self.paper_to_micro_min_trades = int(paper_to_micro_min_trades)
        self.micro_to_live_min_trades = int(micro_to_live_min_trades)

    def evaluate(self, current: StrategyState, s: StrategyPerformanceSnapshot) -> LifecycleDecision:
        if current == StrategyState.RETIRED:
            return LifecycleDecision(current, StrategyState.RETIRED, "KEEP", "Strategy already retired.")

        if s.hard_risk_violations > 0:
            return LifecycleDecision(
                current,
                StrategyState.FROZEN,
                "FREEZE",
                f"Hard risk violations detected: {s.hard_risk_violations}",
            )

        if s.error_rate_pct >= self.freeze_error_rate_pct:
            return LifecycleDecision(
                current,
                StrategyState.FROZEN,
                "FREEZE",
                f"Error rate too high: {s.error_rate_pct:.2f}%",
            )

        if s.telemetry_stale_sec > self.freeze_telemetry_stale_sec:
            return LifecycleDecision(
                current,
                StrategyState.FROZEN,
                "FREEZE",
                f"Telemetry stale: {s.telemetry_stale_sec:.1f}s",
            )

        if s.consecutive_loss_days >= 15 or (s.expectancy < -0.10 and s.trades >= 120):
            return LifecycleDecision(
                current,
                StrategyState.RETIRED,
                "RETIRE",
                "Performance deterioration breached retirement policy.",
                requires_manual_approval=True,
            )

        if current == StrategyState.CANDIDATE:
            if s.trades >= 30 and s.expectancy > 0.0:
                return LifecycleDecision(current, StrategyState.PAPER, "PROMOTE", "Candidate validated in shadow stats.")
            return LifecycleDecision(current, current, "KEEP", "Insufficient candidate evidence.")

        if current == StrategyState.PAPER:
            if (
                s.trades >= self.paper_to_micro_min_trades
                and s.expectancy > 0.0
                and s.sharpe >= 0.8
                and s.max_dd_pct <= 5.0
                and s.error_rate_pct < 1.0
            ):
                return LifecycleDecision(current, StrategyState.MICRO_LIVE, "PROMOTE", "Paper gate passed.")
            return LifecycleDecision(current, current, "KEEP", "Paper gate not yet passed.")

        if current == StrategyState.MICRO_LIVE:
            if (
                s.trades >= self.micro_to_live_min_trades
                and s.expectancy > 0.0
                and s.sharpe >= 1.0
                and s.max_dd_pct <= 4.0
                and s.error_rate_pct < 0.5
            ):
                return LifecycleDecision(
                    current,
                    StrategyState.LIVE,
                    "PROMOTE",
                    "Micro-live gate passed.",
                    requires_manual_approval=True,
                )
            return LifecycleDecision(current, current, "KEEP", "Micro-live gate not yet passed.")

        if current == StrategyState.FROZEN:
            if s.error_rate_pct < 1.0 and s.telemetry_stale_sec <= 120.0 and s.hard_risk_violations == 0:
                return LifecycleDecision(
                    current,
                    StrategyState.PAPER,
                    "UNFREEZE",
                    "Risk signals normalized.",
                    requires_manual_approval=True,
                )
            return LifecycleDecision(current, current, "KEEP", "Still frozen pending stability recovery.")

        return LifecycleDecision(current, current, "KEEP", "No state transition required.")


__all__ = [
    "StrategyLifecycleManager",
    "StrategyPerformanceSnapshot",
    "StrategyState",
    "LifecycleDecision",
]
