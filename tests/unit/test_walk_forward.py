from datetime import date, datetime, timedelta
from pathlib import Path
import json
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.walk_forward import WFReport, WalkForwardEngine


def _write_daily_csv(path: Path, start: date, days: int, base: float = 100.0):
    rows = []
    price = base
    for i in range(days):
        d = start + timedelta(days=i)
        ts = datetime(d.year, d.month, d.day).timestamp()
        price += 0.5
        rows.append([ts, price, price + 1, price - 1, price, 1000 + i])

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df.to_csv(path, index=False)


def test_create_windows_generates_rolling_structure(tmp_path):
    engine = WalkForwardEngine(data_path=tmp_path, output_dir=tmp_path / "out")
    windows = engine.create_windows(date(2025, 1, 1), date(2026, 1, 1), train_months=6, test_months=1, step_months=1)

    assert len(windows) > 0
    first = windows[0]
    assert first.train_start < first.train_end < first.test_start <= first.test_end


def test_validate_data_detects_missing(tmp_path):
    engine = WalkForwardEngine(data_path=tmp_path, output_dir=tmp_path / "out")
    windows = engine.create_windows(date(2025, 1, 1), date(2025, 4, 1), train_months=1, test_months=1, step_months=1)
    valid, reason = engine.validate_data(windows[0])
    assert valid is False
    assert reason in {"NO_TRAIN_DATA", "NO_TEST_DATA"}


def test_run_window_produces_train_and_test_metrics(tmp_path):
    _write_daily_csv(tmp_path / "BTCUSDT.csv", date(2025, 1, 1), days=240)

    engine = WalkForwardEngine(data_path=tmp_path, output_dir=tmp_path / "out")
    report = engine.run_full(date(2025, 1, 1), date(2025, 9, 1), symbols=["BTCUSDT"], skip_invalid=False)

    assert len(report.windows) > 0
    w = report.windows[0]
    assert isinstance(w.train_trades, int)
    assert isinstance(w.test_trades, int)
    assert isinstance(w.train_sharpe, float)
    assert isinstance(w.test_sharpe, float)


def test_run_full_skips_invalid_windows_without_crash(tmp_path):
    # Limited data -> some windows invalid.
    _write_daily_csv(tmp_path / "BTCUSDT.csv", date(2025, 1, 1), days=120)

    engine = WalkForwardEngine(data_path=tmp_path, output_dir=tmp_path / "out")
    report = engine.run_full(date(2025, 1, 1), date(2025, 12, 1), symbols=["BTCUSDT"], skip_invalid=True)

    assert isinstance(report, WFReport)
    assert len(report.no_data_windows) >= 1


def test_save_report_writes_json_and_csv(tmp_path):
    _write_daily_csv(tmp_path / "BTCUSDT.csv", date(2025, 1, 1), days=260)

    out_dir = tmp_path / "out"
    engine = WalkForwardEngine(data_path=tmp_path, output_dir=out_dir)
    report = engine.run_full(date(2025, 1, 1), date(2025, 10, 1), symbols=["BTCUSDT"], skip_invalid=True)

    json_path = engine.save_report(report, "wf_report")
    csv_path = out_dir / "wf_report.csv"

    assert json_path.exists()
    assert csv_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "aggregate_sharpe" in payload
    assert "windows" in payload


def test_aggregate_metrics_calculated(tmp_path):
    _write_daily_csv(tmp_path / "BTCUSDT.csv", date(2025, 1, 1), days=280)

    engine = WalkForwardEngine(data_path=tmp_path, output_dir=tmp_path / "out")
    report = engine.run_full(date(2025, 1, 1), date(2025, 11, 1), symbols=["BTCUSDT"], skip_invalid=True)

    assert isinstance(report.aggregate_sharpe, float)
    assert isinstance(report.aggregate_pnl, float)
    assert isinstance(report.aggregate_dd, float)
