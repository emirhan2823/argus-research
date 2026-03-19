from __future__ import annotations

import json
from pathlib import Path

from argus_py.ops.reliability_watchdog import evaluate_reliability, write_watchdog_report


def test_reliability_watchdog_healthy_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "heartbeat.json").write_text(
        json.dumps({"ts_iso": "2026-02-10T10:00:00+00:00"}),
        encoding="utf-8",
    )
    (run_dir / "metrics.json").write_text(
        json.dumps({"bars_seen": 100, "decisions_total": 20, "trades_total": 5, "rejects_total": 8, "errors_total": 1}),
        encoding="utf-8",
    )
    status = evaluate_reliability(run_dir, stale_after_sec=10**9, max_error_ratio_pct=5.0)
    assert status.healthy
    assert status.error_ratio_pct <= 5.0


def test_reliability_watchdog_flags_missing_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    status = evaluate_reliability(run_dir, stale_after_sec=120.0, max_error_ratio_pct=1.0)
    assert not status.healthy
    assert "missing_heartbeat" in status.reasons


def test_write_watchdog_report_outputs_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "heartbeat.json").write_text(json.dumps({"ts_iso": "2026-02-10T10:00:00+00:00"}), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps({"bars_seen": 1, "errors_total": 0}), encoding="utf-8")
    status = evaluate_reliability(run_dir, stale_after_sec=10**9, max_error_ratio_pct=5.0)
    out_md = tmp_path / "watchdog.md"
    out_json = tmp_path / "watchdog.json"
    write_watchdog_report(status, out_md=out_md, out_json=out_json)
    assert out_md.exists()
    assert out_json.exists()
