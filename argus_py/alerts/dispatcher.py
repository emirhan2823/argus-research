from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import httpx


class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertChannel(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"


@dataclass
class AlertConfig:
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook: Optional[str] = None
    email_smtp: Optional[str] = None
    email_to: Optional[str] = None


@dataclass
class Alert:
    level: AlertLevel
    title: str
    message: str
    channels: List[AlertChannel]
    timestamp: float


class AlertDispatcher:
    def __init__(self, config: AlertConfig):
        self.config = config

    async def send(self, alert: Alert) -> dict:
        results: Dict[str, bool] = {}
        for channel in alert.channels:
            if channel == AlertChannel.TELEGRAM:
                results["telegram"] = await self._send_telegram(alert)
            elif channel == AlertChannel.DISCORD:
                results["discord"] = await self._send_discord(alert)
            elif channel == AlertChannel.EMAIL:
                results["email"] = await self._send_email(alert)
        return results

    async def _send_telegram(self, alert: Alert) -> bool:
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        prefix = {"INFO": "[INFO]", "WARNING": "[WARN]", "CRITICAL": "[CRIT]"}[alert.level.value]
        text = f"{prefix} *{alert.title}*\n{alert.message}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": self.config.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            return response.status_code == 200

    async def _send_discord(self, alert: Alert) -> bool:
        if not self.config.discord_webhook:
            return False

        colors = {"INFO": 3447003, "WARNING": 16776960, "CRITICAL": 15158332}
        payload = {
            "embeds": [
                {
                    "title": alert.title,
                    "description": alert.message,
                    "color": colors[alert.level.value],
                }
            ]
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.config.discord_webhook, json=payload)
            return response.status_code in (200, 204)

    async def _send_email(self, alert: Alert) -> bool:
        # SMTP integration intentionally kept as stub for now.
        if not self.config.email_smtp or not self.config.email_to:
            return False
        return False
