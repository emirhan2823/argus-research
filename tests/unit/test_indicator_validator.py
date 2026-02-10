from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.validation.indicator_validator import IndicatorValidator



def _market_frame(rows: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    base = 100.0 + np.cumsum(rng.normal(0.0, 0.6, rows))
    spread = np.abs(rng.normal(0.6, 0.2, rows))
    high = base + spread
    low = base - spread
    close = base + rng.normal(0.0, 0.15, rows)
    open_ = base + rng.normal(0.0, 0.15, rows)
    vol = rng.uniform(50, 200, rows)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )



def test_indicator_validator_produces_full_report() -> None:
    validator = IndicatorValidator()
    report = validator.validate(_market_frame())

    assert set(report.metrics.keys()) == {
        "bb_lower",
        "bb_mid",
        "bb_upper",
        "macd",
        "rsi",
        "stoch_d",
        "stoch_k",
    }
    assert report.backend in {"freqtrade", "internal_compat"}
    assert report.passed
    assert all(metric.samples > 0 for metric in report.metrics.values())



def test_indicator_validator_assert_valid_raises_when_tolerance_tight() -> None:
    validator = IndicatorValidator(tolerances={"rsi": 0.0})

    class FaultyValidator(IndicatorValidator):
        def _reference_indicators(self, frame, closes, highs, lows):
            refs, backend = super()._reference_indicators(frame, closes, highs, lows)
            refs["rsi"] = refs["rsi"] + 0.1
            return refs, backend

    faulty = FaultyValidator(tolerances={"rsi": 1e-9})
    with pytest.raises(ValueError):
        faulty.assert_valid(_market_frame())



def test_indicator_validator_rejects_invalid_frame() -> None:
    validator = IndicatorValidator()
    with pytest.raises(ValueError):
        validator.validate(pd.DataFrame({"close": [1.0, 2.0]}))
