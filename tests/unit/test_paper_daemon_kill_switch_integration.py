import json
from argparse import Namespace
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.paper_daemon import DEFAULT_CONFIG, PaperDaemon
from argus_py.broker.paper import TradeFill
from argus_py.data.market_state import Bar
from argus_py.risk.kill_switch import RiskLevel


def _cfg(tmp_path: Path):
    cfg = DEFAULT_CONFIG.copy()
    cfg["run_dir"] = tmp_path
    cfg["daemon_id"] = "TEST"
    cfg["args"] = Namespace(symbol=cfg["symbol"], min_adx=cfg["min_adx"])
    cfg["run_id"] = "test_run"
    return cfg


def _bar(ts: float = 1700000000.0):
    return Bar(timestamp=ts, open=100.0, high=101.0, low=99.0, close=100.0, volume=1.0)


def test_kill_switch_state_persists_across_restarts(tmp_path):
    daemon_1 = PaperDaemon(_cfg(tmp_path))
    daemon_1.kill_switch.activate(RiskLevel.SOFT, "test")
    daemon_1._persist_kill_switch()

    daemon_2 = PaperDaemon(_cfg(tmp_path))
    assert daemon_2.kill_switch.get_level() == RiskLevel.SOFT


def test_soft_level_blocks_new_trades_and_writes_reject(tmp_path):
    daemon = PaperDaemon(_cfg(tmp_path))
    daemon.kill_switch.activate(RiskLevel.SOFT, "manual soft")

    blocked = daemon._apply_kill_switch_guard(_bar(), daily_pnl_pct=0.0, current_dd_pct=0.0)

    assert blocked is True
    rejects_csv = (tmp_path / "rejects.csv").read_text(encoding="utf-8")
    assert "REJECT_KILL_SWITCH" in rejects_csv


def test_hard_level_calls_broker_close_all(tmp_path):
    daemon = PaperDaemon(_cfg(tmp_path))

    class FakeBroker:
        def __init__(self):
            self.details = {"BTCUSDT": object()}
            self.closed = False
            self.equity = 1000.0
            self.balance = 1000.0
            self.unrealized_pnl = 0.0

        def close_all(self, timestamp, price_dict):
            self.closed = True
            return [
                TradeFill(
                    timestamp=timestamp,
                    symbol="BTCUSDT",
                    side="SELL",
                    price=100.0,
                    quantity=0.01,
                    commission=0.0,
                    pnl=-1.0,
                    event="CLOSE",
                )
            ]

    fake = FakeBroker()
    daemon.broker = fake

    blocked = daemon._apply_kill_switch_guard(_bar(), daily_pnl_pct=-6.0, current_dd_pct=-1.0)

    assert blocked is True
    assert fake.closed is True


def test_heartbeat_contains_risk_level(tmp_path):
    daemon = PaperDaemon(_cfg(tmp_path))
    daemon.kill_switch.activate(RiskLevel.HARD, "test")

    daemon.update_heartbeat(last_bar=_bar())

    payload = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert payload["risk_level"] == "HARD"
