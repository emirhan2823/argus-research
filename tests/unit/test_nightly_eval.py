from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_nightly_eval_generates_markdown_and_metrics(tmp_path):
    run_dir = tmp_path / "run"
    reports_dir = tmp_path / "reports"
    now = int(time.time())

    _write_csv(
        run_dir / "decisions.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "regime", "mode", "decision", "direction", "score", "exp_move", "adx", "reasons"],
        [
            [now - 3600, now - 3600, "BTCUSDT", "CHOP", "DEFENSE", "GO", "SELL", 1.2, 8.0, 18.0, ""],
            [now - 1800, now - 1800, "BTCUSDT", "CHOP", "DEFENSE", "BLOCK", "SELL", 0.0, 0.0, 10.0, "MIN_ADX"],
        ],
    )

    _write_csv(
        run_dir / "rejects.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "code", "detail"],
        [[now - 1700, now - 1700, "BTCUSDT", "MIN_ADX", "10<20"]],
    )

    _write_csv(
        run_dir / "trades.csv",
        ["ts_iso", "symbol", "side", "price", "qty", "pnl", "event"],
        [
            [now - 1500, "BTCUSDT", "SELL", 50000.0, 0.01, 0.0, "OPEN"],
            [now - 1400, "BTCUSDT", "BUY", 49800.0, 0.01, 2.0, "CLOSE"],
        ],
    )

    cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts/nightly_eval.py"),
        "--run-dir",
        str(run_dir),
        "--reports-dir",
        str(reports_dir),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

    md_path = reports_dir / "nightly_eval.md"
    metrics_path = reports_dir / "metrics.json"

    assert md_path.exists()
    assert metrics_path.exists()

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "window_24h" in payload
    assert "window_7d" in payload
    assert "compare" in payload
    assert payload["window_24h"]["trades"] >= 1
