from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.strategy.lifecycle import (
    StrategyLifecycleManager,
    StrategyPerformanceSnapshot,
    StrategyState,
)


def test_lifecycle_freezes_on_hard_risk_violation() -> None:
    manager = StrategyLifecycleManager()
    snap = StrategyPerformanceSnapshot(
        strategy_id="S1",
        trades=50,
        expectancy=0.1,
        sharpe=1.1,
        max_dd_pct=2.0,
        error_rate_pct=0.1,
        telemetry_stale_sec=5.0,
        hard_risk_violations=1,
        consecutive_loss_days=0,
    )
    d = manager.evaluate(StrategyState.PAPER, snap)
    assert d.next_state == StrategyState.FROZEN
    assert d.action == "FREEZE"


def test_lifecycle_promotes_paper_to_micro_live() -> None:
    manager = StrategyLifecycleManager()
    snap = StrategyPerformanceSnapshot(
        strategy_id="S2",
        trades=180,
        expectancy=0.05,
        sharpe=1.2,
        max_dd_pct=3.2,
        error_rate_pct=0.2,
        telemetry_stale_sec=10.0,
        hard_risk_violations=0,
        consecutive_loss_days=0,
    )
    d = manager.evaluate(StrategyState.PAPER, snap)
    assert d.next_state == StrategyState.MICRO_LIVE
    assert d.action == "PROMOTE"


def test_lifecycle_retires_on_persistent_losses() -> None:
    manager = StrategyLifecycleManager()
    snap = StrategyPerformanceSnapshot(
        strategy_id="S3",
        trades=200,
        expectancy=-0.2,
        sharpe=-0.6,
        max_dd_pct=9.0,
        error_rate_pct=0.4,
        telemetry_stale_sec=6.0,
        hard_risk_violations=0,
        consecutive_loss_days=16,
    )
    d = manager.evaluate(StrategyState.MICRO_LIVE, snap)
    assert d.next_state == StrategyState.RETIRED
    assert d.action == "RETIRE"
