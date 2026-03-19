"""TITAN multi-tier exit system tests — TP1/TP2/runner + structure trailing."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.backtest.exit_policy import (
    EngineExitConfig,
    evaluate_exit_bar_by_bar,
    get_engine_exit_config,
    _find_swing_low,
    _find_swing_high,
    _structure_trail_level,
    REASON_TRAILING_STOP,
    REASON_BREAKEVEN_STOP,
    REASON_STOP_LOSS,
    REASON_TIME_EXIT,
)


_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(close: float, high: float | None = None, low: float | None = None, offset_h: int = 0):
    h = high if high is not None else close * 1.003
    l = low if low is not None else close * 0.997
    return {
        "timestamp": _TS.replace(hour=offset_h % 24),
        "high": h,
        "low": l,
        "close": close,
    }


# ── TITAN config from registry uses tiers ──

TITAN_CFG = get_engine_exit_config("TITAN")

# ── Custom tier config for tests ──

TIER_CFG = EngineExitConfig(
    trailing_enabled=True,
    trail_atr_mult=2.5,
    be_lock_enabled=False,
    unlimited_hold=True,
    partial_tp_enabled=False,
    partial_tp_tiers=(
        (1.0, 0.33),   # TP1 at 1R
        (2.0, 0.33),   # TP2 at 2R
    ),
    be_after_tp1=True,
    be_after_tp1_buffer_pct=0.002,
    runner_trail_mode="atr",
    runner_trail_atr_mult=2.0,
    runner_atr_buffer=0.3,
)


class TestMultiTierTP:
    def test_tp1_triggers_at_1r(self) -> None:
        """TP1 should fire when close reaches entry + 1R."""
        # Entry 100, SL 95 -> R = 5. TP1 at 100 + 5 = 105
        candles = [
            _candle(103.0, offset_h=1),
            _candle(105.5, offset_h=2),  # close > 105 -> TP1 hit
            _candle(106.0, offset_h=3),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=TIER_CFG,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) >= 1
        assert result.partial_exits[0].fraction == 0.33

    def test_tp2_triggers_at_2r(self) -> None:
        """TP2 should fire after TP1 when close reaches entry + 2R."""
        # Entry 100, SL 95 -> R = 5. TP1 at 105, TP2 at 110
        candles = [
            _candle(103.0, offset_h=1),
            _candle(105.5, offset_h=2),  # TP1 hit
            _candle(108.0, offset_h=3),
            _candle(110.5, offset_h=4),  # TP2 hit
            _candle(111.0, offset_h=5),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=TIER_CFG,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 2
        assert result.partial_exits[0].fraction == 0.33
        assert result.partial_exits[1].fraction == 0.33

    def test_be_after_tp1_moves_sl(self) -> None:
        """After TP1, SL should move to entry + buffer."""
        # Entry 100, SL 95 -> R = 5. TP1 at 105.
        # After TP1: SL -> 100 * (1 + 0.002) = 100.2
        # Use config with no trailing so we can isolate BE behavior
        be_cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_tiers=(
                (1.0, 0.33),
            ),
            be_after_tp1=True,
            be_after_tp1_buffer_pct=0.002,
        )
        candles = [
            _candle(105.5, offset_h=1),  # TP1 hit -> SL = 100.2
            _candle(103.0, offset_h=2),  # price drops
            _candle(99.0, low=99.0, offset_h=3),  # low < SL 100.2 -> BE stop
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=be_cfg,
        )
        assert result is not None
        assert result.be_locked is True
        assert result.exit_reason == REASON_BREAKEVEN_STOP
        assert result.exit_price == pytest.approx(100.2, abs=0.01)

    def test_runner_survives_after_tp2(self) -> None:
        """After both tiers, runner should continue with trailing."""
        # Entry 100, SL 95 -> R = 5. TP1 at 105, TP2 at 110.
        # After TP2: runner mode with ATR×2.0 trailing.
        # ATR distance = 100 * 0.02 * 2.0 = 4.0
        candles = [
            _candle(105.5, offset_h=1),  # TP1
            _candle(110.5, offset_h=2),  # TP2 -> runner active
            _candle(115.0, offset_h=3),  # trail: 115 - 4 = 111
            _candle(112.0, offset_h=4),  # no hit (112 > 111)
            _candle(116.0, offset_h=5),  # trail: 116 - 4 = 112
            _candle(111.0, low=111.5, offset_h=6),  # low=111.5 < 112 -> trail hit
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=TIER_CFG,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 2  # Both tiers filled
        assert result.exit_reason == REASON_TRAILING_STOP

    def test_runner_trail_short(self) -> None:
        """Runner trailing works for short positions."""
        short_cfg = EngineExitConfig(
            trailing_enabled=True,
            trail_atr_mult=2.5,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_tiers=(
                (1.0, 0.33),
                (2.0, 0.33),
            ),
            be_after_tp1=True,
            be_after_tp1_buffer_pct=0.002,
            runner_trail_mode="atr",
            runner_trail_atr_mult=2.0,
        )
        # Entry 100, SL 105 -> R = 5. TP1 at 95, TP2 at 90.
        # Runner ATR trail dist = 100 * 0.02 * 2.0 = 4.0
        candles = [
            _candle(94.0, offset_h=1),   # TP1 (< 95)
            _candle(89.0, offset_h=2),   # TP2 (< 90) -> runner
            _candle(85.0, offset_h=3),   # trail: 85 + 4 = 89
            _candle(83.0, offset_h=4),   # trail: 83 + 4 = 87 < 89 -> ratchet
            _candle(88.0, high=87.5, offset_h=5),  # high=87.5 >= 87 -> trail hit
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="short", entry_price=100.0,
            initial_stop_price=105.0, atr_pct=0.02, config=short_cfg,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 2
        assert result.exit_reason == REASON_TRAILING_STOP

    def test_tiers_override_single_partial(self) -> None:
        """When partial_tp_tiers is set, old partial_tp_r is ignored."""
        cfg = EngineExitConfig(
            trailing_enabled=True,
            trail_atr_mult=2.5,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_enabled=True,   # would trigger at 1.5R
            partial_tp_r=1.5,
            partial_tp_fraction=0.5,
            partial_tp_tiers=((1.0, 0.33),),  # tiers override
        )
        # Entry 100, SL 95 -> R = 5. Old single TP at 107.5, tier TP1 at 105.
        candles = [
            _candle(105.5, offset_h=1),  # tier TP1 hits at 1R (105)
            _candle(106.0, offset_h=2),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 1
        assert result.partial_exits[0].fraction == 0.33  # tier fraction, not 0.5

    def test_backward_compat_no_tiers(self) -> None:
        """Engines without tiers still use old single partial TP."""
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_enabled=True,
            partial_tp_r=1.5,
            partial_tp_fraction=0.5,
        )
        # Entry 100, SL 95 -> R = 5. Single partial at 107.5
        candles = [
            _candle(108.0, offset_h=1),  # single partial hit
            _candle(109.0, offset_h=2),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 1
        assert result.partial_exits[0].fraction == 0.5  # old single fraction


class TestStructureTrailing:
    def test_find_swing_low_basic(self) -> None:
        """Simple 3-bar pivot detection for swing lows."""
        lows = [100, 99, 98, 99, 97, 98, 96, 97, 95, 96]
        # Pivots at: idx=2 (98), idx=4 (97), idx=6 (96), idx=8 (95)
        swing = _find_swing_low(lows, end=10, lookback=20)
        assert swing is not None
        assert swing == 95  # most recent

    def test_find_swing_high_basic(self) -> None:
        """Simple 3-bar pivot detection for swing highs."""
        highs = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104]
        # Pivots at: idx=2 (102), idx=4 (103), idx=6 (104), idx=8 (105)
        swing = _find_swing_high(highs, end=10, lookback=20)
        assert swing is not None
        assert swing == 105

    def test_structure_trail_long(self) -> None:
        """Structure trailing places SL below swing low with ATR buffer."""
        lows = [100, 99, 98, 99, 97, 98, 96, 97, 95, 96]
        highs = [102] * 10
        level = _structure_trail_level(
            highs, lows, current_index=10, side="long",
            atr_value=2.0, atr_buffer=0.3,
        )
        # Last swing low = 95, SL = 95 - 2.0 * 0.3 = 94.4
        assert level is not None
        assert level == pytest.approx(94.4, abs=0.01)

    def test_structure_trail_short(self) -> None:
        """Structure trailing places SL above swing high with ATR buffer."""
        highs = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104]
        lows = [98] * 10
        level = _structure_trail_level(
            highs, lows, current_index=10, side="short",
            atr_value=2.0, atr_buffer=0.3,
        )
        # Last swing high = 105, SL = 105 + 2.0 * 0.3 = 105.6
        assert level is not None
        assert level == pytest.approx(105.6, abs=0.01)

    def test_structure_trail_fallback_none(self) -> None:
        """Returns None when insufficient data for swing detection."""
        level = _structure_trail_level(
            [100, 100], [99, 99], current_index=2, side="long",
            atr_value=2.0, atr_buffer=0.3,
        )
        assert level is None

    def test_structure_trail_in_evaluate(self) -> None:
        """Structure trailing integrates with evaluate_exit_bar_by_bar."""
        struct_cfg = EngineExitConfig(
            trailing_enabled=True,
            trail_atr_mult=2.5,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_tiers=(
                (1.0, 0.50),  # TP1 at 1R -> 50% -> runner immediately
            ),
            be_after_tp1=False,
            runner_trail_mode="structure",
            runner_trail_atr_mult=2.0,
            runner_atr_buffer=0.3,
        )
        # Entry 100, SL 95 -> R = 5. TP1 at 105.
        # Provide candle history with swing lows for structure trailing
        candles = [
            _candle(105.5, offset_h=1),  # TP1 -> runner active
            _candle(107.0, high=107.5, low=106.0, offset_h=2),
            _candle(106.0, high=106.5, low=105.0, offset_h=3),  # swing low = 105
            _candle(108.0, high=108.5, low=107.0, offset_h=4),
            _candle(107.0, high=107.5, low=106.0, offset_h=5),  # swing low = 106
            _candle(109.0, high=109.5, low=108.0, offset_h=6),
        ]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]

        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=struct_cfg,
            candle_highs=highs, candle_lows=lows,
        )
        assert result is not None
        # Should have partial exit from TP1
        assert result.partial_exits is not None
        assert len(result.partial_exits) >= 1
