"""Tests for Stateful Backtest Simulator v5 — engine-aware."""

import pytest
from datetime import datetime, timezone, timedelta

from src.backtest.backtest_simulator import (
    BacktestSimulator,
    ClosedTrade,
    SimulatedPosition,
    VirtualAccount,
    TRAILING_ENGINES,
    ENGINE_MAX_AGE,
    DEFAULT_MAX_AGE,
)

_NOW = datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc)


def _ts(minutes: int = 0) -> datetime:
    return _NOW + timedelta(minutes=minutes)


# ── Helper: build an executed advisory output dict ──

def _signal(
    symbol="BTCUSDT",
    action="long",
    engine="NAUTILUS",
    entry=50000.0,
    sl_pct=0.01,
    tp_pct=0.02,
    leverage=2.0,
    size_pct=0.075,
    regime="RANGING",
    adx=15.0,
):
    return {
        "status": "executed",
        "reason": "advisory_signal_sent",
        "action": action,
        "symbol": symbol,
        "engine": engine,
        "suggested_entry_price": entry,
        "stop_loss_pct": sl_pct,
        "take_profit_pct": tp_pct,
        "leverage": leverage,
        "position_size_pct": size_pct,
        "gate_results": {
            "features_snapshot": {
                "regime": regime,
                "adx_14": adx,
                "atr_14_pct": 0.005,
            }
        },
    }


# ═══════════════════════════════════════════════════════════════════
# SimulatedPosition Tests
# ═══════════════════════════════════════════════════════════════════


class TestSimulatedPosition:
    """Unit tests for SimulatedPosition."""

    def _make(self, side="long", engine="NAUTILUS", regime="RANGING", **kw):
        defaults = dict(
            trade_id="bt-0001",
            symbol="BTCUSDT",
            side=side,
            engine=engine,
            regime=regime,
            entry_price=50000.0,
            size_usd=1000.0,
            leverage=2.0,
            sl_price=49500.0,
            tp_price=51000.0,
            current_sl=49500.0,
            opened_at=_NOW,
        )
        defaults.update(kw)
        return SimulatedPosition(**defaults)

    def test_has_engine_and_regime(self):
        pos = self._make(engine="HYDRA", regime="RANGING")
        assert pos.engine == "HYDRA"
        assert pos.regime == "RANGING"
        assert pos.candle_age == 0
        assert pos.adx == 0.0

    def test_sl_hit_long(self):
        pos = self._make()
        assert pos.check_exit(high=50500, low=49400, close=49500) == "sl"

    def test_tp_hit_long(self):
        pos = self._make()
        assert pos.check_exit(high=51100, low=50800, close=51000) == "tp"

    def test_sl_wins_when_both_hit(self):
        pos = self._make()
        assert pos.check_exit(high=51100, low=49400, close=50000) == "sl"

    def test_no_exit(self):
        pos = self._make()
        assert pos.check_exit(high=50500, low=49600, close=50000) is None

    def test_short_sl_hit(self):
        pos = self._make(
            side="short",
            sl_price=50500.0,
            tp_price=49000.0,
            current_sl=50500.0,
        )
        assert pos.check_exit(high=50600, low=50100, close=50300) == "sl"

    def test_short_tp_hit(self):
        pos = self._make(
            side="short",
            sl_price=50500.0,
            tp_price=49000.0,
            current_sl=50500.0,
        )
        assert pos.check_exit(high=49200, low=48900, close=49100) == "tp"

    def test_compute_pnl_long_profit(self):
        pos = self._make()
        pnl_usd, _ = pos.compute_pnl(51000.0)
        assert pnl_usd == pytest.approx(20.0, abs=0.1)

    def test_compute_pnl_long_loss(self):
        pos = self._make()
        pnl_usd, _ = pos.compute_pnl(49500.0)
        assert pnl_usd == pytest.approx(-10.0, abs=0.1)

    def test_breakeven_lock_long(self):
        pos = self._make()
        # Move well above entry + 1 ATR
        locked = pos.try_breakeven_lock(
            current_price=50600,
            atr_pct=0.005,
            trigger_multiple=1.0,
            fee_pct=0.001,
        )
        assert locked is True
        assert pos.be_locked is True
        assert pos.current_sl > pos.entry_price

    def test_breakeven_idempotent(self):
        pos = self._make()
        pos.try_breakeven_lock(current_price=50600, atr_pct=0.005, fee_pct=0.001)
        old_sl = pos.current_sl
        pos.try_breakeven_lock(current_price=50700, atr_pct=0.005, fee_pct=0.001)
        assert pos.current_sl == old_sl

    def test_trailing_stop_ratchets_up(self):
        pos = self._make(current_sl=49500)
        moved = pos.try_trailing_stop(current_price=51000, trail_pct=0.01)
        assert moved is True
        assert pos.current_sl == pytest.approx(50490.0)  # 51000 * 0.99

    def test_trailing_stop_never_goes_down(self):
        pos = self._make(current_sl=50800)
        moved = pos.try_trailing_stop(current_price=51000, trail_pct=0.01)
        assert moved is False  # 51000*0.99=50490 < 50800
        assert pos.current_sl == 50800


# ═══════════════════════════════════════════════════════════════════
# VirtualAccount Tests
# ═══════════════════════════════════════════════════════════════════


class TestVirtualAccount:
    def test_initial_balance(self):
        acc = VirtualAccount(initial_balance=5000)
        assert acc.balance == 5000
        assert acc.total_equity == 5000

    def test_lock_margin_reduces_balance(self):
        acc = VirtualAccount(initial_balance=10000)
        assert acc.lock_margin(2000) is True
        assert acc.balance == 8000
        assert acc.locked_margin == 2000

    def test_lock_margin_fails_insufficient(self):
        acc = VirtualAccount(initial_balance=1000)
        assert acc.lock_margin(2000) is False
        assert acc.balance == 1000

    def test_release_margin_with_profit(self):
        acc = VirtualAccount(initial_balance=10000)
        acc.lock_margin(2000)
        acc.release_margin(2000, 500)
        assert acc.balance == 10500
        assert acc.locked_margin == 0


# ═══════════════════════════════════════════════════════════════════
# BacktestSimulator Tests — v5
# ═══════════════════════════════════════════════════════════════════


class TestSimulatorSignalIntake:
    def test_rejects_non_advisory(self):
        sim = BacktestSimulator()
        result = sim.on_signal({"status": "rejected", "reason": "no_signal"}, _NOW)
        assert result is None

    def test_accepts_advisory_and_opens_position(self):
        sim = BacktestSimulator()
        tid = sim.on_signal(_signal(), _NOW)
        assert tid is not None
        assert tid.startswith("bt-")
        assert len(sim.positions) == 1

    def test_engine_and_regime_propagated(self):
        """v5: engine/regime/adx must be stored on position."""
        sim = BacktestSimulator()
        tid = sim.on_signal(_signal(engine="HYDRA", regime="VOLATILE", adx=25.5), _NOW)
        pos = sim.positions[tid]
        assert pos.engine == "HYDRA"
        assert pos.regime == "VOLATILE"
        assert pos.adx == 25.5
        assert pos.candle_age == 0

    def test_max_concurrent_positions(self):
        sim = BacktestSimulator(max_concurrent_positions=1)
        sim.on_signal(_signal(action="long"), _NOW)
        tid2 = sim.on_signal(_signal(action="short"), _ts(15))
        assert tid2 is None  # max_concurrent=1 already full

    def test_no_duplicate_same_direction(self):
        sim = BacktestSimulator(max_concurrent_positions=5)
        sim.on_signal(_signal(action="long"), _NOW)
        tid2 = sim.on_signal(_signal(action="long"), _ts(15))
        assert tid2 is None


class TestSimulatorCandle:
    def test_sl_closes_position(self):
        sim = BacktestSimulator()
        sim.on_signal(_signal(entry=50000, sl_pct=0.01, tp_pct=0.05), _NOW)
        closed = sim.on_candle(high=50100, low=49400, close=49500, atr_pct=0.005, timestamp=_ts(15))
        assert len(closed) == 1
        assert closed[0].exit_reason == "sl"

    def test_tp_closes_position(self):
        sim = BacktestSimulator()
        sim.on_signal(_signal(entry=50000, sl_pct=0.01, tp_pct=0.02), _NOW)
        closed = sim.on_candle(high=51500, low=50800, close=51200, atr_pct=0.005, timestamp=_ts(15))
        assert len(closed) == 1
        assert closed[0].exit_reason == "tp"

    def test_be_stop_reason(self):
        """SL hit after BE lock should report 'be_stop'."""
        sim = BacktestSimulator(be_trigger_atr_multiple=1.0)
        sim.on_signal(_signal(entry=50000, sl_pct=0.02, tp_pct=0.05), _NOW)
        # First candle: pump triggers BE
        sim.on_candle(high=50400, low=50200, close=50350, atr_pct=0.005, timestamp=_ts(15))
        # After BE lock, SL is at ~entry+fees. Pull back to hit it.
        closed = sim.on_candle(high=50100, low=49800, close=49900, atr_pct=0.005, timestamp=_ts(30))
        assert len(closed) == 1
        assert closed[0].exit_reason == "be_stop"

    def test_candle_age_increments(self):
        """v5: candle_age must increment each on_candle call."""
        sim = BacktestSimulator()
        tid = sim.on_signal(_signal(entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        for i in range(5):
            sim.on_candle(high=50100, low=49900, close=50000, atr_pct=0.005, timestamp=_ts(15 * (i + 1)))
        assert sim.positions[tid].candle_age == 5


class TestTimeStop:
    """v5: per-engine time stop."""

    def test_hydra_closes_at_max_age(self):
        sim = BacktestSimulator()
        tid = sim.on_signal(_signal(engine="HYDRA", entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        max_age = ENGINE_MAX_AGE["HYDRA"]  # 6
        # Candles 1 through 5: no exit
        for i in range(max_age - 1):
            closed = sim.on_candle(high=50100, low=49900, close=50000, atr_pct=0.005, timestamp=_ts(15 * (i + 1)))
            assert len(closed) == 0
        # Candle 6: time_stop
        closed = sim.on_candle(high=50100, low=49900, close=50050, atr_pct=0.005, timestamp=_ts(15 * max_age))
        assert len(closed) == 1
        assert closed[0].exit_reason == "time_stop"
        assert closed[0].duration_candles == max_age
        assert closed[0].exit_price == 50050  # close price for time_stop

    def test_nautilus_lasts_longer(self):
        sim = BacktestSimulator()
        sim.on_signal(_signal(engine="NAUTILUS", entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        # After 6 candles (HYDRA limit), NAUTILUS should still be open
        for i in range(6):
            sim.on_candle(high=50100, low=49900, close=50000, atr_pct=0.005, timestamp=_ts(15 * (i + 1)))
        assert len(sim.positions) == 1  # still open

    def test_poseidon_24_candle_limit(self):
        sim = BacktestSimulator()
        sim.on_signal(_signal(engine="POSEIDON", entry=50000, sl_pct=0.10, tp_pct=0.10, regime="TRENDING"), _NOW)
        for i in range(23):
            sim.on_candle(high=50100, low=49900, close=50000, atr_pct=0.005, timestamp=_ts(15 * (i + 1)))
        assert len(sim.positions) == 1
        closed = sim.on_candle(high=50100, low=49900, close=50000, atr_pct=0.005, timestamp=_ts(15 * 24))
        assert len(closed) == 1
        assert closed[0].exit_reason == "time_stop"


class TestEngineConditionalTrailing:
    """v5: trailing stop only for POSEIDON."""

    def test_poseidon_gets_trailing(self):
        sim = BacktestSimulator(trail_pct=0.01)
        sim.on_signal(_signal(engine="POSEIDON", entry=50000, sl_pct=0.10, tp_pct=0.10, regime="TRENDING"), _NOW)
        tid = list(sim.positions.keys())[0]
        original_sl = sim.positions[tid].current_sl
        # Big pump → trailing should ratchet SL up
        sim.on_candle(high=52000, low=51500, close=51800, atr_pct=0.005, timestamp=_ts(15))
        assert sim.positions[tid].current_sl > original_sl

    def test_nautilus_no_trailing(self):
        sim = BacktestSimulator(trail_pct=0.01)
        sim.on_signal(_signal(engine="NAUTILUS", entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        tid = list(sim.positions.keys())[0]
        original_sl = sim.positions[tid].current_sl
        # Pump: trailing should NOT move SL (non-trend engine)
        sim.on_candle(high=52000, low=51500, close=51800, atr_pct=0.005, timestamp=_ts(15))
        # SL might move from BE lock, but not from trailing
        # With atr_pct=0.005 and 1.5x trigger, need 50000*0.005*1.5=375 move
        # 51800 > 50375 → BE engages at ~50100. But trailing should NOT engage.
        # Reset: test without BE
        sim2 = BacktestSimulator(trail_pct=0.01, be_trigger_atr_multiple=100.0)
        sim2.on_signal(_signal(engine="NAUTILUS", entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        tid2 = list(sim2.positions.keys())[0]
        original_sl2 = sim2.positions[tid2].current_sl
        sim2.on_candle(high=52000, low=51500, close=51800, atr_pct=0.005, timestamp=_ts(15))
        assert sim2.positions[tid2].current_sl == original_sl2

    def test_hydra_no_trailing(self):
        sim = BacktestSimulator(trail_pct=0.01, be_trigger_atr_multiple=100.0)
        sim.on_signal(_signal(engine="HYDRA", entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        tid = list(sim.positions.keys())[0]
        original_sl = sim.positions[tid].current_sl
        sim.on_candle(high=52000, low=51500, close=51800, atr_pct=0.005, timestamp=_ts(15))
        assert sim.positions[tid].current_sl == original_sl


class TestEngineBreakdown:
    """v5: engine breakdown in tear sheet."""

    def _run_mixed_trades(self):
        sim = BacktestSimulator(be_trigger_atr_multiple=100.0)

        # NAUTILUS trade → TP hit
        sim.on_signal(_signal(engine="NAUTILUS", entry=50000, sl_pct=0.10, tp_pct=0.02), _NOW)
        sim.on_candle(high=51500, low=50800, close=51200, atr_pct=0.005, timestamp=_ts(15))

        # HYDRA trade → SL hit
        sim.on_signal(_signal(engine="HYDRA", entry=50000, sl_pct=0.01, tp_pct=0.10), _ts(30))
        sim.on_candle(high=50100, low=49400, close=49500, atr_pct=0.005, timestamp=_ts(45))

        return sim

    def test_engine_breakdown_exists(self):
        sim = self._run_mixed_trades()
        ts = sim.tear_sheet()
        assert "engine_breakdown" in ts
        assert "NAUTILUS" in ts["engine_breakdown"]
        assert "HYDRA" in ts["engine_breakdown"]

    def test_engine_breakdown_counts(self):
        sim = self._run_mixed_trades()
        eb = sim.tear_sheet()["engine_breakdown"]
        assert eb["NAUTILUS"]["trades"] == 1
        assert eb["NAUTILUS"]["wins"] == 1
        assert eb["HYDRA"]["trades"] == 1
        assert eb["HYDRA"]["losses"] == 1

    def test_engine_breakdown_profit_factor(self):
        sim = self._run_mixed_trades()
        eb = sim.tear_sheet()["engine_breakdown"]
        assert eb["NAUTILUS"]["profit_factor"] == float("inf")  # no losses
        assert eb["HYDRA"]["profit_factor"] == 0.0  # no wins

    def test_engine_breakdown_exit_reasons(self):
        sim = self._run_mixed_trades()
        eb = sim.tear_sheet()["engine_breakdown"]
        assert eb["NAUTILUS"]["exit_reasons"]["tp"] == 1
        assert eb["HYDRA"]["exit_reasons"]["sl"] == 1

    def test_duration_candles_recorded(self):
        sim = self._run_mixed_trades()
        trades = sim.account.closed_trades
        for t in trades:
            assert t.duration_candles >= 1

    def test_engine_propagated_to_closed_trade(self):
        sim = self._run_mixed_trades()
        for t in sim.account.closed_trades:
            assert t.engine in ("NAUTILUS", "HYDRA")
            assert t.regime == "RANGING"

    def test_time_stop_in_exit_reasons(self):
        sim = BacktestSimulator()
        sim.on_signal(_signal(engine="HYDRA", entry=50000, sl_pct=0.10, tp_pct=0.10), _NOW)
        for i in range(ENGINE_MAX_AGE["HYDRA"]):
            sim.on_candle(high=50100, low=49900, close=50000, atr_pct=0.005, timestamp=_ts(15 * (i + 1)))
        ts = sim.tear_sheet()
        assert "time_stop" in ts["exit_reasons"]
        assert ts["engine_breakdown"]["HYDRA"]["exit_reasons"]["time_stop"] == 1


class TestTearSheet:
    def test_empty_tear_sheet(self):
        sim = BacktestSimulator()
        ts = sim.tear_sheet()
        assert ts["total_trades"] == 0
        assert ts["engine_breakdown"] == {}

    def test_tear_sheet_basic_metrics(self):
        sim = BacktestSimulator(be_trigger_atr_multiple=100.0)
        sim.on_signal(_signal(entry=50000, sl_pct=0.10, tp_pct=0.02), _NOW)
        sim.on_candle(high=51500, low=50800, close=51200, atr_pct=0.005, timestamp=_ts(15))
        ts = sim.tear_sheet()
        assert ts["total_trades"] == 1
        assert ts["wins"] == 1
        assert ts["total_pnl_usd"] > 0

    def test_tear_sheet_has_engine_breakdown(self):
        sim = BacktestSimulator(be_trigger_atr_multiple=100.0)
        sim.on_signal(_signal(engine="POSEIDON", entry=50000, sl_pct=0.10, tp_pct=0.02, regime="TRENDING"), _NOW)
        sim.on_candle(high=51500, low=50800, close=51200, atr_pct=0.005, timestamp=_ts(15))
        ts = sim.tear_sheet()
        assert "POSEIDON" in ts["engine_breakdown"]
        eb = ts["engine_breakdown"]["POSEIDON"]
        assert eb["trades"] == 1
        assert "avg_duration_candles" in eb
