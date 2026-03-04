"""Unit tests for src/backtest/exit_policy.py — shared exit evaluation."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from src.backtest.exit_policy import (
    EngineExitConfig,
    ExitResult,
    ENGINE_EXIT_CONFIGS,
    DEFAULT_EXIT_CONFIG,
    REASON_STOP_LOSS,
    REASON_BREAKEVEN_STOP,
    REASON_TRAILING_STOP,
    REASON_TIME_STOP,
    REASON_TIME_EXIT,
    evaluate_exit_bar_by_bar,
    get_engine_exit_config,
)


# ─── Helpers ─────────────────────────────────────────────────────────

_BASE_TS = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _candle(
    i: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> dict:
    return {
        "timestamp": _BASE_TS + timedelta(minutes=15 * i),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 100.0,
    }


def _flat_candles(n: int, price: float = 100.0, spread: float = 0.5) -> list[dict]:
    """Generate *n* candles that stay within a tight range around *price*."""
    return [
        _candle(i, price, price + spread, price - spread, price)
        for i in range(n)
    ]


# ─── Config Lookup ───────────────────────────────────────────────────


class TestEngineConfig:
    def test_known_engine_returns_specific_config(self):
        cfg = get_engine_exit_config("POSEIDON")
        assert cfg.trailing_enabled is False  # disabled for MR engines after validation
        assert cfg.be_lock_enabled is False
        assert cfg.max_hold_candles == 24

    def test_unknown_engine_uses_default(self):
        cfg = get_engine_exit_config("NONEXISTENT_ENGINE_XYZ")
        assert cfg is DEFAULT_EXIT_CONFIG
        assert cfg.trailing_enabled is False
        assert cfg.max_hold_candles == 16

    def test_all_registered_engines(self):
        for name in ("HYDRA", "NAUTILUS", "AEGEAN", "POSEIDON", "TITAN"):
            assert name in ENGINE_EXIT_CONFIGS


# ─── Basic SL Hit ────────────────────────────────────────────────────


class TestSLHit:
    def test_sl_hit_basic_long(self):
        """Long SL hit when candle low <= stop price."""
        entry = 100.0
        sl_price = 98.0  # 2% below
        candles = [
            _candle(0, 100, 101, 99.5, 100.5),  # low=99.5 > 98 → no hit
            _candle(1, 100.5, 101, 97.5, 98.5),  # low=97.5 <= 98 → HIT
            _candle(2, 98.5, 99, 97, 98),
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=sl_price,
            atr_pct=0.0,
            config=EngineExitConfig(be_lock_enabled=False, max_hold_candles=99),
        )
        assert result is not None
        assert result.exit_reason == REASON_STOP_LOSS
        assert result.exit_price == pytest.approx(sl_price)
        assert result.exit_candle_index == 1
        assert result.candles_evaluated == 2

    def test_sl_hit_basic_short(self):
        """Short SL hit when candle high >= stop price."""
        entry = 100.0
        sl_price = 102.0  # 2% above
        candles = [
            _candle(0, 100, 101.5, 99, 100),  # high=101.5 < 102 → no hit
            _candle(1, 100, 102.5, 99.5, 101),  # high=102.5 >= 102 → HIT
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="short",
            entry_price=entry,
            initial_stop_price=sl_price,
            atr_pct=0.0,
            config=EngineExitConfig(be_lock_enabled=False, max_hold_candles=99),
        )
        assert result is not None
        assert result.exit_reason == REASON_STOP_LOSS
        assert result.exit_price == pytest.approx(sl_price)
        assert result.exit_candle_index == 1


# ─── Time Exits ──────────────────────────────────────────────────────


class TestTimeExits:
    def test_no_exit_returns_time_exit(self):
        """When no SL/TP hit and under max candles → time_exit at last close."""
        candles = _flat_candles(5, price=100.0, spread=0.2)
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=100.0,
            initial_stop_price=95.0,  # far away
            atr_pct=0.0,
            config=EngineExitConfig(be_lock_enabled=False, max_hold_candles=99),
        )
        assert result is not None
        assert result.exit_reason == REASON_TIME_EXIT
        assert result.exit_candle_index == 4  # last candle
        assert result.exit_price == pytest.approx(100.0)

    def test_candle_age_time_stop(self):
        """Engine max_hold_candles reached → time_stop_hit at close."""
        max_candles = 6
        candles = _flat_candles(10, price=100.0, spread=0.2)
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=100.0,
            initial_stop_price=95.0,
            atr_pct=0.0,
            config=EngineExitConfig(
                be_lock_enabled=False, max_hold_candles=max_candles,
            ),
        )
        assert result is not None
        assert result.exit_reason == REASON_TIME_STOP
        # candle_age increments per candle, so at index max_candles-1 age==max_candles
        assert result.exit_candle_index == max_candles - 1
        assert result.candles_evaluated == max_candles


# ─── Breakeven Lock ──────────────────────────────────────────────────


class TestBreakevenLock:
    def test_breakeven_lock_triggers(self):
        """Price moves 1.5× ATR → SL snaps to entry+buffer, then SL hit → breakeven_stop_hit."""
        entry = 100.0
        atr_pct = 0.02  # 2% ATR
        # BE trigger at entry + 1.5 * 2% * 100 = 103.0
        # BE price = 100 * (1 + 2*0.001) = 100.2
        initial_sl = 96.0  # original SL
        candles = [
            _candle(0, 100, 101, 99, 100.5),  # close=100.5, < 103 → no BE
            _candle(1, 101, 104, 100.5, 103.5),  # close=103.5 >= 103 → BE LOCK
            _candle(2, 103, 103.5, 99.5, 100),  # low=99.5 < BE price 100.2 → HIT
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=atr_pct,
            config=EngineExitConfig(
                be_lock_enabled=True,
                be_trigger_atr_mult=1.5,
                be_buffer_pct=0.001,
                trailing_enabled=False,
                max_hold_candles=99,
            ),
        )
        assert result is not None
        assert result.exit_reason == REASON_BREAKEVEN_STOP
        assert result.be_locked is True
        assert result.exit_price == pytest.approx(100.2)

    def test_atr_zero_disables_be_lock(self):
        """atr_pct=0 → BE lock never triggers even with favorable price."""
        entry = 100.0
        initial_sl = 96.0
        candles = [
            _candle(0, 100, 110, 99, 108),  # huge move in favor
            _candle(1, 108, 108, 95, 95.5),  # low hits original SL
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=0.0,  # no ATR → no BE
            config=EngineExitConfig(
                be_lock_enabled=True,
                be_trigger_atr_mult=1.5,
                trailing_enabled=False,
                max_hold_candles=99,
            ),
        )
        assert result is not None
        assert result.exit_reason == REASON_STOP_LOSS  # not breakeven
        assert result.be_locked is False
        assert result.exit_price == pytest.approx(initial_sl)


# ─── Trailing Stop ───────────────────────────────────────────────────


class TestTrailingStop:
    def test_trailing_ratchets_long(self):
        """POSEIDON long: price rises, trail locks below peak, then retrace hits trail."""
        entry = 100.0
        initial_sl = 97.0
        trail_pct = 0.01  # 1%
        # Trail ratchets on close, SL checks on wick (same candle).
        # Candle lows must stay ABOVE ratcheted trail each candle.
        # Peak at close=104 → trail SL = 104*0.99 = 102.96
        candles = [
            _candle(0, 100, 101, 100.2, 101),   # trail = 99.99 > 97 → ratchet; low=100.2 > 99.99 ✓
            _candle(1, 101, 103, 102.0, 103),    # trail = 101.97; low=102.0 > 101.97 ✓
            _candle(2, 103, 104, 103.0, 104),    # trail = 102.96; low=103.0 > 102.96 ✓
            _candle(3, 104, 104.5, 103.0, 103),  # trail stays 102.96 (103*0.99=101.97 < 102.96)
            _candle(4, 103, 103, 102.0, 102.5),  # low=102.0 <= 102.96 → HIT
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=0.0,
            config=EngineExitConfig(
                trailing_enabled=True,
                trail_pct=trail_pct,
                be_lock_enabled=False,
                max_hold_candles=99,
            ),
        )
        assert result is not None
        assert result.exit_reason == REASON_TRAILING_STOP
        assert result.exit_price == pytest.approx(102.96, abs=0.01)
        assert result.exit_candle_index == 4

    def test_trailing_ratchets_short(self):
        """Short trailing: price falls, trail locks above trough, then retrace hits."""
        entry = 100.0
        initial_sl = 103.0
        trail_pct = 0.01
        # For short: trail = close * 1.01. Each candle's high must stay BELOW
        # the ratcheted trail for no immediate hit.
        # Trough at close=96 → trail = 96*1.01 = 96.96
        candles = [
            _candle(0, 98.5, 98.5, 97, 98),     # trail = 98*1.01=98.98; high=98.5 < 98.98 ✓
            _candle(1, 98, 97.5, 96, 97),        # trail = 97*1.01=97.97; high=97.5 < 97.97 ✓
            _candle(2, 97, 96.5, 95, 96),         # trail = 96*1.01=96.96; high=96.5 < 96.96 ✓
            _candle(3, 96, 97.5, 96, 97),          # high=97.5 >= 96.96 → HIT
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="short",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=0.0,
            config=EngineExitConfig(
                trailing_enabled=True,
                trail_pct=trail_pct,
                be_lock_enabled=False,
                max_hold_candles=99,
            ),
        )
        assert result is not None
        assert result.exit_reason == REASON_TRAILING_STOP
        assert result.exit_price == pytest.approx(96.96, abs=0.01)

    def test_trailing_disabled_non_trailing_engine(self):
        """NAUTILUS (trailing=False) → trailing never engages, SL stays at initial."""
        entry = 100.0
        initial_sl = 97.0
        candles = [
            _candle(0, 100, 105, 99.5, 105),  # huge move up, but no trailing
            _candle(1, 105, 106, 96.5, 97.5),  # low=96.5 <= initial SL 97 → SL hit
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=0.0,
            config=get_engine_exit_config("NAUTILUS"),
        )
        assert result is not None
        assert result.exit_reason == REASON_STOP_LOSS  # plain SL, not trailing
        assert result.exit_price == pytest.approx(initial_sl)

    def test_be_lock_then_trailing(self):
        """BE lock engages first, then trailing ratchets SL further → trailing_stop_hit."""
        entry = 100.0
        initial_sl = 96.0
        atr_pct = 0.02  # BE trigger: entry + 1.5*0.02*100 = 103.0
        trail_pct = 0.01
        # BE price = 100*(1+2*0.001) = 100.2
        # After BE, trailing takes over: close*0.99 must be > BE price (100.2)
        # close=103.5 → trail=102.465 > 100.2 ✓
        # close=106 → trail=104.94
        # Candle lows must stay above the ratcheted trail each time.
        candles = [
            _candle(0, 100, 101, 100.5, 101),     # no BE (101 < 103), trail=99.99>96→ratchet; low=100.5>99.99 ✓
            _candle(1, 101, 104, 102.0, 103.5),    # BE lock (103.5>=103): SL→100.2; trail=102.465>100.2→ratchet; low=102.0<102.465?
        ]
        # Hmm, candle 1: trail=103.5*0.99=102.465, low=102.0 <= 102.465 → HIT.
        # Need low > 102.465 on candle 1. Use low=102.5.
        candles = [
            _candle(0, 100, 101, 100.5, 101),     # trail=99.99; low=100.5>99.99 ✓
            _candle(1, 101, 104, 102.5, 103.5),    # BE lock; trail=102.465; low=102.5>102.465 ✓
            _candle(2, 103.5, 106, 105.0, 106),    # trail=104.94; low=105.0>104.94 ✓
            _candle(3, 106, 106.5, 104.0, 104.5),  # low=104.0 <= 104.94 → HIT
        ]
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=atr_pct,
            config=EngineExitConfig(
                trailing_enabled=True,
                trail_pct=trail_pct,
                be_lock_enabled=True,
                be_trigger_atr_mult=1.5,
                be_buffer_pct=0.001,
                max_hold_candles=99,
            ),
        )
        assert result is not None
        assert result.exit_reason == REASON_TRAILING_STOP
        assert result.be_locked is True
        assert result.exit_price == pytest.approx(104.94, abs=0.01)


# ─── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_candles_returns_none(self):
        result = evaluate_exit_bar_by_bar(
            candles=[],
            side="long",
            entry_price=100.0,
            initial_stop_price=97.0,
            atr_pct=0.0,
            config=DEFAULT_EXIT_CONFIG,
        )
        assert result is None

    def test_backward_compat_all_disabled(self):
        """All features disabled → behaves like old SL-only check."""
        entry = 100.0
        initial_sl = 97.0
        candles = [
            _candle(0, 100, 105, 99.5, 105),  # big up, but no trailing/BE
            _candle(1, 105, 106, 96.5, 97.5),  # low hits SL
        ]
        config = EngineExitConfig(
            trailing_enabled=False,
            be_lock_enabled=False,
            max_hold_candles=9999,
        )
        result = evaluate_exit_bar_by_bar(
            candles=candles,
            side="long",
            entry_price=entry,
            initial_stop_price=initial_sl,
            atr_pct=0.02,
            config=config,
        )
        assert result is not None
        assert result.exit_reason == REASON_STOP_LOSS
        assert result.exit_price == pytest.approx(initial_sl)

    def test_canonical_exit_reasons_are_strings(self):
        """Verify all reason constants are the expected strings."""
        assert REASON_STOP_LOSS == "stop_loss_hit"
        assert REASON_BREAKEVEN_STOP == "breakeven_stop_hit"
        assert REASON_TRAILING_STOP == "trailing_stop_hit"
        assert REASON_TIME_STOP == "time_stop_hit"
        assert REASON_TIME_EXIT == "time_exit_backtest_sim"
