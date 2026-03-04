from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from src.reporting.trade_reporting import TradeReportManager


def _init_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE trades (
          trade_id TEXT PRIMARY KEY,
          symbol TEXT NOT NULL,
          side TEXT NOT NULL,
          engine TEXT NOT NULL,
          entry_time TEXT NOT NULL,
          exit_time TEXT,
          hold_minutes INTEGER,
          size REAL,
          entry_price REAL,
          exit_price REAL,
          pnl_pct REAL,
          net_pnl_pct REAL,
          confidence REAL,
          regime_at_entry TEXT,
          regime_at_exit TEXT,
          stop_distance REAL,
          reason_entry TEXT,
          reason_exit TEXT,
          features_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def _insert_trade(conn: sqlite3.Connection, *, trade_id: str, net_pnl_pct: float, engine: str = "TITAN") -> None:
    features = {
        "atr_14_pct": 0.012,
        "volume_ratio": 1.35,
        "trailing_activated": net_pnl_pct > 0.0,
        "trailing_exit": False,
        "position_size_pct": 0.04,
        "leverage": 2.0,
    }
    conn.execute(
        """
        INSERT INTO trades (
          trade_id, symbol, side, engine, entry_time, exit_time, hold_minutes,
          size, entry_price, exit_price, pnl_pct, net_pnl_pct, confidence,
          regime_at_entry, regime_at_exit, stop_distance, reason_entry, reason_exit, features_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            "BTCUSDT",
            "long",
            engine,
            "2026-02-20T10:00:00+00:00",
            "2026-02-20T10:30:00+00:00",
            30,
            0.04,
            42000.0,
            42300.0,
            net_pnl_pct,
            net_pnl_pct,
            0.72,
            "TRENDING",
            "TRENDING",
            0.01,
            "backtest_sim_entry",
            "time_exit_backtest_sim",
            json.dumps(features),
        ),
    )
    conn.commit()


def test_trade_json_creation_and_index_append(tmp_path) -> None:
    conn = _init_conn()
    _insert_trade(conn, trade_id="t-1", net_pnl_pct=0.0084, engine="TITAN")

    manager = TradeReportManager(
        conn=conn,
        run_dir=tmp_path,
        run_id="run-123",
        run_started_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
    )
    records = manager.sync_closed_trades()

    assert len(records) == 1
    trade_path = tmp_path / "run-123" / "trades" / "t-1.json"
    assert trade_path.exists()
    payload = json.loads(trade_path.read_text(encoding="utf-8"))
    assert payload["symbol"] == "BTCUSDT"
    assert payload["engine"] == "TITAN"
    assert isinstance(payload["what_went_right"], str)
    assert isinstance(payload["what_went_wrong"], str)
    assert isinstance(payload["improvement_suggestion"], str)

    index_path = tmp_path / "run-123" / "trades_index.csv"
    lines = index_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("trade_id,symbol,engine,side,entry_time,exit_time,net_pnl_pct,max_drawdown,regime")
    assert lines[1].startswith("t-1,BTCUSDT,TITAN,long,")
    conn.close()


def test_daily_report_update_after_new_close(tmp_path) -> None:
    conn = _init_conn()
    _insert_trade(conn, trade_id="t-1", net_pnl_pct=0.0080, engine="TITAN")
    _insert_trade(conn, trade_id="t-2", net_pnl_pct=-0.0030, engine="HYDRA")

    manager = TradeReportManager(
        conn=conn,
        run_dir=tmp_path,
        run_id="run-abc",
        run_started_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
    )
    records = manager.sync_closed_trades()
    assert len(records) == 2

    day_report = tmp_path / "run-abc" / "daily_reports" / "2026-02-20.md"
    assert day_report.exists()
    text = day_report.read_text(encoding="utf-8")
    assert "## Daily Report — 2026-02-20" in text
    assert "Trades: 2" in text
    assert "Win rate:" in text
    assert "Total return:" in text
    assert "Best engine:" in text
    assert "Worst engine:" in text
    assert "Observations:" in text

    month_report = tmp_path / "run-abc" / "monthly_reports" / "2026-02.md"
    assert month_report.exists()
    conn.close()
