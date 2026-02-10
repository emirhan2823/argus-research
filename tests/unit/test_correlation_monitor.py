from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.risk.correlation import CorrelationRiskMonitor


def test_correlation_monitor_scales_highly_correlated_pairs() -> None:
    rng = np.random.default_rng(0)
    base = np.cumsum(rng.normal(0, 1, size=300)) + 100.0
    correlated = base + rng.normal(0, 0.2, size=300)
    low_corr = np.cumsum(rng.normal(0, 1, size=300)) + 100.0

    prices = pd.DataFrame({"BTC": base, "ETH": correlated, "XRP": low_corr})
    monitor = CorrelationRiskMonitor(threshold=0.7, min_scale=0.25)

    adjusted, details = monitor.scale_positions(prices, {"BTC": 1000.0, "ETH": 1000.0, "XRP": 1000.0})

    assert adjusted["BTC"] <= 1000.0
    assert adjusted["ETH"] <= 1000.0
    assert details["BTC"].max_abs_corr >= 0.7


def test_correlation_monitor_leaves_low_corr_positions_unchanged() -> None:
    rng = np.random.default_rng(2)
    prices = pd.DataFrame(
        {
            "A": np.cumsum(rng.normal(0, 1, size=240)) + 100,
            "B": np.cumsum(rng.normal(0, 1, size=240)) + 200,
            "C": np.cumsum(rng.normal(0, 1, size=240)) + 300,
        }
    )
    monitor = CorrelationRiskMonitor(threshold=0.99)
    adjusted, _ = monitor.scale_positions(prices, {"A": 500.0, "B": 700.0, "C": 900.0})

    assert adjusted["A"] == 500.0
    assert adjusted["B"] == 700.0
    assert adjusted["C"] == 900.0
