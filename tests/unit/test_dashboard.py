from pathlib import Path
import sys
import json

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.dashboard.app import DashboardData, create_app


def _seed_run(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "heartbeat.json").write_text(json.dumps({"ts_iso": "2026-02-07T00:00:00", "risk_level": "NORMAL"}), encoding="utf-8")
    (run_dir / "daemon_state.json").write_text(json.dumps({"equity": 1000.0, "balance": 990.0, "current_dd_pct": 1.0}), encoding="utf-8")
    (run_dir / "trades.csv").write_text(
        "timestamp,symbol,event,side,price,quantity,pnl\n"
        "1,BTCUSDT,OPEN,BUY,50000,0.01,0\n"
        "2,BTCUSDT,CLOSE,SELL,51000,0.01,10\n",
        encoding="utf-8",
    )
    (run_dir / "decisions.csv").write_text("timestamp,symbol,decision\n1,BTCUSDT,GO\n", encoding="utf-8")
    (run_dir / "rejects.csv").write_text("timestamp,code\n1,REJECT_RISK\n2,REJECT_RISK\n", encoding="utf-8")


def test_dashboard_data_readers(tmp_path):
    _seed_run(tmp_path)
    data = DashboardData(tmp_path)

    hb = data.get_heartbeat()
    st = data.get_state()
    trades = data.get_recent_trades(5)
    eq = data.get_equity_curve()
    rej = data.get_rejection_summary()

    assert hb["risk_level"] == "NORMAL"
    assert st["equity"] == 1000.0
    assert len(trades) == 2
    assert len(eq) == 1
    assert rej["REJECT_RISK"] == 2


def test_create_app_requires_flask_if_missing(tmp_path):
    _seed_run(tmp_path)
    try:
        app = create_app(str(tmp_path))
    except RuntimeError as exc:
        assert "Flask is not installed" in str(exc)
        return

    client = app.test_client()
    r = client.get("/api/status")
    assert r.status_code == 200
    payload = r.get_json()
    assert "heartbeat" in payload and "state" in payload
