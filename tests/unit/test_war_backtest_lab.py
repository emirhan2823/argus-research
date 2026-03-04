from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from Scripts import war_backtest_lab as lab


def test_scenario_yaml_parsing_default_file() -> None:
    path = Path("Scripts/scenarios/backtest_scenarios.yaml")
    presets = lab.load_scenario_presets(path)

    assert "bull_2024" in presets
    assert "luna_crash_2022" in presets
    assert "bear_crash_2022" in presets
    assert "full_2018_to_now" in presets
    assert presets["full_2018_to_now"].end is None
    assert presets["bull_2024"].timeframe == "1h"
    assert len(presets["bull_2024"].assets) >= 1


def test_month_slicing_correctness() -> None:
    slices = lab.generate_month_slices(start=lab.date(2022, 5, 10), end=lab.date(2022, 7, 2))
    assert [item.label for item in slices] == ["2022-05", "2022-06", "2022-07"]
    assert slices[0].start.isoformat() == "2022-05-10T00:00:00+00:00"
    assert slices[0].end.isoformat() == "2022-05-31T23:59:00+00:00"
    assert slices[-1].start.isoformat() == "2022-07-01T00:00:00+00:00"
    assert slices[-1].end.isoformat() == "2022-07-02T23:59:00+00:00"


def test_aggregation_math_sanity_toy_dataset() -> None:
    trade_rows = [
        {
            "trade_id": "t1",
            "exit_time": "2024-01-01T01:00:00+00:00",
            "net_pnl_pct": 0.10,
            "engine": "TITAN",
            "regime_at_entry": "TRENDING",
        },
        {
            "trade_id": "t2",
            "exit_time": "2024-01-01T02:00:00+00:00",
            "net_pnl_pct": -0.05,
            "engine": "TITAN",
            "regime_at_entry": "TRENDING",
        },
        {
            "trade_id": "t3",
            "exit_time": "2024-01-01T03:00:00+00:00",
            "net_pnl_pct": 0.02,
            "engine": "HYDRA",
            "regime_at_entry": "RANGING",
        },
    ]
    metrics = lab.aggregate_trade_metrics(trade_rows)

    expected_total_return = (1.10 * 0.95 * 1.02) - 1.0
    assert metrics["trades"] == 3
    assert metrics["win_rate"] == 2 / 3
    assert metrics["total_return"] == expected_total_return
    assert metrics["max_drawdown"] == pytest.approx(-0.05, abs=1e-12)
    assert metrics["best_engine"] == "TITAN"
    assert metrics["regime_dominance"] == "TRENDING"
    assert metrics["longest_losing_streak"] == 1
    assert metrics["max_consecutive_loss_pct_sum"] == 0.05


def test_determinism_same_inputs_same_outputs() -> None:
    trade_rows = [
        {
            "trade_id": "t1",
            "exit_time": "2025-01-01T01:00:00+00:00",
            "net_pnl_pct": 0.01,
            "engine": "TITAN",
            "regime_at_entry": "TRENDING",
        },
        {
            "trade_id": "t2",
            "exit_time": "2025-01-01T02:00:00+00:00",
            "net_pnl_pct": -0.02,
            "engine": "HYDRA",
            "regime_at_entry": "RANGING",
        },
    ]
    metrics_a = lab.aggregate_trade_metrics(trade_rows)
    metrics_b = lab.aggregate_trade_metrics(trade_rows)
    curves_a = lab.build_curve_rows(scenario_id="s", trade_rows=trade_rows)
    curves_b = lab.build_curve_rows(scenario_id="s", trade_rows=trade_rows)

    assert metrics_a == metrics_b
    assert curves_a == curves_b


def test_bear_scenario_short_edge_not_zero() -> None:
    trade_rows = [
        {
            "trade_id": "s1",
            "side": "short",
            "net_pnl_pct": 0.04,
            "regime_at_entry": "CRISIS",
            "scenario": "bear_2022__orion_on",
            "exit_time": "2022-06-01T01:00:00+00:00",
        },
        {
            "trade_id": "s2",
            "side": "short",
            "net_pnl_pct": 0.02,
            "regime_at_entry": "CRISIS",
            "scenario": "bear_2022__orion_on",
            "exit_time": "2022-06-01T02:00:00+00:00",
        },
        {
            "trade_id": "l1",
            "side": "long",
            "net_pnl_pct": -0.03,
            "regime_at_entry": "CRISIS",
            "scenario": "bear_2022__orion_on",
            "exit_time": "2022-06-01T03:00:00+00:00",
        },
    ]
    short_ret, long_ret, edge = lab._bear_edge_metrics(trade_rows)
    assert short_ret > 0.0
    assert long_ret < 0.0
    assert edge > 0.0


def _seed_fake_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE decisions (
          decision_id TEXT PRIMARY KEY,
          timestamp TEXT,
          symbol TEXT,
          action TEXT,
          engine TEXT,
          reason TEXT,
          status TEXT,
          confidence REAL,
          gate_results_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE trades (
          trade_id TEXT PRIMARY KEY,
          symbol TEXT,
          side TEXT,
          engine TEXT,
          entry_time TEXT,
          exit_time TEXT,
          entry_price REAL,
          exit_price REAL,
          hold_minutes INTEGER,
          pnl_pct REAL,
          net_pnl_pct REAL,
          confidence REAL,
          regime_at_entry TEXT,
          regime_at_exit TEXT,
          stop_distance REAL,
          size REAL,
          leverage REAL
        )
        """
    )
    gate = {
        "features_snapshot": {
            "regime": "TRENDING",
            "atr_14_pct": 0.012,
            "adx_14": 24.0,
            "volume_ratio": 1.20,
        }
    }
    conn.execute(
        """
        INSERT INTO decisions(decision_id, timestamp, symbol, action, engine, reason, status, confidence, gate_results_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "d1",
            "2024-01-01T00:00:00+00:00",
            "BTCUSDT",
            "long",
            "TITAN",
            "advisory_signal_sent",
            "executed",
            0.72,
            json.dumps(gate),
        ),
    )
    conn.execute(
        """
        INSERT INTO trades(trade_id, symbol, side, engine, entry_time, exit_time, entry_price, exit_price,
                           hold_minutes, pnl_pct, net_pnl_pct, confidence, regime_at_entry, regime_at_exit, stop_distance, size, leverage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "t1",
            "BTCUSDT",
            "long",
            "TITAN",
            "2024-01-01T00:00:00+00:00",
            "2024-01-01T01:00:00+00:00",
            42000.0,
            42100.0,
            60,
            0.0023,
            0.0023,
            0.72,
            "TRENDING",
            "TRENDING",
            0.01,
            0.04,
            1.0,
        ),
    )
    conn.commit()
    conn.close()


def test_backtest_runner_smoke_small_range(monkeypatch, tmp_path: Path) -> None:
    scenarios_yaml = tmp_path / "scenarios.yaml"
    scenarios_yaml.write_text(
        "\n".join(
            [
                "defaults:",
                "  assets: [BTCUSDT]",
                "  timeframe: 1h",
                "  risk_profile: normal",
                "  orion: off",
                "scenarios:",
                "  smoke_case:",
                "    start: 2024-01-01",
                "    end: 2024-01-31",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def _fake_coverage(**_: object) -> dict[str, int]:
        return {"BTCUSDT": 8}

    def _fake_runner(**kwargs: object) -> tuple[str, str]:
        db_path = Path(str(kwargs["db_path"]))
        _seed_fake_db(db_path)
        return "COMPLETED", "ok"

    monkeypatch.setattr(lab, "_collect_month_coverage", _fake_coverage)
    monkeypatch.setattr(lab, "_run_backtest_slice", _fake_runner)

    output_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    rc = lab.main(
        [
            "--scenario",
            "smoke_case",
            "--orion",
            "off",
            "--scenarios-file",
            str(scenarios_yaml),
            "--output-dir",
            str(output_dir),
            "--reports-dir",
            str(reports_dir),
            "--cache-root",
            str(tmp_path / "cache"),
            "--max-cycles-per-scenario",
            "5",
        ]
    )
    assert rc == 0

    assert (reports_dir / "WAR_BACKTEST_SCENARIO_SUMMARY.md").exists()
    assert (reports_dir / "WAR_BACKTEST_SCENARIO_SUMMARY.csv").exists()
    assert (reports_dir / "WAR_BACKTEST_ENGINE_BREAKDOWN.csv").exists()
    assert (reports_dir / "WAR_BACKTEST_REGIME_BREAKDOWN.csv").exists()
    assert (reports_dir / "WAR_BACKTEST_EQUITY_CURVE.csv").exists()
    assert (reports_dir / "WAR_BACKTEST_DRAWDOWN_CURVE.csv").exists()
    assert (reports_dir / "WAR_BACKTEST_DATA_COVERAGE.md").exists()
    assert (reports_dir / "LONG_SHORT_BREAKDOWN.csv").exists()
    assert (reports_dir / "BEAR_EDGE_REPORT.md").exists()
    assert (reports_dir / "EARLY_ENTRY_REPORT.md").exists()
    assert (reports_dir / "FLIP_COMPARISON_REPORT.md").exists()

    summary_lines = (reports_dir / "WAR_BACKTEST_SCENARIO_SUMMARY.csv").read_text(encoding="utf-8").splitlines()
    assert "long_total_return" in summary_lines[0]
    assert "short_total_return" in summary_lines[0]
    assert "bear_short_edge_ratio" in summary_lines[0]

    trade_json_files = sorted((output_dir / "smoke_case__orion_off" / "2024-01" / "trades").glob("*.json"))
    assert trade_json_files


class _FakeReplayLoader:
    def __init__(self) -> None:
        timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=12, freq="1h")
        closes = [100.0 + float(i * 2) for i in range(len(timestamps))]
        self._frame = pd.DataFrame({"timestamp": timestamps, "close": closes})

    def load_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        start: str | None = None,
        end: str | None = None,
        *,
        verify: bool = False,
    ) -> pd.DataFrame:
        _ = (symbol, interval, verify)
        frame = self._frame.copy()
        if start is not None:
            start_ts = pd.to_datetime(start, utc=True)
            frame = frame[frame["timestamp"] >= start_ts]
        if end is not None:
            end_ts = pd.to_datetime(end, utc=True)
            frame = frame[frame["timestamp"] <= end_ts]
        return frame.reset_index(drop=True)


def test_early_entry_comparison_detects_lagging_entry() -> None:
    scenario_trade_rows = {
        "scenario_a": [
            {
                "scenario": "scenario_a",
                "trade_id": "t1",
                "symbol": "BTCUSDT",
                "side": "long",
                "engine": "TITAN",
                "entry_time": "2024-01-01T05:00:00+00:00",
                "exit_time": "2024-01-01T08:00:00+00:00",
                "entry_price": 110.0,
                "exit_price": 116.0,
                "pnl_pct": 0.0545454545,
                "net_pnl_pct": 0.0545454545,
            }
        ]
    }
    scenario_timeframes = {"scenario_a": "1h"}
    loader = _FakeReplayLoader()

    rows_a, engines_a = lab._build_early_entry_comparison_rows(
        scenario_trade_rows=scenario_trade_rows,
        scenario_timeframes=scenario_timeframes,
        loader=loader,
    )
    rows_b, engines_b = lab._build_early_entry_comparison_rows(
        scenario_trade_rows=scenario_trade_rows,
        scenario_timeframes=scenario_timeframes,
        loader=loader,
    )

    assert rows_a == rows_b
    assert engines_a == engines_b
    assert rows_a[0]["label"] == "LAGGING_ENTRY_ENGINE"
    assert rows_a[0]["early_total_return"] > rows_a[0]["original_total_return"]


def test_flip_comparison_detects_inverted_direction() -> None:
    scenario_trade_rows = {
        "scenario_flip": [
            {
                "scenario": "scenario_flip",
                "trade_id": "t1",
                "symbol": "BTCUSDT",
                "side": "long",
                "engine": "HYDRA",
                "entry_time": "2024-01-01T00:00:00+00:00",
                "exit_time": "2024-01-01T01:00:00+00:00",
                "entry_price": 100.0,
                "exit_price": 90.0,
                "pnl_pct": -0.10,
                "net_pnl_pct": -0.10,
            }
        ]
    }

    rows_a, engines_a = lab._build_flip_comparison_rows(scenario_trade_rows=scenario_trade_rows)
    rows_b, engines_b = lab._build_flip_comparison_rows(scenario_trade_rows=scenario_trade_rows)

    assert rows_a == rows_b
    assert engines_a == engines_b
    assert rows_a[0]["label"] == "DIRECTIONALLY_INVERTED_ENGINE"
    assert rows_a[0]["flipped_total_return"] > rows_a[0]["original_total_return"]
