"""Tests for unified clock."""

from datetime import datetime, timezone

import pytest

from src.core.clock import Clock


class TestClock:
    def test_live_mode_returns_utc(self):
        clock = Clock(mode="live")
        now = clock.now()
        assert now.tzinfo is not None

    def test_backtest_mode_requires_advance(self):
        clock = Clock(mode="backtest")
        with pytest.raises(RuntimeError, match="no simulated time"):
            clock.now()

    def test_backtest_advance(self):
        clock = Clock(mode="backtest")
        t = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        clock.advance(t)
        assert clock.now() == t

    def test_live_cannot_advance(self):
        clock = Clock(mode="live")
        with pytest.raises(RuntimeError, match="live mode"):
            clock.advance(datetime.now(timezone.utc))

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="Invalid clock mode"):
            Clock(mode="turbo")

    def test_reset(self):
        clock = Clock(mode="backtest")
        clock.advance(datetime(2024, 1, 1, tzinfo=timezone.utc))
        clock.reset()
        with pytest.raises(RuntimeError):
            clock.now()
