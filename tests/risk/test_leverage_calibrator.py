"""Tests for Dynamic Leverage Calibrator."""

from __future__ import annotations

import pytest

from src.risk.leverage_calibrator import (
    CalibratedLeverage,
    LeverageCalibrationConfig,
    calibrate_leverage,
    calibrate_leverage_for_scale_in,
)


def _cfg(**overrides) -> LeverageCalibrationConfig:
    defaults = dict(
        enabled=True,
        max_leverage=20.0,
        min_leverage=1.0,
        risk_pct=0.02,
        safety_margin=1.0,  # No safety margin for clean test math
    )
    defaults.update(overrides)
    return LeverageCalibrationConfig(**defaults)


# --- Core Invariant Tests ---


class TestCoreInvariant:
    """Risk USD must be consistent across different stop distances."""

    def test_1pct_stop_gives_2x_leverage(self):
        """Standard case: 2% risk, 1% stop → 2x leverage."""
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.01,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == pytest.approx(2.0)
        assert result.risk_usd == pytest.approx(200.0)

    def test_3pct_stop_reduces_leverage(self):
        """Wider stop: 2% risk, 3% stop → ~0.667x → clamped to 1.0x."""
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.03,
            entry_price=65000.0, config=_cfg(),
        )
        # 200 / (0.03 * 10000) = 0.667 → clamped to 1.0
        assert result.leverage == pytest.approx(1.0)

    def test_tight_stop_increases_leverage(self):
        """Tight stop: 2% risk, 0.5% stop → 4x leverage."""
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.005,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == pytest.approx(4.0)

    def test_very_tight_stop_10x(self):
        """Sniper entry: 2% risk, 0.2% stop → 10x leverage."""
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.002,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == pytest.approx(10.0)

    def test_risk_pct_consistent_across_stops(self):
        """The absolute risk in USD should be the same regardless of stop distance."""
        cfg = _cfg(max_leverage=20.0)
        stops = [0.005, 0.01, 0.02]
        results = [
            calibrate_leverage(
                equity=10000.0, risk_pct=0.02,
                stop_distance_pct=s, entry_price=65000.0, config=cfg,
            )
            for s in stops
        ]
        # All should risk $200 (or less if capped)
        for r in results:
            assert r.risk_usd <= 200.0 + 0.01  # allow float epsilon


# --- Cap Tests ---


class TestCaps:
    def test_max_leverage_cap_respected(self):
        """Leverage never exceeds config max_leverage."""
        cfg = _cfg(max_leverage=5.0)
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.001,
            entry_price=65000.0, config=cfg,
        )
        # Theoretical: 20x, but capped at 5x
        assert result.leverage == pytest.approx(5.0)
        assert result.was_capped is True
        assert "capped" in result.reason

    def test_min_leverage_floor(self):
        """Very wide stop → leverage floors at 1.0."""
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.10,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == pytest.approx(1.0)


# --- Safety Margin Tests ---


class TestSafetyMargin:
    def test_safety_margin_reduces_leverage(self):
        """95% safety margin → 95% of theoretical leverage."""
        cfg = _cfg(safety_margin=0.95)
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.01,
            entry_price=65000.0, config=cfg,
        )
        # Theoretical 2.0x * 0.95 = 1.9x
        assert result.leverage == pytest.approx(1.9)


# --- Edge Case Tests ---


class TestEdgeCases:
    def test_zero_equity_returns_1x(self):
        result = calibrate_leverage(
            equity=0.0, risk_pct=0.02, stop_distance_pct=0.01,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == 1.0
        assert result.reason == "invalid_equity"

    def test_zero_stop_returns_1x(self):
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.0,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == 1.0
        assert result.reason == "invalid_stop_distance"

    def test_negative_entry_returns_1x(self):
        result = calibrate_leverage(
            equity=10000.0, risk_pct=0.02, stop_distance_pct=0.01,
            entry_price=-100.0, config=_cfg(),
        )
        assert result.leverage == 1.0
        assert result.reason == "invalid_entry_price"

    def test_nan_equity_returns_1x(self):
        result = calibrate_leverage(
            equity=float("nan"), risk_pct=0.02, stop_distance_pct=0.01,
            entry_price=65000.0, config=_cfg(),
        )
        assert result.leverage == 1.0


# --- Scale-In Integration Tests ---


class TestScaleInIntegration:
    def test_calibrate_for_scale_in_long(self):
        """After scale-in, leverage calibrates from average entry to SL."""
        result = calibrate_leverage_for_scale_in(
            equity=10000.0, risk_pct=0.02,
            avg_entry_price=64000.0,  # avg from 65k + 63k entries
            current_sl_price=63360.0,  # 1% below avg
            side="long", config=_cfg(),
        )
        assert result.leverage == pytest.approx(2.0)
        assert result.stop_distance_pct == pytest.approx(0.01)

    def test_calibrate_for_scale_in_short(self):
        """Short side: SL above avg entry."""
        result = calibrate_leverage_for_scale_in(
            equity=10000.0, risk_pct=0.02,
            avg_entry_price=65000.0,
            current_sl_price=66300.0,  # 2% above avg
            side="short", config=_cfg(),
        )
        assert result.leverage == pytest.approx(1.0)
        assert result.stop_distance_pct == pytest.approx(0.02)

    def test_calibrate_for_scale_in_zero_entry(self):
        result = calibrate_leverage_for_scale_in(
            equity=10000.0, risk_pct=0.02,
            avg_entry_price=0.0, current_sl_price=63000.0,
            side="long", config=_cfg(),
        )
        assert result.leverage == 1.0
        assert result.reason == "invalid_avg_entry"
