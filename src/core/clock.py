"""ARGUS v2.0 — Unified clock for live and backtest modes."""

from datetime import datetime, timezone


class Clock:
    """Provides current time. In live mode uses real UTC; in backtest mode
    uses simulated time that advances per candle."""

    def __init__(self, mode: str = "live") -> None:
        if mode not in ("live", "backtest"):
            raise ValueError(f"Invalid clock mode: {mode!r}. Must be 'live' or 'backtest'.")
        self._mode = mode
        self._simulated_time: datetime | None = None

    @property
    def mode(self) -> str:
        return self._mode

    def now(self) -> datetime:
        """Return current time (UTC)."""
        if self._mode == "live":
            return datetime.now(timezone.utc)
        if self._simulated_time is None:
            raise RuntimeError("Backtest clock has no simulated time set. Call advance() first.")
        return self._simulated_time

    def advance(self, dt: datetime) -> None:
        """Set simulated time (backtest mode only)."""
        if self._mode != "backtest":
            raise RuntimeError("Cannot advance clock in live mode.")
        self._simulated_time = dt

    def reset(self) -> None:
        """Reset simulated time to None (backtest mode only)."""
        if self._mode != "backtest":
            raise RuntimeError("Cannot reset clock in live mode.")
        self._simulated_time = None
