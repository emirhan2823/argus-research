from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.notifications.telegram import TelegramSignalNotifier


def _init_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE telegram_notifications (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sent_at TEXT NOT NULL,
          sent_day_utc TEXT NOT NULL,
          symbol TEXT NOT NULL,
          action TEXT NOT NULL,
          confidence REAL,
          engine TEXT,
          regime TEXT,
          decision_id INTEGER,
          trade_id TEXT,
          dedup_key TEXT NOT NULL,
          message_text TEXT,
          created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def test_telegram_dedup_logic() -> None:
    conn = _init_conn()
    notifier = TelegramSignalNotifier(
        conn=conn,
        enabled=True,
        bot_token="token",
        chat_id="chat",
        dedup_minutes=10,
        daily_cap=30,
    )

    ok_resp = MagicMock()
    ok_resp.raise_for_status.return_value = None
    ok_resp.json.return_value = {"ok": True}

    t0 = datetime(2026, 2, 21, 10, 0, tzinfo=timezone.utc)

    with patch("src.notifications.telegram.requests.post", return_value=ok_resp) as mock_post:
        assert notifier.notify_signal(
            timestamp=t0,
            symbol="BTCUSDT",
            action="long",
            confidence=0.75,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
            decision_id=1,
        )
        # Duplicate within 10m should be suppressed
        assert not notifier.notify_signal(
            timestamp=t0 + timedelta(minutes=5),
            symbol="BTCUSDT",
            action="long",
            confidence=0.8,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
            decision_id=2,
        )
        # Beyond dedup window should send
        assert notifier.notify_signal(
            timestamp=t0 + timedelta(minutes=11),
            symbol="BTCUSDT",
            action="long",
            confidence=0.82,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
            decision_id=3,
        )

    assert mock_post.call_count == 2
    conn.close()


def test_telegram_daily_cap() -> None:
    conn = _init_conn()
    notifier = TelegramSignalNotifier(
        conn=conn,
        enabled=True,
        bot_token="token",
        chat_id="chat",
        dedup_minutes=1,
        daily_cap=2,
    )

    ok_resp = MagicMock()
    ok_resp.raise_for_status.return_value = None
    ok_resp.json.return_value = {"ok": True}

    t0 = datetime(2026, 2, 21, 0, 0, tzinfo=timezone.utc)

    with patch("src.notifications.telegram.requests.post", return_value=ok_resp) as mock_post:
        assert notifier.notify_signal(
            timestamp=t0,
            symbol="BTCUSDT",
            action="long",
            confidence=0.7,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
        )
        assert notifier.notify_signal(
            timestamp=t0 + timedelta(minutes=2),
            symbol="ETHUSDT",
            action="short",
            confidence=0.71,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
        )
        # cap reached
        assert not notifier.notify_signal(
            timestamp=t0 + timedelta(minutes=4),
            symbol="SOLUSDT",
            action="long",
            confidence=0.9,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
        )
        # new UTC day resets cap
        assert notifier.notify_signal(
            timestamp=t0 + timedelta(days=1, minutes=1),
            symbol="SOLUSDT",
            action="long",
            confidence=0.9,
            engine="TITAN",
            regime="TRENDING",
            run_dir="runs/paper_v2",
        )

    assert mock_post.call_count == 3
    conn.close()
