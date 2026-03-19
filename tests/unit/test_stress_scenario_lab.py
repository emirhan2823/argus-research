from __future__ import annotations

from pathlib import Path

from argus_py.lab.stress_scenario_lab import run_stress_scenario_lab, write_stress_report


def _write_trades(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ts_iso,symbol,side,price,qty,commission,pnl,event,mark_price,fill_price,slip_applied,spread_applied,asset_class,venue_id,strategy_id",
                "a,BTCUSDT,BUY,100,1,0.0,1.2,TP,0,0,0,0,crypto,sim,COUNCIL",
                "b,BTCUSDT,BUY,100,1,0.0,-0.8,STOP,0,0,0,0,crypto,sim,COUNCIL",
                "c,BTCUSDT,BUY,100,1,0.0,0.4,TP,0,0,0,0,crypto,sim,COUNCIL",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_stress_scenario_lab_returns_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _write_trades(run_dir / "trades.csv")
    report = run_stress_scenario_lab(run_dir)
    assert len(report.scenarios) >= 3
    names = {s.name for s in report.scenarios}
    assert "baseline" in names
    assert "fee_slippage_x2" in names


def test_write_stress_report_outputs_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _write_trades(run_dir / "trades.csv")
    report = run_stress_scenario_lab(run_dir, scenarios=["baseline"])
    out_md = tmp_path / "stress.md"
    out_json = tmp_path / "stress.json"
    write_stress_report(report, out_md=out_md, out_json=out_json)
    assert out_md.exists()
    assert out_json.exists()
    assert "Stress Scenario Lab" in out_md.read_text(encoding="utf-8")
