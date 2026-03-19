"""Tests for the Hyper-Precision module (PR-J01, CAI Pivot 5)."""

from __future__ import annotations

import pytest

from src.execution.hyper_precision import (
    CRITICAL_TIMEOUT_BARS,
    DEFAULT_TIMEOUT_BARS,
    OBI_THRESHOLD,
    PrecisionEntryResult,
    PrecisionExitResult,
    compute_trailing_sl,
    snipe_entry,
    snipe_partial_exit,
)


# ====================================================================
# Shared helpers / fixtures
# ====================================================================
_ENTRY_DEFAULTS = dict(
    target_price=100_000.0,
    current_price=100_000.0,
    vwap_dev_pct=0.001,
    spread_pct=0.01,
    median_spread_pct=0.01,
    atr_pct=0.005,
)

_EXIT_DEFAULTS = dict(
    pct_to_close=0.25,
    current_price=100_000.0,
    vwap_dev_pct=0.001,
    spread_pct=0.01,
    median_spread_pct=0.01,
)


# ====================================================================
# snipe_entry tests
# ====================================================================
class TestSnipeEntryLimitWithGoodOBI:
    """Limit order placed when directional OBI is sufficient."""

    def test_long_limit_with_good_obi(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.75,  # well above 0.60
            **_ENTRY_DEFAULTS,
        )
        assert isinstance(result, PrecisionEntryResult)
        assert result.order_type == "limit"
        assert result.price is not None
        assert result.price < _ENTRY_DEFAULTS["current_price"]  # LONG limit below
        assert result.timeout_bars == DEFAULT_TIMEOUT_BARS
        assert "obi_ok" in result.reason

    def test_short_limit_with_good_obi(self) -> None:
        result = snipe_entry(
            direction="SHORT",
            obi=-0.75,  # sellers dominating
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "limit"
        assert result.price is not None
        assert result.price > _ENTRY_DEFAULTS["current_price"]  # SHORT limit above
        assert "obi_ok" in result.reason


class TestSnipeEntrySkipWithBadOBILowUrgency:
    """Skip when OBI is insufficient and urgency is LOW or NORMAL."""

    def test_skip_low_urgency(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.30,  # below threshold
            urgency="LOW",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "skip"
        assert result.price is None
        assert result.timeout_bars == 0
        assert "insufficient" in result.reason

    def test_skip_normal_urgency(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.30,
            urgency="NORMAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "skip"
        assert result.price is None

    def test_skip_with_none_obi(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=None,
            urgency="NORMAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "skip"

    def test_skip_short_obi_wrong_direction(self) -> None:
        """OBI is positive but direction is SHORT -> skip."""
        result = snipe_entry(
            direction="SHORT",
            obi=0.80,  # positive but we need negative for SHORT
            urgency="NORMAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "skip"


class TestSnipeEntryMarketFallbackHighUrgency:
    """Market order fallback when OBI is bad but urgency is HIGH/CRITICAL."""

    def test_market_high_urgency(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.10,
            urgency="HIGH",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "market"
        assert result.price is None
        assert result.timeout_bars == DEFAULT_TIMEOUT_BARS
        assert "market" in result.reason

    def test_market_critical_urgency(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.10,
            urgency="CRITICAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "market"
        assert result.price is None


class TestSnipeEntryShortDirection:
    """SHORT direction specifics."""

    def test_short_limit_price_above_current(self) -> None:
        result = snipe_entry(
            direction="SHORT",
            obi=-0.80,
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "limit"
        assert result.price is not None
        assert result.price > _ENTRY_DEFAULTS["current_price"]

    def test_short_skip_positive_obi(self) -> None:
        """Positive OBI with SHORT direction = skip."""
        result = snipe_entry(
            direction="SHORT",
            obi=0.90,
            urgency="NORMAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "skip"


class TestSnipeEntryCriticalTimeout:
    """CRITICAL urgency reduces timeout to 1 bar."""

    def test_critical_timeout_with_good_obi(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.75,
            urgency="CRITICAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "limit"
        assert result.timeout_bars == CRITICAL_TIMEOUT_BARS

    def test_critical_timeout_with_bad_obi_market(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=0.10,
            urgency="CRITICAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "market"
        assert result.timeout_bars == CRITICAL_TIMEOUT_BARS


class TestSnipeEntryEdgeCases:
    """Boundary / edge conditions."""

    def test_obi_exactly_at_threshold_long(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=OBI_THRESHOLD,  # exactly 0.60
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "limit"

    def test_obi_just_below_threshold_long(self) -> None:
        result = snipe_entry(
            direction="LONG",
            obi=OBI_THRESHOLD - 0.01,
            urgency="NORMAL",
            **_ENTRY_DEFAULTS,
        )
        assert result.order_type == "skip"

    def test_invalid_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            snipe_entry(direction="UP", obi=0.8, **_ENTRY_DEFAULTS)

    def test_invalid_urgency_raises(self) -> None:
        with pytest.raises(ValueError, match="urgency"):
            snipe_entry(direction="LONG", obi=0.8, urgency="ASAP", **_ENTRY_DEFAULTS)

    def test_wide_spread_still_uses_limit_with_good_obi(self) -> None:
        """Even with spread 3x median, good OBI -> limit (noted in reason)."""
        result = snipe_entry(
            direction="LONG",
            obi=0.80,
            target_price=100_000.0,
            current_price=100_000.0,
            vwap_dev_pct=0.001,
            spread_pct=0.06,           # 3x median
            median_spread_pct=0.02,
            atr_pct=0.005,
        )
        assert result.order_type == "limit"
        assert "wide_spread" in result.reason


# ====================================================================
# snipe_partial_exit tests
# ====================================================================
class TestSnipePartialExitLimitWithOBIReversal:
    """Limit exit when OBI has reversed against the position."""

    def test_long_exit_limit_with_reversal(self) -> None:
        result = snipe_partial_exit(
            direction="LONG",
            obi=-0.40,  # sellers taking over (reversal for LONG exit)
            **_EXIT_DEFAULTS,
        )
        assert isinstance(result, PrecisionExitResult)
        assert result.order_type == "limit"
        assert result.price is not None
        # Exiting a LONG is selling -> limit above current price
        assert result.price > _EXIT_DEFAULTS["current_price"]
        assert "reversal" in result.reason

    def test_short_exit_limit_with_reversal(self) -> None:
        result = snipe_partial_exit(
            direction="SHORT",
            obi=0.40,  # buyers taking over (reversal for SHORT exit)
            **_EXIT_DEFAULTS,
        )
        assert result.order_type == "limit"
        assert result.price is not None
        # Exiting a SHORT is buying -> limit below current price
        assert result.price < _EXIT_DEFAULTS["current_price"]


class TestSnipePartialExitMarketFallback:
    """Market order fallback when no OBI reversal detected."""

    def test_no_reversal_market(self) -> None:
        result = snipe_partial_exit(
            direction="LONG",
            obi=0.50,  # still favourable to position, no reversal
            **_EXIT_DEFAULTS,
        )
        assert result.order_type == "market"
        assert result.price is None
        assert "market" in result.reason

    def test_none_obi_market(self) -> None:
        result = snipe_partial_exit(
            direction="LONG",
            obi=None,
            **_EXIT_DEFAULTS,
        )
        assert result.order_type == "market"

    def test_wide_spread_forces_market(self) -> None:
        """Even with OBI reversal, wide spread -> market."""
        result = snipe_partial_exit(
            direction="LONG",
            obi=-0.50,
            pct_to_close=0.25,
            current_price=100_000.0,
            vwap_dev_pct=0.001,
            spread_pct=0.10,           # 5x median
            median_spread_pct=0.02,
        )
        assert result.order_type == "market"


# ====================================================================
# compute_trailing_sl tests
# ====================================================================
class TestComputeTrailingSLLongOnlyUp:
    """LONG: SL should only ratchet upward."""

    def test_first_computation_no_current_sl(self) -> None:
        sl = compute_trailing_sl(
            direction="LONG",
            current_price=100_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        assert sl == 100_000.0 - 500.0 * 2.0  # 99_000.0

    def test_sl_moves_up_when_price_rises(self) -> None:
        sl1 = compute_trailing_sl(
            direction="LONG",
            current_price=100_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        sl2 = compute_trailing_sl(
            direction="LONG",
            current_price=101_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=sl1,
        )
        assert sl2 > sl1

    def test_sl_does_not_move_down(self) -> None:
        sl1 = compute_trailing_sl(
            direction="LONG",
            current_price=101_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        # Price drops -- candidate SL would be lower, but we keep old SL
        sl2 = compute_trailing_sl(
            direction="LONG",
            current_price=99_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=sl1,
        )
        assert sl2 == sl1  # monotonic: never goes down

    def test_multiple_ratchets(self) -> None:
        prices = [100_000.0, 101_000.0, 102_000.0, 101_500.0, 103_000.0]
        sl = None
        prev_sl = -float("inf")
        for px in prices:
            sl = compute_trailing_sl(
                direction="LONG",
                current_price=px,
                atr=500.0,
                trailing_mult=2.0,
                current_sl=sl,
            )
            assert sl >= prev_sl
            prev_sl = sl


class TestComputeTrailingSLShortOnlyDown:
    """SHORT: SL should only ratchet downward."""

    def test_first_computation_no_current_sl(self) -> None:
        sl = compute_trailing_sl(
            direction="SHORT",
            current_price=100_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        assert sl == 100_000.0 + 500.0 * 2.0  # 101_000.0

    def test_sl_moves_down_when_price_drops(self) -> None:
        sl1 = compute_trailing_sl(
            direction="SHORT",
            current_price=100_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        sl2 = compute_trailing_sl(
            direction="SHORT",
            current_price=99_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=sl1,
        )
        assert sl2 < sl1

    def test_sl_does_not_move_up(self) -> None:
        sl1 = compute_trailing_sl(
            direction="SHORT",
            current_price=99_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        # Price rises -- candidate SL would be higher, but we keep old SL
        sl2 = compute_trailing_sl(
            direction="SHORT",
            current_price=101_000.0,
            atr=500.0,
            trailing_mult=2.0,
            current_sl=sl1,
        )
        assert sl2 == sl1

    def test_multiple_ratchets(self) -> None:
        prices = [100_000.0, 99_000.0, 98_000.0, 98_500.0, 97_000.0]
        sl = None
        prev_sl = float("inf")
        for px in prices:
            sl = compute_trailing_sl(
                direction="SHORT",
                current_price=px,
                atr=500.0,
                trailing_mult=2.0,
                current_sl=sl,
            )
            assert sl <= prev_sl
            prev_sl = sl


class TestComputeTrailingSLATRMultiplier:
    """ATR multiplier is applied correctly."""

    def test_mult_2_0(self) -> None:
        sl = compute_trailing_sl(
            direction="LONG",
            current_price=50_000.0,
            atr=200.0,
            trailing_mult=2.0,
            current_sl=None,
        )
        assert sl == pytest.approx(50_000.0 - 400.0)

    def test_mult_1_2(self) -> None:
        sl = compute_trailing_sl(
            direction="LONG",
            current_price=50_000.0,
            atr=200.0,
            trailing_mult=1.2,
            current_sl=None,
        )
        assert sl == pytest.approx(50_000.0 - 240.0)

    def test_mult_3_0_short(self) -> None:
        sl = compute_trailing_sl(
            direction="SHORT",
            current_price=50_000.0,
            atr=200.0,
            trailing_mult=3.0,
            current_sl=None,
        )
        assert sl == pytest.approx(50_000.0 + 600.0)

    def test_invalid_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            compute_trailing_sl(
                direction="FLAT",
                current_price=50_000.0,
                atr=200.0,
                trailing_mult=2.0,
                current_sl=None,
            )


# ====================================================================
# Contract tests (GR-6: frozen dataclasses)
# ====================================================================
class TestFrozenContracts:
    def test_entry_result_is_frozen(self) -> None:
        result = PrecisionEntryResult(
            order_type="limit", price=100.0, timeout_bars=3, reason="test"
        )
        with pytest.raises(AttributeError):
            result.price = 200.0  # type: ignore[misc]

    def test_exit_result_is_frozen(self) -> None:
        result = PrecisionExitResult(
            order_type="market", price=None, timeout_bars=3, reason="test"
        )
        with pytest.raises(AttributeError):
            result.order_type = "limit"  # type: ignore[misc]
