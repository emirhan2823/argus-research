from __future__ import annotations

import math
import time

from argus_py.data.market_state import Bar
from argus_py.ops.data_quality_sentinel import DataQualitySentinel


def _bar(ts: float, close: float = 100.0) -> Bar:
    return Bar(timestamp=ts, open=close * 0.99, high=close * 1.01, low=close * 0.98, close=close, volume=1000.0)


def test_data_quality_sentinel_ok_band() -> None:
    now = time.time()
    sentinel = DataQualitySentinel(interval="1m")
    history = [_bar(now - 120.0, 99.0), _bar(now - 60.0, 100.0)]
    result = sentinel.evaluate(history, now_ts=now)
    assert result.band in {"OK", "DEGRADED"}
    assert result.score > 0.4


def test_data_quality_sentinel_halts_on_nan() -> None:
    now = time.time()
    sentinel = DataQualitySentinel(interval="1m")
    bad = Bar(timestamp=now - 30.0, open=100.0, high=101.0, low=99.0, close=math.nan, volume=100.0)
    result = sentinel.evaluate([bad], now_ts=now)
    assert result.halt_new_entries
    assert result.band == "HALT"
    assert result.score < 0.4


def test_data_quality_sentinel_detects_stale_feed() -> None:
    now = time.time()
    sentinel = DataQualitySentinel(interval="1m", max_staleness_mult=2.0)
    history = [_bar(now - 900.0, 100.0)]
    result = sentinel.evaluate(history, now_ts=now)
    assert any(c.name == "freshness" and not c.passed for c in result.checks)
    assert result.band in {"DEGRADED", "HALT"}
