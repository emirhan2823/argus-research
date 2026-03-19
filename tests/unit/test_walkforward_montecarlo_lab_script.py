from __future__ import annotations

import csv
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_price_series(path: Path, days: int = 300) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    rows = []
    for i in range(days):
        ts = (start + timedelta(days=i)).timestamp()
        price += 0.5
        rows.append([ts, price, price + 1.0, price - 1.0, price, 1000 + i])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        w.writerows(rows)


def test_walkforward_montecarlo_lab_script(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    out_dir = tmp_path / "out"
    _write_price_series(data_path / "BTCUSDT.csv")

    cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts/walkforward_montecarlo_lab.py"),
        "--data-path",
        str(data_path),
        "--symbol",
        "BTCUSDT",
        "--start-date",
        "2025-01-01",
        "--end-date",
        "2025-12-01",
        "--out-dir",
        str(out_dir),
        "--mc-runs",
        "100",
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=40)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert (out_dir / "walkforward_montecarlo.md").exists()
    assert (out_dir / "walkforward_montecarlo.json").exists()
