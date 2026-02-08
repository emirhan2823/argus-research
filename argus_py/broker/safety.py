from __future__ import annotations

from typing import List, Tuple

from .live import LiveConfig


LIVE_TRADING_CHECKLIST: List[str] = [
    "testnet=True verified working",
    "max_order_value set to acceptable loss",
    "max_daily_volume set to daily risk budget",
    "require_confirmation=True for initial testing",
    "Kill-switch integration verified",
    "API keys have trade permission only (no withdraw)",
    "IP whitelist configured on Binance",
    "Testnet paper run for 7+ days without issues",
]


def validate_live_config(config: LiveConfig) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    if not config.api_key:
        issues.append("api_key missing")
    if not config.api_secret:
        issues.append("api_secret missing")
    if config.max_order_value <= 0:
        issues.append("max_order_value must be > 0")
    if config.max_daily_volume <= 0:
        issues.append("max_daily_volume must be > 0")

    # Production guardrail: confirmation should be on when first enabling live.
    if not config.testnet and not config.require_confirmation:
        issues.append("require_confirmation should be True for initial live rollout")

    return (len(issues) == 0, issues)
