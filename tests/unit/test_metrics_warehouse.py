from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.telemetry.metrics_warehouse import MetricPoint, MetricsWarehouse, make_metric_point


def test_metrics_warehouse_writes_cold_and_warm_with_fallback(tmp_path) -> None:
    wh = MetricsWarehouse(
        redis_url=None,
        warm_dir=tmp_path / "warm",
        cold_db=tmp_path / "cold" / "metrics.sqlite3",
    )
    p = make_metric_point("expectancy", 0.12, "unit", {"strategy": "TOPHUNTER"})
    res = wh.write(p)

    assert res.cold_written is True
    assert res.warm_written is True
    assert res.hot_written is False

    cold_rows = wh.read_cold("expectancy")
    assert len(cold_rows) >= 1
    assert cold_rows[0].key == "expectancy"

    partition = (tmp_path / "warm" / f"date={p.ts_utc[:10]}")
    parquet_file = partition / "metrics.parquet"
    fallback_file = partition / "metrics.parquet.unavailable.jsonl"
    assert parquet_file.exists() or fallback_file.exists()


def test_metrics_warehouse_rejects_invalid_timestamp(tmp_path) -> None:
    wh = MetricsWarehouse(redis_url=None, warm_dir=tmp_path / "warm", cold_db=tmp_path / "cold" / "m.sqlite3")
    bad = MetricPoint(key="x", value=1.0, ts_utc="not-a-ts", source="unit", tags={})
    with pytest.raises(ValueError):
        wh.write(bad)
