import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import json

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.bot.telegram_bot import ArgusTelegramBot


class _FakeUser:
    def __init__(self, uid: int):
        self.id = uid


class _FakeMessage:
    def __init__(self):
        self.calls = []

    async def reply_text(self, text, **kwargs):
        self.calls.append((text, kwargs))


class _FakeUpdate:
    def __init__(self, uid: int):
        self.effective_user = _FakeUser(uid)
        self.message = _FakeMessage()


class _FakeCtx:
    def __init__(self, args=None):
        self.args = args or []


def _run(coro):
    return asyncio.run(coro)


def _write_sample_files(run_dir: Path):
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    t0 = now_ts - 3600
    t1 = now_ts - 1800
    t2 = now_ts - 1200
    t3 = now_ts - 600

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "daemon_state.json").write_text(
        json.dumps({"equity": 1234.56, "balance": 1200.0, "current_dd_pct": 1.2, "positions": ["p1"]}),
        encoding="utf-8",
    )
    (run_dir / "heartbeat.json").write_text(
        json.dumps({"equity": 1300.0, "dd_pct": 2.5}),
        encoding="utf-8",
    )
    (run_dir / "trades.csv").write_text(
        "timestamp,symbol,event,side,price,quantity,commission,pnl,position_id,reject_reason\n"
        f"{t0},BTCUSDT,OPEN,BUY,42000,0.01,0.1,0,p1,\n"
        f"{t1},BTCUSDT,CLOSE,SELL_TP,43000,0.01,0.1,9.5,p1,\n"
        f"{t2},ETHUSDT,OPEN,BUY,2500,0.20,0.1,0,p2,\n"
        f"{t3},ETHUSDT,CLOSE,SELL_SL,2450,0.20,0.1,-5,p2,\n",
        encoding="utf-8",
    )


def test_status_replies_for_allowed_user(tmp_path):
    _write_sample_files(tmp_path)
    bot = ArgusTelegramBot(token="x", run_dir=tmp_path, allowed_users=[42])

    update = _FakeUpdate(42)
    _run(bot.cmd_status(update, _FakeCtx()))

    assert len(update.message.calls) == 1
    text, kwargs = update.message.calls[0]
    assert "Argus Status" in text
    assert "Equity: $1300.00" in text
    assert "Kill-Switch: NORMAL" in text
    assert "Open Positions: 1" in text
    assert kwargs.get("parse_mode") == "Markdown"


def test_unauthorized_user_gets_no_response(tmp_path):
    _write_sample_files(tmp_path)
    bot = ArgusTelegramBot(token="x", run_dir=tmp_path, allowed_users=[42])

    update = _FakeUpdate(999)
    _run(bot.cmd_status(update, _FakeCtx()))

    assert update.message.calls == []


def test_trades_and_balance_commands(tmp_path):
    _write_sample_files(tmp_path)
    bot = ArgusTelegramBot(token="x", run_dir=tmp_path, allowed_users=[42])

    update_trades = _FakeUpdate(42)
    _run(bot.cmd_trades(update_trades, _FakeCtx()))
    assert "Recent Trades" in update_trades.message.calls[0][0]
    assert "SELL_SL" in update_trades.message.calls[0][0]

    update_balance = _FakeUpdate(42)
    _run(bot.cmd_balance(update_balance, _FakeCtx()))
    assert "Balance: $1200.00" in update_balance.message.calls[0][0]


def test_killswitch_command_changes_state(tmp_path):
    _write_sample_files(tmp_path)
    bot = ArgusTelegramBot(token="x", run_dir=tmp_path, allowed_users=[42])

    update_soft = _FakeUpdate(42)
    _run(bot.cmd_killswitch(update_soft, _FakeCtx(args=["soft"])))
    payload = json.loads((tmp_path / "kill_switch_state.json").read_text(encoding="utf-8"))
    assert payload["level"] == "SOFT"

    update_off = _FakeUpdate(42)
    _run(bot.cmd_killswitch(update_off, _FakeCtx(args=["off"])))
    payload2 = json.loads((tmp_path / "kill_switch_state.json").read_text(encoding="utf-8"))
    assert payload2["level"] == "NORMAL"


def test_report_command_outputs_summary(tmp_path):
    _write_sample_files(tmp_path)
    bot = ArgusTelegramBot(token="x", run_dir=tmp_path, allowed_users=[42])

    update = _FakeUpdate(42)
    _run(bot.cmd_report(update, _FakeCtx()))

    text = update.message.calls[0][0]
    assert "Argus Report" in text
    assert "Weekly: net" in text
    assert "Top Symbols" in text
