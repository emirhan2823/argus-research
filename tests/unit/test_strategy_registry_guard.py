from __future__ import annotations

import json
from pathlib import Path

from argus_py.strategy.registry_guard import StrategyRegistryGuard


def test_registry_guard_reads_strategy_registry_schema(tmp_path: Path) -> None:
    reg = {
        "strategies": {
            "TOPHUNTER_SHORT_V1": {"enabled": False, "disable_reason": "negative_expectancy"},
            "COUNCIL_BASELINE": {"enabled": True, "disable_reason": None},
        }
    }
    reg_path = tmp_path / "strategy_registry.json"
    reg_path.write_text(json.dumps(reg), encoding="utf-8")

    guard = StrategyRegistryGuard([reg_path])
    disabled, reason = guard.is_disabled("TOPHUNTER_SHORT_V1")
    enabled, reason_enabled = guard.is_disabled("COUNCIL_BASELINE")

    assert disabled is True
    assert "negative_expectancy" in reason
    assert enabled is False
    assert reason_enabled == "enabled_or_not_listed"


def test_registry_guard_reads_disabled_list_schema(tmp_path: Path) -> None:
    disabled_payload = {
        "disabled_strategies": [
            {"strategy_id": "COUNCIL_BASELINE", "reason": "manual_kill"},
        ]
    }
    disabled_path = tmp_path / "disabled_strategies.json"
    disabled_path.write_text(json.dumps(disabled_payload), encoding="utf-8")

    guard = StrategyRegistryGuard([disabled_path])
    disabled, reason = guard.is_disabled("COUNCIL_BASELINE")
    assert disabled is True
    assert reason == "manual_kill"
