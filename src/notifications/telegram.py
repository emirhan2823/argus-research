"""Telegram signal notifications for paper/live actionable advisories."""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

LOG = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return _utc_now()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class TelegramSignalNotifier:
    conn: sqlite3.Connection | None = None
    enabled: bool = False
    bot_token: str | None = None
    chat_id: str | None = None
    min_confidence: float = 0.60
    dedup_minutes: int = 10
    daily_cap: int = 30
    timeout_seconds: float = 8.0
    _disabled_notice_emitted: bool = field(default=False, init=False, repr=False)
    _memory_log: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def from_env(
        cls,
        *,
        conn: sqlite3.Connection | None,
        enabled: bool,
        min_confidence: float = 0.60,
        dedup_minutes: int = 10,
        daily_cap: int = 30,
    ) -> "TelegramSignalNotifier":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or None
        return cls(
            conn=conn,
            enabled=bool(enabled),
            bot_token=token,
            chat_id=chat_id,
            min_confidence=max(0.0, min(float(min_confidence), 1.0)),
            dedup_minutes=max(1, int(dedup_minutes)),
            daily_cap=max(1, int(daily_cap)),
        )

    @property
    def active(self) -> bool:
        return bool(self.enabled and self.bot_token and self.chat_id)

    def notify_signal(
        self,
        *,
        timestamp: datetime,
        symbol: str,
        action: str,
        confidence: float,
        engine: str,
        regime: str,
        run_dir: str,
        decision_id: int | None = None,
        trade_id: str | None = None,
        size_pct: float | None = None,
        leverage: float | None = None,
        entry_price: float | None = None,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        advisory_message: str | None = None,
    ) -> bool:
        if not self.active:
            self._log_disabled_once()
            return False

        act = str(action).lower()
        conf = float(confidence)
        if act not in {"long", "short"}:
            return False
        if conf < float(self.min_confidence):
            return False

        now_utc = _to_utc(timestamp)
        if self._is_daily_cap_reached(now_utc):
            return False
        if self._is_duplicate(now_utc, symbol=symbol, action=act):
            return False

        message = self._format_message(
            timestamp=now_utc,
            symbol=symbol,
            action=act,
            confidence=conf,
            engine=engine,
            regime=regime,
            run_dir=run_dir,
            decision_id=decision_id,
            trade_id=trade_id,
            size_pct=size_pct,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            advisory_message=advisory_message,
        )

        if not self._send_message(message):
            return False

        self._record_sent(
            now_utc,
            symbol=str(symbol).upper(),
            action=act,
            confidence=conf,
            engine=str(engine),
            regime=str(regime),
            decision_id=decision_id,
            trade_id=trade_id,
            message=message,
        )
        return True

    def _log_disabled_once(self) -> None:
        if self._disabled_notice_emitted:
            return
        self._disabled_notice_emitted = True
        if not self.enabled:
            LOG.info("Telegram notifier disabled (set --telegram-signals to enable).")
            return
        LOG.info("Telegram notifier disabled: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")

    def _is_daily_cap_reached(self, now_utc: datetime) -> bool:
        day_key = now_utc.strftime("%Y-%m-%d")
        if self.conn is not None:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM telegram_notifications WHERE sent_day_utc = ?",
                (day_key,),
            ).fetchone()
            sent_today = int(row[0]) if row else 0
            return sent_today >= self.daily_cap

        sent_today = sum(1 for rec in self._memory_log if rec.get("day") == day_key)
        return sent_today >= self.daily_cap

    def _is_duplicate(self, now_utc: datetime, *, symbol: str, action: str) -> bool:
        dedup_after = now_utc - timedelta(minutes=self.dedup_minutes)
        symbol_key = str(symbol).upper()
        if self.conn is not None:
            row = self.conn.execute(
                """
                SELECT sent_at FROM telegram_notifications
                WHERE symbol = ? AND action = ?
                ORDER BY id DESC LIMIT 1
                """,
                (symbol_key, action),
            ).fetchone()
            if not row:
                return False
            try:
                last_ts = datetime.fromisoformat(str(row[0]))
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                else:
                    last_ts = last_ts.astimezone(timezone.utc)
                return last_ts >= dedup_after
            except Exception:
                return False

        for rec in reversed(self._memory_log):
            if rec.get("symbol") != symbol_key or rec.get("action") != action:
                continue
            ts = rec.get("ts")
            if isinstance(ts, datetime) and ts >= dedup_after:
                return True
            break
        return False

    def _send_message(self, text: str) -> bool:
        assert self.bot_token is not None
        assert self.chat_id is not None
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or not bool(data.get("ok", False)):
                LOG.warning("Telegram send failed: non-ok response")
                return False
            return True
        except Exception as exc:
            LOG.warning("Telegram notification failed: %s", exc)
            return False

    def _record_sent(
        self,
        now_utc: datetime,
        *,
        symbol: str,
        action: str,
        confidence: float,
        engine: str,
        regime: str,
        decision_id: int | None,
        trade_id: str | None,
        message: str,
    ) -> None:
        day_key = now_utc.strftime("%Y-%m-%d")
        dedup_key = f"{symbol}:{action}"
        if self.conn is not None:
            self.conn.execute(
                """
                INSERT INTO telegram_notifications (
                  sent_at, sent_day_utc, symbol, action, confidence, engine, regime,
                  decision_id, trade_id, dedup_key, message_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_utc.isoformat(),
                    day_key,
                    symbol,
                    action,
                    float(confidence),
                    engine,
                    regime,
                    int(decision_id) if decision_id is not None else None,
                    str(trade_id) if trade_id is not None else None,
                    dedup_key,
                    message,
                ),
            )
            self.conn.commit()
            return

        self._memory_log.append(
            {
                "ts": now_utc,
                "day": day_key,
                "symbol": symbol,
                "action": action,
            }
        )

    @staticmethod
    def _fmt_opt(value: float | None, fmt: str = ".4f") -> str:
        if value is None:
            return "n/a"
        return format(float(value), fmt)

    def _format_message(
        self,
        *,
        timestamp: datetime,
        symbol: str,
        action: str,
        confidence: float,
        engine: str,
        regime: str,
        run_dir: str,
        decision_id: int | None,
        trade_id: str | None,
        size_pct: float | None,
        leverage: float | None,
        entry_price: float | None,
        stop_loss_pct: float | None,
        take_profit_pct: float | None,
        advisory_message: str | None,
    ) -> str:
        parts = [
            "ARGUS Actionable Signal",
            f"Entry Time: {timestamp.isoformat()}",
            f"Symbol: {str(symbol).upper()}",
            f"Action: {str(action).upper()}",
            f"Confidence: {confidence:.2f}",
            f"Engine: {engine}",
            f"Regime: {regime}",
            f"Size: {self._fmt_opt(size_pct)}  Leverage: {self._fmt_opt(leverage, '.2f')}",
            f"Entry: {self._fmt_opt(entry_price)}  Stop: {self._fmt_opt(stop_loss_pct)}  Target: {self._fmt_opt(take_profit_pct)}",
            f"Decision ID: {decision_id if decision_id is not None else 'n/a'}",
            f"Trade ID: {trade_id if trade_id else 'n/a'}",
            f"Run Dir: {run_dir}",
            "Disclaimer: paper signal only.",
        ]
        if advisory_message:
            parts.append(f"Advisory: {advisory_message}")
        return "\n".join(parts)
