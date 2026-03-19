from __future__ import annotations

import pandas as pd

from src.main import ArgusPipeline


def test_backtest_sonar_init_enabled_in_replay_mode() -> None:
    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        replay_now=pd.Timestamp("2026-02-24T00:00:00Z"),
        enable_backtest_sonar=True,
    )
    assert pipeline._sonar_scanner is not None


def test_backtest_sonar_not_initialized_without_flag() -> None:
    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        replay_now=pd.Timestamp("2026-02-24T00:00:00Z"),
        enable_backtest_sonar=False,
    )
    assert pipeline._sonar_scanner is None

