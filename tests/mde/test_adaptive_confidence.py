"""Tests for the adaptive confidence floor module."""

from __future__ import annotations

import pytest

from src.mde.adaptive_confidence import AdaptiveFloorResult, compute_adaptive_floor


class TestInsufficientData:
    def test_empty_history(self):
        result = compute_adaptive_floor(recent_trade_outcomes=[])
        assert result.effective_min_confidence == 0.65
        assert result.adjustment == 0.0
        assert "insufficient_data" in result.reason

    def test_under_10_trades(self):
        result = compute_adaptive_floor(recent_trade_outcomes=[True, False, True, True, False])
        assert result.effective_min_confidence == 0.65
        assert result.sample_size == 5


class TestHighWinRate:
    def test_relaxation_at_65_percent(self):
        outcomes = [True] * 13 + [False] * 7  # 65% WR
        result = compute_adaptive_floor(recent_trade_outcomes=outcomes)
        assert result.adjustment == -0.03
        assert result.effective_min_confidence == 0.62

    def test_relaxation_at_80_percent(self):
        outcomes = [True] * 16 + [False] * 4  # 80% WR
        result = compute_adaptive_floor(recent_trade_outcomes=outcomes)
        assert result.adjustment == -0.03
        assert result.effective_min_confidence == 0.62


class TestNormalWinRate:
    def test_no_change_at_60_percent(self):
        outcomes = [True] * 12 + [False] * 8  # 60% WR
        result = compute_adaptive_floor(recent_trade_outcomes=outcomes)
        assert result.adjustment == 0.0
        assert result.effective_min_confidence == 0.65


class TestLowWinRate:
    def test_tighten_at_50_percent(self):
        outcomes = [True] * 10 + [False] * 10  # 50% WR
        result = compute_adaptive_floor(recent_trade_outcomes=outcomes)
        assert result.adjustment == 0.05
        assert result.effective_min_confidence == 0.70

    def test_heavy_tighten_at_35_percent(self):
        outcomes = [True] * 7 + [False] * 13  # 35% WR
        result = compute_adaptive_floor(recent_trade_outcomes=outcomes)
        assert result.adjustment == 0.10
        assert result.effective_min_confidence == 0.75


class TestFloorBounds:
    def test_floor_never_below_low(self):
        # Even with relaxation, shouldn't go below 0.60
        result = compute_adaptive_floor(
            base_min_confidence=0.60,
            recent_trade_outcomes=[True] * 18 + [False] * 2,
        )
        assert result.effective_min_confidence >= 0.60

    def test_floor_never_above_high(self):
        # Even with worst performance, shouldn't exceed 0.80
        result = compute_adaptive_floor(
            base_min_confidence=0.75,
            recent_trade_outcomes=[False] * 20,
        )
        assert result.effective_min_confidence <= 0.80


class TestLookback:
    def test_only_recent_trades_matter(self):
        # Old trades were good, recent are bad
        old_good = [True] * 30
        recent_bad = [False] * 15 + [True] * 5
        result = compute_adaptive_floor(
            recent_trade_outcomes=old_good + recent_bad,
            lookback=20,
        )
        # Should use only last 20 trades (25% WR)
        assert result.adjustment == 0.10
        assert result.recent_win_rate == 0.25
