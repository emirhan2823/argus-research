from __future__ import annotations

from pathlib import Path

from argus_py.reporting.pnl_attribution import compute_pnl_attribution, write_pnl_attribution_report


def _write_trades(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ts_iso,symbol,side,price,qty,commission,pnl,event,mark_price,fill_price,slip_applied,spread_applied,asset_class,venue_id,strategy_id",
                "2026-01-01T00:00:00Z,BTCUSDT,BUY,100,1,0.1,0.0,ENTRY,100,100,0,0,crypto,sim,COUNCIL",
                "2026-01-01T01:00:00Z,BTCUSDT,SELL,102,1,0.1,2.0,TP,102,102,0,0,crypto,sim,COUNCIL",
                "2026-01-01T02:00:00Z,ETHUSDT,BUY,50,1,0.1,-1.0,STOP,50,50,0,0,crypto,sim,TOPHUNTER",
                "2026-01-01T03:00:00Z,AAPL,BUY,200,1,0.0,1.5,TP,200,200,0,0,stock,stock_sim,COUNCIL",
                "2026-01-01T04:00:00Z,AAPL,BUY,200,0,0.0,0.0,REJECTED,0,0,0,0,stock,stock_sim,COUNCIL",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_compute_pnl_attribution_groups_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _write_trades(run_dir / "trades.csv")

    report = compute_pnl_attribution(run_dir)
    assert report.total_closed_trades == 3
    assert report.total_realized_pnl == 2.5
    assert report.by_strategy[0].key in {"COUNCIL", "TOPHUNTER"}


def test_write_pnl_attribution_report_outputs_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _write_trades(run_dir / "trades.csv")
    report = compute_pnl_attribution(run_dir)
    out_md = tmp_path / "rep.md"
    out_json = tmp_path / "rep.json"
    write_pnl_attribution_report(report, out_md=out_md, out_json=out_json)
    assert out_md.exists()
    assert out_json.exists()
    assert "PnL Attribution" in out_md.read_text(encoding="utf-8")
