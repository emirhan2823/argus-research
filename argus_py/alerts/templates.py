from __future__ import annotations

import time

from .dispatcher import Alert, AlertChannel, AlertLevel


def _channels(channels):
    return channels if channels else [AlertChannel.TELEGRAM]


def alert_trade_executed(symbol: str, side: str, qty: float, price: float, channels=None) -> Alert:
    return Alert(
        level=AlertLevel.INFO,
        title="Trade Executed",
        message=f"{symbol} {side} {qty:.6f} @ {price:.2f}",
        channels=_channels(channels),
        timestamp=time.time(),
    )


def alert_position_closed(symbol: str, pnl: float, channels=None) -> Alert:
    level = AlertLevel.INFO if pnl >= 0 else AlertLevel.WARNING
    return Alert(
        level=level,
        title="Position Closed",
        message=f"{symbol} PnL={pnl:.2f}",
        channels=_channels(channels),
        timestamp=time.time(),
    )


def alert_kill_switch(level: str, reason: str, channels=None) -> Alert:
    return Alert(
        level=AlertLevel.CRITICAL,
        title="Kill-Switch Activated",
        message=f"Level={level} Reason={reason}",
        channels=_channels(channels),
        timestamp=time.time(),
    )


def alert_heartbeat_stale(minutes: int, channels=None) -> Alert:
    return Alert(
        level=AlertLevel.WARNING,
        title="Heartbeat Stale",
        message=f"No heartbeat for {minutes} minutes",
        channels=_channels(channels),
        timestamp=time.time(),
    )


def alert_daily_summary(realized_pnl: float, trades: int, channels=None) -> Alert:
    level = AlertLevel.INFO if realized_pnl >= 0 else AlertLevel.WARNING
    return Alert(
        level=level,
        title="Daily Summary",
        message=f"Trades={trades}, RealizedPnL={realized_pnl:.2f}",
        channels=_channels(channels),
        timestamp=time.time(),
    )
