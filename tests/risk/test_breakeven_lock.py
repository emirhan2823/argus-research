"""Tests for Aggressive Break-Even Lock."""

from __future__ import annotations

import pytest

from src.risk.breakeven_lock import (
    BreakevenConfig,
    check_breakeven_trigger,
    compute_breakeven_price,
)


def _cfg(**overrides) -> BreakevenConfig:
    defaults = dict(
        enabled=True,
        trigger_atr_multiple=1.0,
        include_fees=True,
        default_fee_pct=0.001,
    )
    defaults.update(overrides)
    return BreakevenConfig(**defaults)


# --- Break-Even Price Computation ---


class TestBreakevenPrice:
    def test_be_price_long_with_fees(self):
        """Long BE = entry × (1 + 2 × fee_pct)."""
        be = compute_breakeven_price(
            avg_entry_price=65000.0, side="long",
            fee_pct=0.001, include_fees=True,
        )
        # 65000 × 1.002 = 65130
        assert be == pytest.approx(65130.0)

    def test_be_price_short_with_fees(self):
        """Short BE = entry × (1 - 2 × fee_pct)."""
        be = compute_breakeven_price(
            avg_entry_price=65000.0, side="short",
            fee_pct=0.001, include_fees=True,
        )
        # 65000 × 0.998 = 64870
        assert be == pytest.approx(64870.0)

    def test_be_price_no_fees(self):
        """Without fees, BE = entry price exactly."""
        be = compute_breakeven_price(
            avg_entry_price=65000.0, side="long",
            fee_pct=0.001, include_fees=False,
        )
        assert be == pytest.approx(65000.0)

    def test_fee_adjusted_be_price(self):
        """With 0.05% fee per side, round-trip is 0.1%."""
        be = compute_breakeven_price(
            avg_entry_price=10000.0, side="long",
            fee_pct=0.0005, include_fees=True,
        )
        assert be == pytest.approx(10010.0)  # 10000 * 1.001


# --- Long Position Tests ---


class TestLongPosition:
    def test_snap_to_be_at_1x_atr_long(self):
        """Long: price >= entry + 1×ATR → SL snaps to BE."""
        result = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=66500.0,  # +1500, ATR=1000 → 1.5R
            atr=1000.0,
            current_sl=63000.0,     # current SL is below entry
            config=_cfg(),
        )
        assert result.triggered is True
        assert result.new_sl == pytest.approx(65130.0)  # BE with fees
        assert result.profit_distance == pytest.approx(1.5)
        assert "locked" in result.reason

    def test_no_snap_below_threshold(self):
        """Long: price hasn't reached 1×ATR → no change."""
        result = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=65500.0,  # only +500, ATR=1000 → 0.5R
            atr=1000.0,
            current_sl=63000.0,
            config=_cfg(),
        )
        assert result.triggered is False
        assert result.new_sl == pytest.approx(63000.0)  # unchanged
        assert "below_trigger" in result.reason

    def test_already_locked_no_regression(self):
        """SL already above BE → don't move it backwards."""
        result = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=67000.0,  # +2000, ATR=1000 → 2R
            atr=1000.0,
            current_sl=65500.0,     # SL is already above BE (65130)
            config=_cfg(),
        )
        assert result.triggered is True
        # SL should stay at 65500 (higher than BE 65130), NOT regress
        assert result.new_sl == pytest.approx(65500.0)

    def test_different_atr_multiple_trigger(self):
        """Custom trigger at 2× ATR."""
        cfg = _cfg(trigger_atr_multiple=2.0)
        result = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=66500.0,  # +1500, ATR=1000 → 1.5R < 2R trigger
            atr=1000.0,
            current_sl=63000.0,
            config=cfg,
        )
        assert result.triggered is False

        result2 = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=67500.0,  # +2500, ATR=1000 → 2.5R >= 2R trigger
            atr=1000.0,
            current_sl=63000.0,
            config=cfg,
        )
        assert result2.triggered is True


# --- Short Position Tests ---


class TestShortPosition:
    def test_snap_to_be_at_1x_atr_short(self):
        """Short: price <= entry - 1×ATR → SL snaps to BE."""
        result = check_breakeven_trigger(
            side="short",
            avg_entry_price=65000.0,
            current_price=63500.0,  # -1500, ATR=1000 → 1.5R
            atr=1000.0,
            current_sl=67000.0,     # current SL above entry
            config=_cfg(),
        )
        assert result.triggered is True
        # Short BE = 65000 * 0.998 = 64870
        assert result.new_sl == pytest.approx(64870.0)
        assert "locked" in result.reason

    def test_short_no_regression(self):
        """Short: SL already below BE → don't move up."""
        result = check_breakeven_trigger(
            side="short",
            avg_entry_price=65000.0,
            current_price=63000.0,  # -2000, ATR=1000 → 2R
            atr=1000.0,
            current_sl=64500.0,     # SL already below BE (64870)
            config=_cfg(),
        )
        assert result.triggered is True
        assert result.new_sl == pytest.approx(64500.0)  # Stay at lower value


# --- Disabled Config Tests ---


class TestDisabledConfig:
    def test_disabled_config_passthrough(self):
        """When disabled, returns current SL unchanged."""
        cfg = _cfg(enabled=False)
        result = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=70000.0,
            atr=1000.0,
            current_sl=63000.0,
            config=cfg,
        )
        assert result.triggered is False
        assert result.new_sl == pytest.approx(63000.0)
        assert "disabled" in result.reason


# --- Edge Case Tests ---


class TestEdgeCases:
    def test_zero_atr_returns_no_trigger(self):
        result = check_breakeven_trigger(
            side="long", avg_entry_price=65000.0,
            current_price=66000.0, atr=0.0,
            current_sl=63000.0, config=_cfg(),
        )
        assert result.triggered is False
        assert "invalid_atr" in result.reason

    def test_negative_entry_returns_no_trigger(self):
        result = check_breakeven_trigger(
            side="long", avg_entry_price=-100.0,
            current_price=66000.0, atr=1000.0,
            current_sl=63000.0, config=_cfg(),
        )
        assert result.triggered is False
        assert "invalid" in result.reason

    def test_fee_pct_override(self):
        """Custom fee_pct overrides config default."""
        result = check_breakeven_trigger(
            side="long",
            avg_entry_price=65000.0,
            current_price=66500.0,
            atr=1000.0,
            current_sl=63000.0,
            config=_cfg(),
            fee_pct=0.005,  # 0.5% per side = 1% round trip
        )
        assert result.triggered is True
        # BE = 65000 * (1 + 2*0.005) = 65000 * 1.01 = 65650
        assert result.new_sl == pytest.approx(65650.0)
