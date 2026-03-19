from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ml.model_registry import ModelRegistry, metrics_now


def test_model_registry_promotes_better_challenger(tmp_path) -> None:
    path = tmp_path / "model_registry.json"
    reg = ModelRegistry(
        path,
        min_trades_for_promotion=20,
        min_expectancy_edge=0.02,
        min_sharpe_edge=0.05,
        max_dd_guard_pct=10.0,
    )
    reg.ensure_champion("COUNCIL", "M_BASE")
    reg.register_challenger("COUNCIL", "M_NEW")

    reg.record_metrics(
        metrics_now(
            strategy_id="COUNCIL",
            model_id="M_BASE",
            trades=40,
            expectancy=0.06,
            sharpe=1.00,
            max_dd_pct=3.0,
        )
    )
    reg.record_metrics(
        metrics_now(
            strategy_id="COUNCIL",
            model_id="M_NEW",
            trades=40,
            expectancy=0.10,
            sharpe=1.20,
            max_dd_pct=3.2,
        )
    )

    decision = reg.evaluate("COUNCIL")
    assert decision.action == "PROMOTE_CHALLENGER"
    assert decision.champion_before == "M_BASE"
    assert decision.champion_after == "M_NEW"
    assert reg.active_model("COUNCIL") == "M_NEW"

    reloaded = ModelRegistry(path)
    assert reloaded.active_model("COUNCIL") == "M_NEW"


def test_model_registry_rejects_high_drawdown_challenger(tmp_path) -> None:
    path = tmp_path / "model_registry.json"
    reg = ModelRegistry(path, min_trades_for_promotion=10, max_dd_guard_pct=8.0)
    reg.ensure_champion("COUNCIL", "M_BASE")
    reg.register_challenger("COUNCIL", "M_RISKY")

    reg.record_metrics(
        metrics_now(
            strategy_id="COUNCIL",
            model_id="M_BASE",
            trades=20,
            expectancy=0.04,
            sharpe=0.80,
            max_dd_pct=3.5,
        )
    )
    reg.record_metrics(
        metrics_now(
            strategy_id="COUNCIL",
            model_id="M_RISKY",
            trades=30,
            expectancy=0.50,
            sharpe=2.00,
            max_dd_pct=12.0,
        )
    )

    decision = reg.evaluate("COUNCIL")
    assert decision.action == "KEEP"
    assert decision.reason == "Challenger drawdown too high."
    assert reg.active_model("COUNCIL") == "M_BASE"

