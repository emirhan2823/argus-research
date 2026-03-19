"""Tests for the backtest validation framework."""

from __future__ import annotations

import pytest

from src.backtest.validation import (
    EngineRegimeStats,
    TradeRecord,
    ValidationReport,
    profit_factor,
    validate_filter_performance,
    win_rate_by_group,
)


class TestProfitFactor:
    def test_basic(self):
        assert profit_factor([100, -50, 200, -30]) == pytest.approx(300 / 80)

    def test_all_wins(self):
        assert profit_factor([10, 20, 30]) == float("inf")

    def test_all_losses(self):
        assert profit_factor([-10, -20]) == 0.0

    def test_empty(self):
        assert profit_factor([]) == 0.0


class TestWinRateByGroup:
    def test_engine_grouping(self):
        trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7),
            TradeRecord(pnl=-5.0, engine="TITAN", regime="TRENDING", confidence=0.6),
            TradeRecord(pnl=8.0, engine="NAUTILUS", regime="RANGING", confidence=0.7),
        ]
        result = win_rate_by_group(trades, "engine")
        assert result["TITAN"] == pytest.approx(0.50)
        assert result["NAUTILUS"] == pytest.approx(1.0)

    def test_regime_grouping(self):
        trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7),
            TradeRecord(pnl=8.0, engine="TITAN", regime="TRENDING", confidence=0.6),
            TradeRecord(pnl=-5.0, engine="NAUTILUS", regime="RANGING", confidence=0.7),
        ]
        result = win_rate_by_group(trades, "regime")
        assert result["TRENDING"] == pytest.approx(1.0)
        assert result["RANGING"] == pytest.approx(0.0)


class TestValidateFilterPerformance:
    def test_empty_trades(self):
        report = validate_filter_performance([])
        assert report.overall_trade_count == 0
        assert report.overfitting_risk == "LOW"

    def test_good_performance(self):
        trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7, is_in_sample=True)
            for _ in range(25)
        ] + [
            TradeRecord(pnl=-3.0, engine="TITAN", regime="TRENDING", confidence=0.6, is_in_sample=True)
            for _ in range(10)
        ]
        report = validate_filter_performance(trades)
        assert report.overall_win_rate == pytest.approx(25 / 35, rel=0.01)
        assert report.overall_trade_count == 35
        assert report.engine_regime_stats[0].sufficient_sample is True

    def test_insufficient_sample_flagged(self):
        trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7)
            for _ in range(5)
        ]
        report = validate_filter_performance(trades, min_sample_size=30)
        assert report.engine_regime_stats[0].sufficient_sample is False
        assert any("unreliable" in r for r in report.recommendations)

    def test_overfitting_detection(self):
        is_trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7, is_in_sample=True)
            for _ in range(40)
        ]
        oos_trades = [
            TradeRecord(pnl=-5.0, engine="TITAN", regime="TRENDING", confidence=0.7, is_in_sample=False)
            for _ in range(20)
        ]
        report = validate_filter_performance(is_trades + oos_trades)
        assert report.in_sample_win_rate == pytest.approx(1.0)
        assert report.out_of_sample_win_rate == pytest.approx(0.0)
        assert report.overfitting_risk == "HIGH"
        assert report.degradation_pct == pytest.approx(1.0)

    def test_low_overfit_risk(self):
        is_trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7, is_in_sample=True)
            for _ in range(30)
        ] + [
            TradeRecord(pnl=-5.0, engine="TITAN", regime="TRENDING", confidence=0.6, is_in_sample=True)
            for _ in range(10)
        ]
        oos_trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7, is_in_sample=False)
            for _ in range(20)
        ] + [
            TradeRecord(pnl=-5.0, engine="TITAN", regime="TRENDING", confidence=0.6, is_in_sample=False)
            for _ in range(10)
        ]
        report = validate_filter_performance(is_trades + oos_trades)
        # IS WR = 75%, OOS WR = 66.7%, degradation ~11%
        assert report.overfitting_risk == "LOW"

    def test_poor_engine_regime_flagged(self):
        trades = [
            TradeRecord(pnl=-5.0, engine="HYDRA", regime="RANGING", confidence=0.6)
            for _ in range(35)
        ]
        report = validate_filter_performance(trades)
        assert report.engine_regime_stats[0].win_rate == 0.0
        assert any("below 50%" in r for r in report.recommendations)

    def test_no_oos_trades_warning(self):
        trades = [
            TradeRecord(pnl=10.0, engine="TITAN", regime="TRENDING", confidence=0.7, is_in_sample=True)
            for _ in range(20)
        ]
        report = validate_filter_performance(trades)
        assert any("walk-forward" in r.lower() for r in report.recommendations)
