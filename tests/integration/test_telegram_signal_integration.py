from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.notifications.telegram import TelegramSignalNotifier
from src.v25.db.migrations import run_v25_migrations


def test_telegram_notifier_env_and_send_integration(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "telegram_integration.db"
    conn = run_v25_migrations(str(db_path))

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat456")

    notifier = TelegramSignalNotifier.from_env(
        conn=conn,
        enabled=True,
        min_confidence=0.60,
        dedup_minutes=10,
        daily_cap=30,
    )

    ok_response = MagicMock()
    ok_response.raise_for_status.return_value = None
    ok_response.json.return_value = {"ok": True}

    ts = datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc)

    with patch("src.notifications.telegram.requests.post", return_value=ok_response) as mock_post:
        sent = notifier.notify_signal(
            timestamp=ts,
            symbol="BTCUSDT",
            action="long",
            confidence=0.77,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
            decision_id=10,
            entry_price=51234.5,
            stop_loss_pct=0.012,
            take_profit_pct=0.024,
            advisory_message="mock advisory",
        )

    assert sent is True
    assert mock_post.call_count == 1

    sent_payload = mock_post.call_args.kwargs.get("json", {})
    text = str(sent_payload.get("text", ""))
    assert "BTCUSDT" in text
    assert "LONG" in text
    assert "0.77" in text
    assert "TITAN" in text
    assert "paper signal only" in text.lower()

    row = conn.execute("SELECT COUNT(*) FROM telegram_notifications").fetchone()
    assert row is not None and int(row[0]) == 1
    conn.close()
