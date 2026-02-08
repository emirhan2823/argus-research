from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.alerts.dispatcher import Alert, AlertChannel, AlertConfig, AlertDispatcher, AlertLevel
from argus_py.alerts.templates import (
    alert_daily_summary,
    alert_heartbeat_stale,
    alert_kill_switch,
    alert_position_closed,
    alert_trade_executed,
)


@pytest.mark.anyio
async def test_send_telegram_missing_config_returns_false():
    disp = AlertDispatcher(AlertConfig())
    alert = Alert(
        level=AlertLevel.INFO,
        title="x",
        message="y",
        channels=[AlertChannel.TELEGRAM],
        timestamp=0,
    )
    out = await disp.send(alert)
    assert out["telegram"] is False


@pytest.mark.anyio
async def test_send_discord_missing_config_returns_false():
    disp = AlertDispatcher(AlertConfig())
    alert = Alert(
        level=AlertLevel.WARNING,
        title="x",
        message="y",
        channels=[AlertChannel.DISCORD],
        timestamp=0,
    )
    out = await disp.send(alert)
    assert out["discord"] is False


@pytest.mark.anyio
async def test_send_telegram_and_discord_mocked(monkeypatch):
    disp = AlertDispatcher(
        AlertConfig(
            telegram_bot_token="tkn",
            telegram_chat_id="1",
            discord_webhook="https://example.com/webhook",
        )
    )

    async def ok_telegram(_):
        return True

    async def ok_discord(_):
        return True

    monkeypatch.setattr(disp, "_send_telegram", ok_telegram)
    monkeypatch.setattr(disp, "_send_discord", ok_discord)

    alert = Alert(
        level=AlertLevel.CRITICAL,
        title="critical",
        message="boom",
        channels=[AlertChannel.TELEGRAM, AlertChannel.DISCORD],
        timestamp=1,
    )
    out = await disp.send(alert)
    assert out == {"telegram": True, "discord": True}


def test_templates_emit_expected_levels():
    a1 = alert_trade_executed("BTCUSDT", "BUY", 0.01, 50000)
    a2 = alert_position_closed("BTCUSDT", -10)
    a3 = alert_kill_switch("HARD", "dd")
    a4 = alert_heartbeat_stale(6)
    a5 = alert_daily_summary(12.0, 7)

    assert a1.level == AlertLevel.INFO
    assert a2.level == AlertLevel.WARNING
    assert a3.level == AlertLevel.CRITICAL
    assert a4.level == AlertLevel.WARNING
    assert a5.level == AlertLevel.INFO
