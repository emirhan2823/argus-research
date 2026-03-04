"""TITAN v2 exit policy tests — ATR trailing, R-based BE, partial TP, unlimited hold."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.backtest.exit_policy import (
    ENGINE_EXIT_CONFIGS,
    EngineExitConfig,
    evaluate_exit_bar_by_bar,
    get_engine_exit_config,
    REASON_TRAILING_STOP,
    REASON_BREAKEVEN_STOP,
    REASON_STOP_LOSS,
    REASON_TIME_STOP,
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


class TestTitanExitConfig:
    def test_titan_config_exists(self) -> None:
        cfg = get_engine_exit_config("TITAN")
        assert cfg.trailing_enabled is True
        assert cfg.trail_atr_mult == 2.5
        assert cfg.be_lock_enabled is False
        assert cfg.unlimited_hold is True
        # Multi-tier TP replaces single partial TP
        assert cfg.partial_tp_enabled is False
        assert len(cfg.partial_tp_tiers) == 2
        assert cfg.partial_tp_tiers[0] == (1.0, 0.33)  # TP1 at 1R
        assert cfg.partial_tp_tiers[1] == (2.0, 0.33)  # TP2 at 2R
        assert cfg.be_after_tp1 is True
        assert cfg.runner_trail_mode == "structure"

    def test_mr_engines_unchanged(self) -> None:
        for name in ["HYDRA", "NAUTILUS", "AEGEAN", "POSEIDON"]:
            cfg = get_engine_exit_config(name)
            assert cfg.trailing_enabled is False
            assert cfg.be_lock_enabled is False
            assert cfg.trail_atr_mult is None


class TestATRBasedTrailing:
    def test_atr_trailing_ratchets_up_long(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=True,
            trail_atr_mult=2.5,
            be_lock_enabled=False,
            unlimited_hold=True,
        )
        # Entry 100, SL 95, ATR pct = 2%
        # Trail distance = 100 * 0.02 * 2.5 = 5.0
        candles = [
            _candle(102.0, offset_h=1),  # new_sl = 102 - 5 = 97 > 95 → ratchet
            _candle(105.0, offset_h=2),  # new_sl = 105 - 5 = 100 > 97 → ratchet
            _candle(103.0, offset_h=3),  # new_sl = 103 - 5 = 98 < 100 → no ratchet
            _candle(106.0, offset_h=4),  # new_sl = 106 - 5 = 101 > 100 → ratchet
            _candle(104.0, low=100.5, offset_h=5),  # low=100.5 > 101? no → sl hit
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.exit_reason == REASON_TRAILING_STOP

    def test_atr_trailing_never_regresses(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=True,
            trail_atr_mult=2.0,
            be_lock_enabled=False,
            unlimited_hold=True,
        )
        # Entry 100, SL 96, ATR pct = 2%, trail dist = 4
        candles = [
            _candle(104.0, offset_h=1),  # sl = 104 - 4 = 100
            _candle(101.0, offset_h=2),  # sl = 101 - 4 = 97 < 100 → no regress
            _candle(103.0, offset_h=3),  # sl = 103 - 4 = 99 < 100 → no regress
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=96.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.final_sl >= 100.0  # Should never go below 100


class TestRBasedBreakevenLock:
    def test_be_lock_at_1_2r_long(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=True,
            be_trigger_r_mult=1.2,
            be_buffer_pct=0.001,
            unlimited_hold=True,
        )
        # Entry 100, SL 95 → R = 5. BE triggers at 100 + 5*1.2 = 106
        candles = [
            _candle(104.0, offset_h=1),  # no BE yet
            _candle(107.0, offset_h=2),  # close > 106 → BE lock
            _candle(102.0, low=100.0, offset_h=3),  # low touches BE SL
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.be_locked is True
        assert result.exit_reason == REASON_BREAKEVEN_STOP

    def test_be_lock_at_1_2r_short(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=True,
            be_trigger_r_mult=1.2,
            be_buffer_pct=0.001,
            unlimited_hold=True,
        )
        # Entry 100, SL 105 → R = 5. BE triggers at 100 - 5*1.2 = 94
        candles = [
            _candle(96.0, offset_h=1),
            _candle(93.0, offset_h=2),  # close < 94 → BE lock
            _candle(98.0, high=100.5, offset_h=3),  # high hits BE SL
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="short", entry_price=100.0,
            initial_stop_price=105.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.be_locked is True


class TestUnlimitedHold:
    def test_no_time_stop_with_unlimited_hold(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            max_hold_candles=5,
            unlimited_hold=True,
        )
        # 10 candles without SL hit — should NOT time-stop
        candles = [_candle(101.0 + i * 0.1, offset_h=i) for i in range(10)]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.exit_reason == REASON_TIME_EXIT  # No stop, exits at end
        assert result.candles_evaluated == 10

    def test_time_stop_without_unlimited_hold(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            max_hold_candles=5,
            unlimited_hold=False,
        )
        candles = [_candle(101.0, offset_h=i) for i in range(10)]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.exit_reason == REASON_TIME_STOP
        assert result.candles_evaluated == 5


class TestPartialTP:
    def test_partial_tp_recorded(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_enabled=True,
            partial_tp_r=1.5,
            partial_tp_fraction=0.5,
        )
        # Entry 100, SL 95 → R = 5. Partial at 100 + 5*1.5 = 107.5
        candles = [
            _candle(103.0, offset_h=1),
            _candle(108.0, offset_h=2),  # close > 107.5 → partial TP
            _candle(106.0, offset_h=3),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 1
        assert result.partial_exits[0].fraction == 0.5
        assert result.partial_exits[0].exit_price == 108.0

    def test_partial_tp_only_once(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_enabled=True,
            partial_tp_r=1.5,
            partial_tp_fraction=0.5,
        )
        candles = [
            _candle(108.0, offset_h=1),  # partial TP hit
            _candle(110.0, offset_h=2),  # should NOT trigger again
            _candle(109.0, offset_h=3),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.partial_exits is not None
        assert len(result.partial_exits) == 1  # Only once

    def test_no_partial_tp_when_disabled(self) -> None:
        cfg = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            unlimited_hold=True,
            partial_tp_enabled=False,
        )
        candles = [_candle(110.0, offset_h=i) for i in range(5)]
        result = evaluate_exit_bar_by_bar(
            candles=candles, side="long", entry_price=100.0,
            initial_stop_price=95.0, atr_pct=0.02, config=cfg,
        )
        assert result is not None
        assert result.partial_exits is None
