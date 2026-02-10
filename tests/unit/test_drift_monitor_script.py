from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_drift_monitor_generates_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reports_dir = tmp_path / "reports"

    _write_csv(
        run_dir / "decisions.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "regime", "mode", "decision", "direction", "score", "exp_move", "adx", "reasons"],
        [
            ["2026-01-01T00:00:00", "2026-01-01T00:00:00", "BTCUSDT", "CHOP", "DEFENSE", "GO", "SELL", 1.0, 10.0, 30.0, ""],
        ],
    )
    _write_csv(
        run_dir / "rejects.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "code", "detail"],
        [],
    )
    _write_csv(
        run_dir / "trades.csv",
        ["ts_iso", "symbol", "side", "price", "qty", "commission", "pnl", "event", "mark_price", "fill_price", "slip_applied", "spread_applied", "asset_class", "venue_id", "strategy_id"],
        [
            ["2026-01-01T00:10:00", "BTCUSDT", "SELL", 100.0, 1.0, 0.1, 0.0, "OPEN", 100.0, 100.0, 1.0, 1.0, "crypto", "sim", "COUNCIL_BASELINE"],
            ["2026-01-01T00:20:00", "BTCUSDT", "BUY", 99.0, 1.0, 0.1, 1.0, "CLOSE", 99.0, 99.0, 1.0, 1.0, "crypto", "sim", "COUNCIL_BASELINE"],
        ],
    )
    (run_dir / "heartbeat.json").write_text(json.dumps({"ts_iso": "2026-01-01T00:30:00", "counters": {"bars_seen": 10}}), encoding="utf-8")
    (run_dir / "daemon_state.json").write_text(json.dumps({"config_snapshot": {"strategy": "council", "start_balance": 1000.0}}), encoding="utf-8")

    out_md = reports_dir / "drift_monitor.md"
    out_json = reports_dir / "drift_monitor.json"

    cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts/drift_monitor.py"),
        "--run-dir",
        str(run_dir),
        "--out-md",
        str(out_md),
        "--out-json",
        str(out_json),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert out_md.exists()
    assert out_json.exists()
