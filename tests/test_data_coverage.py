from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from Scripts.data_coverage_validator import analyze_symbol_coverage


def _make_ohlcv_frame(timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    base = np.arange(len(timestamps), dtype=float) + 100.0
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": base,
            "high": base + 2.0,
            "low": base - 2.0,
            "close": base + 1.0,
            "volume": np.full(len(timestamps), 10.0),
        }
    )


def _write_year_parquet(
    *,
    root: Path,
    symbol: str,
    timeframe: str,
    year: int,
    frame: pd.DataFrame,
) -> None:
    out = root / symbol / timeframe
    out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out / f"{year}.parquet", index=False)


def test_deterministic_mock_dataset(tmp_path: Path) -> None:
    idx = pd.date_range("2024-01-01T00:00:00Z", periods=48, freq="1h")
    frame = _make_ohlcv_frame(idx)
    _write_year_parquet(root=tmp_path, symbol="BTCUSDT", timeframe="1h", year=2024, frame=frame)

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 3, tzinfo=timezone.utc)

    summary_a, monthly_a = analyze_symbol_coverage(
        data_root=tmp_path,
        symbol="BTCUSDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    summary_b, monthly_b = analyze_symbol_coverage(
        data_root=tmp_path,
        symbol="BTCUSDT",
        timeframe="1h",
        start=start,
        end=end,
    )

    assert summary_a == summary_b
    assert monthly_a == monthly_b
    assert summary_a.coverage_pct == 100.0
    assert summary_a.missing_count == 0
    assert summary_a.duplicate_timestamps == 0
    assert summary_a.gaps_gt_2_intervals == 0
    assert summary_a.strictly_increasing


def test_gap_detection(tmp_path: Path) -> None:
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-01-01T00:00:00Z"),
            pd.Timestamp("2024-01-01T01:00:00Z"),
            pd.Timestamp("2024-01-01T05:00:00Z"),
            pd.Timestamp("2024-01-01T06:00:00Z"),
        ]
    )
    frame = _make_ohlcv_frame(idx)
    _write_year_parquet(root=tmp_path, symbol="ETHUSDT", timeframe="1h", year=2024, frame=frame)

    summary, monthly_rows = analyze_symbol_coverage(
        data_root=tmp_path,
        symbol="ETHUSDT",
        timeframe="1h",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert summary.gaps_gt_2_intervals == 1
    assert len(monthly_rows) == 1
    assert monthly_rows[0].gaps_gt_2_intervals == 1


def test_duplicate_detection(tmp_path: Path) -> None:
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-01-01T00:00:00Z"),
            pd.Timestamp("2024-01-01T01:00:00Z"),
            pd.Timestamp("2024-01-01T02:00:00Z"),
            pd.Timestamp("2024-01-01T02:00:00Z"),  # duplicate
            pd.Timestamp("2024-01-01T03:00:00Z"),
        ]
    )
    frame = _make_ohlcv_frame(idx)
    _write_year_parquet(root=tmp_path, symbol="SOLUSDT", timeframe="1h", year=2024, frame=frame)

    summary, monthly_rows = analyze_symbol_coverage(
        data_root=tmp_path,
        symbol="SOLUSDT",
        timeframe="1h",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert summary.duplicate_timestamps == 1
    assert not summary.strictly_increasing
    assert len(monthly_rows) == 1
    assert monthly_rows[0].duplicate_timestamps == 1
