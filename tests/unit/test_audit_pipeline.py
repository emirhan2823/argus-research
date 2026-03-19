import csv
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.reporting.audit_pipeline import AuditPipeline


def _write_csv(path: Path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def test_generate_handles_missing_files_gracefully(tmp_path):
    pipeline = AuditPipeline(tmp_path)
    report = pipeline.generate_weekly_report("2026-W06")

    assert report.conversion_metrics.total_signals == 0
    assert report.conversion_metrics.total_opens == 0
    assert report.rejection_breakdown.total_rejects == 0
    assert report.recommendations


def test_invalid_week_format_raises(tmp_path):
    pipeline = AuditPipeline(tmp_path)
    with pytest.raises(ValueError):
        pipeline.generate_weekly_report("2026/06")


def test_filters_rows_by_iso_week(tmp_path):
    _write_csv(
        tmp_path / "decisions.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "regime", "mode", "decision", "direction", "score", "exp_move", "adx", "reasons"],
        [
            ["2026-02-06T10:00:00", "2026-02-06T09:59:00", "BTCUSDT", "TREND", "ATTACK", "GO", "BUY", "0.9", "12", "30", ""],
            ["2026-02-10T10:00:00", "2026-02-10T09:59:00", "BTCUSDT", "TREND", "ATTACK", "GO", "BUY", "0.9", "12", "30", ""],
        ],
    )
    _write_csv(
        tmp_path / "trades.csv",
        ["ts_iso", "symbol", "side", "price", "qty", "pnl", "event"],
        [
            ["2026-02-06T10:00:01", "BTCUSDT", "BUY", "70000", "0.01", "0", "OPEN"],
            ["2026-02-10T10:00:01", "BTCUSDT", "BUY", "70000", "0.01", "0", "OPEN"],
        ],
    )
    _write_csv(
        tmp_path / "rejects.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "code", "detail"],
        [
            ["2026-02-06T10:01:00", "2026-02-06T09:59:00", "BTCUSDT", "MAX_EXP", "x"],
            ["2026-02-10T10:01:00", "2026-02-10T09:59:00", "BTCUSDT", "MAX_EXP", "x"],
        ],
    )

    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    assert report.conversion_metrics.total_signals == 1
    assert report.conversion_metrics.total_opens == 1
    assert report.rejection_breakdown.total_rejects == 1


def test_rejection_counts_sum_correctly(tmp_path):
    _write_csv(
        tmp_path / "decisions.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "regime", "mode", "decision", "direction", "score", "exp_move", "adx", "reasons"],
        [
            ["2026-02-06T11:00:00", "2026-02-06T10:59:00", "BTCUSDT", "CHOP", "DEFENSE", "NO_GO", "HOLD", "0", "0", "10", ""],
        ],
    )
    _write_csv(
        tmp_path / "rejects.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "code", "detail"],
        [
            ["2026-02-06T11:01:00", "2026-02-06T10:59:00", "BTCUSDT", "MAX_EXP", "x"],
            ["2026-02-06T11:02:00", "2026-02-06T10:59:00", "BTCUSDT", "MAX_EXP", "x"],
            ["2026-02-06T11:03:00", "2026-02-06T10:59:00", "BTCUSDT", "ROUTER_DEFENSE", "x"],
        ],
    )

    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    rb = report.rejection_breakdown

    assert rb.total_rejects == 3
    assert sum(rb.by_code.values()) == rb.total_rejects
    assert sum(rb.by_regime.values()) == rb.total_rejects
    assert rb.top_5_codes[0][0] == "MAX_EXP"
    assert rb.top_5_codes[0][1] == 2


def test_rejection_regime_mapping_uses_decisions_bar_ts(tmp_path):
    _write_csv(
        tmp_path / "decisions.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "regime", "mode", "decision", "direction", "score", "exp_move", "adx", "reasons"],
        [
            ["2026-02-06T12:00:00", "2026-02-06T11:59:00", "BTCUSDT", "TREND", "ATTACK", "GO", "BUY", "0.8", "10", "25", ""],
            ["2026-02-06T12:01:00", "2026-02-06T12:00:00", "BTCUSDT", "CHOP", "DEFENSE", "NO_GO", "HOLD", "0.0", "0", "12", ""],
        ],
    )
    _write_csv(
        tmp_path / "rejects.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "code", "detail"],
        [
            ["2026-02-06T12:02:00", "2026-02-06T11:59:00", "BTCUSDT", "MAX_EXP", "x"],
            ["2026-02-06T12:03:00", "2026-02-06T12:00:00", "BTCUSDT", "MIN_ADX", "x"],
        ],
    )

    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    assert report.rejection_breakdown.by_regime["TREND"] == 1
    assert report.rejection_breakdown.by_regime["CHOP"] == 1


def test_conversion_metrics_calculation(tmp_path):
    _write_csv(
        tmp_path / "decisions.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "regime", "mode", "decision", "direction", "score", "exp_move", "adx", "reasons"],
        [
            ["2026-02-06T13:00:00", "2026-02-06T12:59:00", "BTCUSDT", "TREND", "ATTACK", "GO", "BUY", "0.8", "10", "25", ""],
            ["2026-02-06T13:01:00", "2026-02-06T13:00:00", "BTCUSDT", "CHOP", "DEFENSE", "GO", "BUY", "0.7", "9", "20", ""],
            ["2026-02-06T13:02:00", "2026-02-06T13:01:00", "BTCUSDT", "TREND", "ATTACK", "NO_GO", "HOLD", "0.0", "0", "11", ""],
        ],
    )
    _write_csv(
        tmp_path / "trades.csv",
        ["ts_iso", "symbol", "side", "price", "qty", "pnl", "event"],
        [
            ["2026-02-06T13:00:10", "BTCUSDT", "BUY", "70000", "0.01", "0", "OPEN"],
            ["2026-02-06T13:00:20", "BTCUSDT", "BUY", "70000", "0.00", "0", "REJECTED"],
        ],
    )

    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    cm = report.conversion_metrics

    assert cm.total_signals == 2
    assert cm.total_opens == 1
    assert cm.total_rejects == 1
    assert cm.conversion_rate == pytest.approx(0.5)
    assert "TREND" in cm.by_regime
    assert "CHOP" in cm.by_regime


def test_kill_switch_activations_count(tmp_path):
    _write_csv(
        tmp_path / "rejects.csv",
        ["ts_iso", "bar_ts_iso", "symbol", "code", "detail"],
        [
            ["2026-02-06T14:00:00", "2026-02-06T13:59:00", "BTCUSDT", "REJECT_KILL_SWITCH", "soft"],
            ["2026-02-06T14:01:00", "2026-02-06T14:00:00", "BTCUSDT", "KILL_SWITCH_DD", "hard"],
            ["2026-02-06T14:02:00", "2026-02-06T14:01:00", "BTCUSDT", "MAX_EXP", "x"],
        ],
    )

    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    assert report.kill_switch_activations == 2


def test_to_markdown_is_readable(tmp_path):
    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    md = AuditPipeline(tmp_path).to_markdown(report)

    assert "# Weekly Audit Report - 2026-W06" in md
    assert "## Conversion Metrics" in md
    assert "## Rejection Breakdown" in md
    assert "## Recommendations" in md


def test_to_json_returns_valid_payload(tmp_path):
    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    raw = AuditPipeline(tmp_path).to_json(report)
    payload = json.loads(raw)

    assert payload["week"] == "2026-W06"
    assert "rejection_breakdown" in payload
    assert "conversion_metrics" in payload


def test_recommendations_non_empty(tmp_path):
    report = AuditPipeline(tmp_path).generate_weekly_report("2026-W06")
    assert isinstance(report.recommendations, list)
    assert len(report.recommendations) >= 1
