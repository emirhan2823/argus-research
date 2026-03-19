from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.risk.auto_risk_optimizer import (
    RiskConfigReloader,
    load_risk_config,
    save_risk_config,
    should_run_monthly_optimization,
)
from src.risk.dynamic_risk_manager import RiskConfig


def test_load_risk_config_missing_returns_none(tmp_path: Path) -> None:
    assert load_risk_config(tmp_path / "missing.json") is None


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "risk_config.json"
    cfg = RiskConfig(
        atr_multiplier=1.8,
        rr_ratio=2.5,
        leverage_cap=4.0,
        atr_multiplier_long=1.6,
        atr_multiplier_short=1.9,
        rr_ratio_long=2.2,
        rr_ratio_short=2.8,
        leverage_cap_long=4.2,
        leverage_cap_short=3.6,
        trailing_activation_long=1.0,
        trailing_activation_short=1.2,
        volatility_threshold=0.04,
        vol_k=18.0,
        drawdown_sensitivity=1.3,
        confidence_floor=0.62,
    )
    save_risk_config(path, config=cfg, engine="Titan")
    loaded = load_risk_config(path)
    assert loaded is not None
    assert loaded.engine == "Titan"
    assert loaded.config.atr_multiplier == pytest.approx(1.8)
    assert loaded.config.rr_ratio == pytest.approx(2.5)
    assert loaded.config.leverage_cap == pytest.approx(4.0)
    assert loaded.config.atr_multiplier_long == pytest.approx(1.6)
    assert loaded.config.atr_multiplier_short == pytest.approx(1.9)
    assert loaded.config.rr_ratio_long == pytest.approx(2.2)
    assert loaded.config.rr_ratio_short == pytest.approx(2.8)
    assert loaded.config.leverage_cap_long == pytest.approx(4.2)
    assert loaded.config.leverage_cap_short == pytest.approx(3.6)
    assert loaded.config.trailing_activation_short == pytest.approx(1.2)
    assert loaded.config.volatility_threshold == pytest.approx(0.04)
    assert loaded.config.vol_k == pytest.approx(18.0)
    assert loaded.config.drawdown_sensitivity == pytest.approx(1.3)
    assert loaded.config.confidence_floor == pytest.approx(0.62)


def test_should_run_monthly_optimization_triggers_on_first_run() -> None:
    now = datetime.now(timezone.utc)
    assert should_run_monthly_optimization(
        now_utc=now,
        last_run_utc=None,
        rolling_30d_performance=None,
        benchmark=0.0,
    )


def test_should_run_monthly_optimization_triggers_on_30_days_elapsed() -> None:
    now = datetime.now(timezone.utc)
    last = now - timedelta(days=31)
    assert should_run_monthly_optimization(
        now_utc=now,
        last_run_utc=last,
        rolling_30d_performance=0.10,
        benchmark=0.0,
    )


def test_should_run_monthly_optimization_triggers_on_underperformance() -> None:
    now = datetime.now(timezone.utc)
    last = now - timedelta(days=5)
    assert should_run_monthly_optimization(
        now_utc=now,
        last_run_utc=last,
        rolling_30d_performance=-0.05,
        benchmark=0.0,
    )


def test_should_run_monthly_optimization_does_not_trigger_when_healthy() -> None:
    now = datetime.now(timezone.utc)
    last = now - timedelta(days=5)
    assert (
        should_run_monthly_optimization(
            now_utc=now,
            last_run_utc=last,
            rolling_30d_performance=0.05,
            benchmark=0.0,
        )
        is False
    )


def test_risk_config_reloader_detects_changes(tmp_path: Path) -> None:
    path = tmp_path / "risk_config.json"
    reloader = RiskConfigReloader(path)

    assert reloader.maybe_reload() is None

    save_risk_config(path, config=RiskConfig(atr_multiplier=1.5), engine="Titan")
    first = reloader.maybe_reload()
    assert first is not None
    assert first.config.atr_multiplier == pytest.approx(1.5)

    # No changes => no reload
    assert reloader.maybe_reload() is None

    save_risk_config(path, config=RiskConfig(atr_multiplier=2.0), engine="Titan")
    second = reloader.maybe_reload()
    assert second is not None
    assert second.config.atr_multiplier == pytest.approx(2.0)
