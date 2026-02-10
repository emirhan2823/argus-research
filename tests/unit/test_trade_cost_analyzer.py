from __future__ import annotations

from pathlib import Path

from argus_py.reporting.trade_cost_analyzer import analyze_trade_costs, write_trade_cost_report


def _write_sample_trades(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ts_iso,symbol,side,price,qty,commission,pnl,event,mark_price,fill_price,slip_applied,spread_applied,asset_class,venue_id,strategy_id",
                "2026-01-01T00:00:00,BTCUSDT,BUY,100.0,1.0,0.10,0.0,OPEN,100.0,100.0,1.5,1.0,crypto,sim,TOPHUNTER_SHORT_V1",
                "2026-01-01T01:00:00,BTCUSDT,SELL,101.0,1.0,0.11,1.0,CLOSE,101.2,101.0,2.0,1.0,crypto,sim,TOPHUNTER_SHORT_V1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_trade_cost_analyzer_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_sample_trades(run_dir / "trades.csv")

    summary = analyze_trade_costs(run_dir)
    assert summary.closed_trades == 1
    assert summary.total_pnl == 1.0
    assert summary.total_commission > 0.0
    assert summary.total_cost > 0.0


def test_trade_cost_report_writes_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_sample_trades(run_dir / "trades.csv")

    out_md = tmp_path / "trade_costs.md"
    out_json = tmp_path / "trade_costs.json"
    write_trade_cost_report(run_dir, out_md, out_json)

    assert out_md.exists()
    assert out_json.exists()
