from __future__ import annotations

from pathlib import Path

from src.risk.kill_switch import KillSwitch, RiskLevel


def test_kill_switch_escalation_levels(tmp_path: Path) -> None:
    db = tmp_path / "ks.db"
    ks = KillSwitch(db_path=str(db))

    assert ks.update_from_drawdown(drawdown=0.01) == RiskLevel.NORMAL
    assert ks.update_from_drawdown(drawdown=0.03) == RiskLevel.CAUTION
    assert ks.update_from_drawdown(drawdown=0.05) == RiskLevel.DEFENSIVE
    assert ks.update_from_drawdown(drawdown=0.07) == RiskLevel.HALT
    assert ks.can_trade() is False


def test_kill_switch_hermes_critical_forces_halt(tmp_path: Path) -> None:
    db = tmp_path / "ks2.db"
    ks = KillSwitch(db_path=str(db))
    level = ks.update_from_drawdown(drawdown=0.0, hermes_critical=True)
    assert level >= RiskLevel.HALT


def test_kill_switch_persistence(tmp_path: Path) -> None:
    db = tmp_path / "ks3.db"
    ks1 = KillSwitch(db_path=str(db))
    ks1.update_from_drawdown(drawdown=0.06)

    ks2 = KillSwitch(db_path=str(db))
    assert ks2.level == ks1.level
