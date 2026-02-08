from datetime import date
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.reporting.compliance import ComplianceReporter


def _write_trades_csv(path: Path, rows: list[str]) -> None:
    header = "timestamp,symbol,event,side,price,quantity,commission,pnl,position_id,reject_reason\n"
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def test_generate_8949_fifo_with_partial_match(tmp_path):
    trades = tmp_path / "trades.csv"
    _write_trades_csv(
        trades,
        [
            "1704067200,BTCUSDT,OPEN,BUY,100,1.0,0,0,pos1,",
            "1704153600,BTCUSDT,OPEN,BUY,110,1.0,0,0,pos2,",
            "1704844800,BTCUSDT,CLOSE,SELL_TP,120,1.5,0,0,pos3,",
        ],
    )

    reporter = ComplianceReporter(trades)
    lots = reporter.generate_8949(2024)

    assert len(lots) == 2
    assert lots[0].symbol == "BTCUSDT"
    assert abs(lots[0].quantity - 1.0) < 1e-12
    assert abs(lots[0].pnl - 20.0) < 1e-12
    assert lots[0].short_term is True

    assert abs(lots[1].quantity - 0.5) < 1e-12
    assert abs(lots[1].pnl - 5.0) < 1e-12


def test_generate_8949_filters_by_sell_year(tmp_path):
    trades = tmp_path / "trades.csv"
    _write_trades_csv(
        trades,
        [
            "1704067200,ETHUSDT,OPEN,BUY,2000,1.0,0,0,p1,",  # 2024-01-01
            "1735689600,ETHUSDT,CLOSE,SELL,2200,1.0,0,0,p1,",  # 2025-01-01
        ],
    )

    reporter = ComplianceReporter(trades)
    lots_2024 = reporter.generate_8949(2024)
    lots_2025 = reporter.generate_8949(2025)

    assert len(lots_2024) == 0
    assert len(lots_2025) == 1
    assert lots_2025[0].sell_date.year == 2025


def test_generate_pnl_statement_ranges_and_win_rate(tmp_path):
    trades = tmp_path / "trades.csv"
    _write_trades_csv(
        trades,
        [
            "1704067200,BTCUSDT,OPEN,BUY,100,1.0,0,0,a,",
            "1704153600,BTCUSDT,CLOSE,SELL,120,1.0,0,0,a,",  # +20
            "1704240000,BTCUSDT,OPEN,BUY,200,1.0,0,0,b,",
            "1704326400,BTCUSDT,CLOSE,SELL,180,1.0,0,0,b,",  # -20
        ],
    )

    reporter = ComplianceReporter(trades)
    statement = reporter.generate_pnl_statement(date(2024, 1, 1), date(2024, 12, 31))

    assert statement["total_trades"] == 2
    assert abs(statement["realized_pnl"] - 0.0) < 1e-12
    assert abs(statement["short_term_pnl"] - 0.0) < 1e-12
    assert statement["long_term_pnl"] == 0
    assert abs(statement["win_rate"] - 0.5) < 1e-12


def test_commission_is_included_in_cost_basis(tmp_path):
    trades = tmp_path / "trades.csv"
    _write_trades_csv(
        trades,
        [
            "1704067200,BTCUSDT,OPEN,BUY,100,1.0,1.0,0,a,",
            "1704153600,BTCUSDT,CLOSE,SELL,110,1.0,2.0,0,a,",
        ],
    )

    reporter = ComplianceReporter(trades)
    lots = reporter.generate_8949(2024)
    assert len(lots) == 1

    # buy unit cost = 100 + 1 = 101
    # sell unit proceeds = 110 - 2 = 108
    # pnl = 7
    assert abs(lots[0].buy_price - 101.0) < 1e-12
    assert abs(lots[0].sell_price - 108.0) < 1e-12
    assert abs(lots[0].pnl - 7.0) < 1e-12


def test_export_csv_writes_expected_columns(tmp_path):
    trades = tmp_path / "trades.csv"
    _write_trades_csv(
        trades,
        [
            "1704067200,BTCUSDT,OPEN,BUY,100,1.0,0,0,a,",
            "1704153600,BTCUSDT,CLOSE,SELL,120,1.0,0,0,a,",
        ],
    )

    reporter = ComplianceReporter(trades)
    lots = reporter.generate_8949(2024)

    out = tmp_path / "tax.csv"
    reporter.export_csv(lots, out)

    text = out.read_text(encoding="utf-8")
    assert "Symbol,Buy Date,Buy Price,Sell Date,Sell Price,Quantity,P&L,Term" in text
    assert "BTCUSDT" in text
    assert "Short" in text


def test_generate_tax_report_script_runs(tmp_path):
    trades = tmp_path / "trades.csv"
    _write_trades_csv(
        trades,
        [
            "1704067200,BTCUSDT,OPEN,BUY,100,1.0,0,0,a,",
            "1704153600,BTCUSDT,CLOSE,SELL,120,1.0,0,0,a,",
        ],
    )

    output_csv = tmp_path / "report_2024.csv"
    summary_json = tmp_path / "summary.json"

    cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts" / "generate_tax_report.py"),
        str(trades),
        "--year",
        "2024",
        "--output",
        str(output_csv),
        "--statement-json",
        str(summary_json),
    ]

    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert output_csv.exists()
    assert summary_json.exists()
    assert "Generated 8949 CSV" in proc.stdout
