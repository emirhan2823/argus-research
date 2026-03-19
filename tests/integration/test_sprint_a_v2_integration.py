from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.paper_daemon import DEFAULT_CONFIG, PaperDaemon
from argus_py.data.market_state import Bar


def _cfg(tmp_path: Path):
    cfg = DEFAULT_CONFIG.copy()
    run_dir = tmp_path / "run"
    cfg["run_dir"] = run_dir
    cfg["daemon_id"] = "TEST_V2"
    cfg["run_id"] = "itest_v2"
    cfg["mode"] = "v2"
    cfg["strategy"] = "council"
    cfg["interval"] = "1m"
    cfg["args"] = Namespace(symbol=cfg["symbol"], min_adx=cfg["min_adx"])
    return cfg


def _bars(n: int = 320) -> list[Bar]:
    out: list[Bar] = []
    ts0 = 1_700_000_000.0
    price = 100.0
    for i in range(n):
        drift = 0.03
        noise = ((i % 7) - 3) * 0.01
        prev = price
        price = max(1.0, price + drift + noise)
        high = max(prev, price) + 0.15
        low = min(prev, price) - 0.15
        out.append(
            Bar(
                timestamp=ts0 + (i * 60.0),
                open=prev,
                high=high,
                low=low,
                close=price,
                volume=1000.0 + i,
            )
        )
    return out


def _sqlite_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()
    return int(row[0]) if row else 0


def test_sprint_a_v2_end_to_end_pipeline(tmp_path):
    cfg = _cfg(tmp_path)
    daemon = PaperDaemon(cfg)

    bars = _bars(340)
    daemon.history_bars = bars[:-1]
    daemon.process_bar(bars[-1])
    daemon.update_heartbeat(last_bar=bars[-1])

    run_dir = Path(cfg["run_dir"])
    metrics_path = run_dir / "metrics.json"
    events_path = run_dir / "events_v2.jsonl"
    warehouse_db = run_dir / "warehouse" / "cold" / "metrics.sqlite3"

    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics.get("mode") == "v2"
    assert isinstance(metrics.get("v2"), dict)
    assert events_path.exists()
    assert events_path.read_text(encoding="utf-8").strip() != ""
    assert _sqlite_rows(warehouse_db) > 0

    reports_dir = tmp_path / "reports"
    nightly_cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts/nightly_eval.py"),
        "--mode",
        "v2",
        "--run-dir",
        str(run_dir),
        "--reports-dir",
        str(reports_dir),
    ]
    nightly = subprocess.run(nightly_cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30)
    assert nightly.returncode == 0, nightly.stdout + "\n" + nightly.stderr

    nightly_metrics = reports_dir / "metrics.json"
    assert nightly_metrics.exists()
    nightly_payload = json.loads(nightly_metrics.read_text(encoding="utf-8"))
    assert nightly_payload.get("mode") == "v2"
    assert isinstance(nightly_payload.get("v2"), dict)

    validation_report = reports_dir / "integration_validation.md"
    validate_cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts/integration_validate.py"),
        "--run-dir",
        str(run_dir),
        "--report",
        str(validation_report),
        "--nightly-metrics",
        str(nightly_metrics),
    ]
    validate = subprocess.run(validate_cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30)
    assert validate.returncode == 0, validate.stdout + "\n" + validate.stderr
    assert validation_report.exists()
    content = validation_report.read_text(encoding="utf-8")
    assert "Sprint A Integration Validation" in content
    assert "mode_is_v2" in content
