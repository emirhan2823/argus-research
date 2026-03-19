"""Parity tests: evaluate_exit_bar_by_bar vs backtest_simulator.SimulatedPosition.

Ensures the shared exit_policy module produces identical results to the
stateful SimulatedPosition + BacktestSimulator.on_candle() loop.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from src.backtest.backtest_simulator import (
    SimulatedPosition,
    BacktestSimulator,
    ENGINE_MAX_AGE,
    TRAILING_ENGINES,
    DEFAULT_MAX_AGE,
)
from src.backtest.exit_policy import (
    EngineExitConfig,
    evaluate_exit_bar_by_bar,
    get_engine_exit_config,
    REASON_STOP_LOSS,
    REASON_BREAKEVEN_STOP,
    REASON_TRAILING_STOP,
    REASON_TIME_STOP,
    REASON_TIME_EXIT,
)


# ─── Helpers ─────────────────────────────────────────────────────────

_BASE_TS = datetime(2024, 6, 1, tzinfo=timezone.utc)


def _make_candle_sequence() -> list[dict]:
    """20-candle sequence with a rally, pullback, and flat.

    Price: 100 → rises to ~108 → pulls back to ~103 → flat around 104.
    """
    raw = [
        # i, open, high, low, close
        (0, 100.0, 101.0, 99.5, 100.5),
        (1, 100.5, 102.0, 100.0, 101.5),
        (2, 101.5, 103.0, 101.0, 102.5),
        (3, 102.5, 104.5, 102.0, 104.0),
        (4, 104.0, 106.0, 103.5, 105.5),
        (5, 105.5, 108.0, 105.0, 107.5),
        (6, 107.5, 108.5, 106.5, 107.0),
        (7, 107.0, 107.5, 105.0, 105.5),
        (8, 105.5, 106.0, 104.0, 104.5),
        (9, 104.5, 105.0, 103.0, 103.5),
        (10, 103.5, 104.5, 103.0, 104.0),
        (11, 104.0, 105.0, 103.5, 104.5),
        (12, 104.5, 105.0, 103.5, 104.0),
        (13, 104.0, 104.5, 103.0, 103.5),
        (14, 103.5, 104.0, 103.0, 103.5),
        (15, 103.5, 104.0, 103.0, 103.5),
        (16, 103.5, 104.0, 102.5, 103.0),
        (17, 103.0, 103.5, 102.5, 103.0),
        (18, 103.0, 103.5, 102.5, 103.0),
        (19, 103.0, 103.5, 102.0, 102.5),
    ]
    return [
        {
            "timestamp": _BASE_TS + timedelta(minutes=15 * i),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1000.0,
        }
        for i, o, h, l, c in raw
    ]


def _run_simulator(
    candles: list[dict],
    side: str,
    engine: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    atr_pct: float,
) -> tuple[str, float, int]:
    """Run a single trade through BacktestSimulator's on_candle loop.

    Returns (exit_reason, exit_price, exit_candle_index).
    """
    sim = BacktestSimulator(
        initial_balance=100_000,
        be_trigger_atr_multiple=1.5,
        trail_pct=0.01,
    )
    pos = SimulatedPosition(
        trade_id="parity-001",
        symbol="TEST/USDT",
        side=side,
        engine=engine,
        regime="RANGING",
        entry_price=entry_price,
        size_usd=1000.0,
        leverage=5.0,
        sl_price=sl_price,
        tp_price=tp_price,
        current_sl=sl_price,
        opened_at=candles[0]["timestamp"],
    )
    sim.positions["parity-001"] = pos

    for i, c in enumerate(candles):
        closed = sim.on_candle(
            high=float(c["high"]),
            low=float(c["low"]),
            close=float(c["close"]),
            atr_pct=atr_pct,
            timestamp=c["timestamp"],
        )
        if closed:
            trade = closed[0]
            return trade.exit_reason, trade.exit_price, i

    # Still open after all candles — shouldn't happen with enough candles
    return "still_open", 0.0, len(candles)


# Configs that MATCH the simulator's behavior (trailing for POSEIDON, BE for all).
# These differ from ENGINE_EXIT_CONFIGS which has trailing+BE disabled for MR
# after validation findings (see EXIT_VALIDATION_SUMMARY.md).
_SIMULATOR_MATCHING_CONFIGS: dict[str, EngineExitConfig] = {
    "POSEIDON": EngineExitConfig(
        trailing_enabled=True, trail_pct=0.01,
        be_lock_enabled=True, be_trigger_atr_mult=1.5, be_buffer_pct=0.001,
        max_hold_candles=24,
    ),
    "HYDRA": EngineExitConfig(
        trailing_enabled=False,
        be_lock_enabled=True, be_trigger_atr_mult=1.5, be_buffer_pct=0.001,
        max_hold_candles=6,
    ),
    "AEGEAN": EngineExitConfig(
        trailing_enabled=False,
        be_lock_enabled=True, be_trigger_atr_mult=1.5, be_buffer_pct=0.001,
        max_hold_candles=8,
    ),
}


def _run_exit_policy(
    candles: list[dict],
    side: str,
    engine: str,
    entry_price: float,
    sl_price: float,
    atr_pct: float,
) -> tuple[str, float, int]:
    """Run the same trade through evaluate_exit_bar_by_bar.

    Uses simulator-matching configs to ensure parity test validity.
    Returns (exit_reason, exit_price, exit_candle_index).
    """
    config = _SIMULATOR_MATCHING_CONFIGS.get(engine, get_engine_exit_config(engine))
    result = evaluate_exit_bar_by_bar(
        candles=candles,
        side=side,
        entry_price=entry_price,
        initial_stop_price=sl_price,
        atr_pct=atr_pct,
        config=config,
    )
    if result is None:
        return "none", 0.0, -1
    return result.exit_reason, result.exit_price, result.exit_candle_index


# Map simulator exit reasons to compatible exit_policy reasons.
# The simulator uses "sl" for ALL stop-loss hits (including trailing-ratcheted),
# while exit_policy distinguishes trailing_stop_hit from stop_loss_hit.
# For parity: same exit price + same candle index is the critical check.
# Reason mapping is "compatible" not "identical".
_SL_COMPATIBLE_REASONS = {
    # Simulator "sl" can map to any of these in exit_policy
    REASON_STOP_LOSS,
    REASON_TRAILING_STOP,
}
_REASON_MAP = {
    "be_stop": {REASON_BREAKEVEN_STOP},
    "time_stop": {REASON_TIME_STOP},
    "sl": _SL_COMPATIBLE_REASONS,
}


# ─── Parity Tests ────────────────────────────────────────────────────


class TestExitParity:
    """Verify evaluate_exit_bar_by_bar matches SimulatedPosition behavior.

    Critical parity: same exit_price, same exit_candle_index.
    Reason: exit_policy has FINER-GRAINED reasons than simulator
    (e.g. trailing_stop_hit vs sl), so we check compatible sets.
    """

    @pytest.mark.parametrize(
        "engine,side,entry,sl,tp,atr_pct",
        [
            # POSEIDON long: trailing should engage on the rally
            ("POSEIDON", "long", 100.0, 96.0, 115.0, 0.02),
            # POSEIDON short: SL hit on the rally
            ("POSEIDON", "short", 100.0, 104.0, 88.0, 0.02),
            # HYDRA short: max_hold_candles=6 → time_stop
            ("HYDRA", "short", 108.0, 112.0, 95.0, 0.02),
            # AEGEAN long: max_hold_candles=8 → time_stop or SL
            ("AEGEAN", "long", 100.0, 96.0, 115.0, 0.02),
        ],
    )
    def test_parity(self, engine, side, entry, sl, tp, atr_pct):
        candles = _make_candle_sequence()

        sim_reason, sim_price, sim_idx = _run_simulator(
            candles, side, engine, entry, sl, tp, atr_pct,
        )
        pol_reason, pol_price, pol_idx = _run_exit_policy(
            candles, side, engine, entry, sl, atr_pct,
        )

        # Check compatible reason
        compatible = _REASON_MAP.get(sim_reason, {sim_reason})
        assert pol_reason in compatible, (
            f"Reason mismatch for {engine} {side}: "
            f"simulator={sim_reason}, policy={pol_reason}, "
            f"compatible={compatible}"
        )
        assert pol_price == pytest.approx(sim_price, abs=0.02), (
            f"Price mismatch for {engine} {side}: "
            f"simulator={sim_price}, policy={pol_price}"
        )
        assert pol_idx == sim_idx, (
            f"Candle index mismatch for {engine} {side}: "
            f"simulator={sim_idx}, policy={pol_idx}"
        )
