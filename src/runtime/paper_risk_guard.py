"""Stage-2C Paper-Only Risk Safety Layer.

Provides runtime safety checks for paper/demo modes:
- Daily loss cap
- Max trades per day
- Overtrade cooldown
- Drawdown-triggered position size reduction

All checks are paper-only. Live trading logic is untouched.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any

_LOG = logging.getLogger("argus.paper_risk")


@dataclass
class PaperRiskGuard:
    """Runtime safety guard for paper trading.

    Parameters
    ----------
    daily_loss_cap_pct : float
        Stop trading when daily PnL reaches this negative threshold (default 5%).
    max_trades_per_day : int
        Maximum number of trades allowed per day (default 50).
    overtrade_count : int
        Number of trades in window that triggers cooldown (default 10).
    overtrade_window_minutes : int
        Window in minutes for overtrade detection (default 30).
    dd_reduction_threshold : float
        Rolling DD threshold to trigger position size reduction (default 0.08).
    dd_size_multiplier : float
        Multiplier applied to position_size_pct when DD is breached (default 0.5).
    """

    daily_loss_cap_pct: float = 0.05
    max_trades_per_day: int = 50
    overtrade_count: int = 10
    overtrade_window_minutes: int = 30
    dd_reduction_threshold: float = 0.08
    dd_size_multiplier: float = 0.5

    # Internal state
    _daily_pnl: float = field(default=0.0, init=False, repr=False)
    _daily_trade_count: int = field(default=0, init=False, repr=False)
    _trade_timestamps: list[float] = field(default_factory=list, init=False, repr=False)
    _returns_history: list[float] = field(default_factory=list, init=False, repr=False)
    _day_halted: bool = field(default=False, init=False, repr=False)
    _cooldown_until: float = field(default=0.0, init=False, repr=False)

    def reset_daily(self) -> None:
        """Reset daily counters (call at midnight rotation)."""
        self._daily_pnl = 0.0
        self._daily_trade_count = 0
        self._day_halted = False
        self._trade_timestamps.clear()

    def record_trade(self, pnl_pct: float) -> None:
        """Record a completed trade for safety tracking."""
        self._daily_pnl += pnl_pct
        self._daily_trade_count += 1
        self._trade_timestamps.append(time.monotonic())
        self._returns_history.append(pnl_pct)

    def check_can_trade(self) -> tuple[bool, str]:
        """Check if a new trade is allowed.

        Returns
        -------
        tuple
            (allowed: bool, reason: str)
        """
        # Daily loss cap
        if self._daily_pnl <= -self.daily_loss_cap_pct:
            self._day_halted = True
            return False, f"daily_loss_cap: daily PnL {self._daily_pnl:.4f} breached -{self.daily_loss_cap_pct}"

        if self._day_halted:
            return False, "day_halted: trading stopped for remainder of day"

        # Max trades per day
        if self._daily_trade_count >= self.max_trades_per_day:
            return False, f"max_trades_per_day: {self._daily_trade_count} >= {self.max_trades_per_day}"

        # Overtrade cooldown
        now = time.monotonic()
        if now < self._cooldown_until:
            remaining = self._cooldown_until - now
            return False, f"overtrade_cooldown: {remaining:.0f}s remaining"

        # Check for overtrading in recent window
        window_start = now - (self.overtrade_window_minutes * 60)
        recent = [t for t in self._trade_timestamps if t >= window_start]
        if len(recent) >= self.overtrade_count:
            self._cooldown_until = now + (self.overtrade_window_minutes * 60)
            return False, (
                f"overtrade_detected: {len(recent)} trades in {self.overtrade_window_minutes}min "
                f"(limit={self.overtrade_count}) → cooldown applied"
            )

        return True, "ok"

    def adjust_position_size(self, base_size_pct: float) -> float:
        """Apply DD-triggered position size reduction.

        Parameters
        ----------
        base_size_pct : float
            Original position size percentage.

        Returns
        -------
        float
            Adjusted position size (may be reduced).
        """
        rolling_dd = self._compute_rolling_dd()
        if abs(rolling_dd) > self.dd_reduction_threshold:
            reduced = base_size_pct * self.dd_size_multiplier
            _LOG.info(
                "[risk_guard] DD-triggered size reduction: %.4f → %.4f (DD=%.4f)",
                base_size_pct, reduced, rolling_dd,
            )
            return reduced
        return base_size_pct

    def _compute_rolling_dd(self) -> float:
        """Compute rolling max drawdown from returns history."""
        if not self._returns_history:
            return 0.0
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in self._returns_history:
            equity *= (1.0 + r)
            peak = max(peak, equity)
            dd = (equity / peak) - 1.0 if peak > 0 else 0.0
            max_dd = min(max_dd, dd)
        return max_dd

    def status(self) -> dict[str, Any]:
        """Return current guard status."""
        return {
            "daily_pnl": round(self._daily_pnl, 8),
            "daily_trade_count": self._daily_trade_count,
            "day_halted": self._day_halted,
            "rolling_dd": round(self._compute_rolling_dd(), 8),
            "cooldown_active": time.monotonic() < self._cooldown_until,
        }
