"""Shared bar-by-bar exit evaluation for both backtest paths.

Pure functions — no mutable state between calls.
Matches the evaluation order of ``backtest_simulator.py``'s
``SimulatedPosition`` + ``BacktestSimulator.on_candle()`` exactly:

    Per candle:
      a) candle_age += 1
      b) BE lock check using CLOSE only
      b2) Multi-tier TP check (or single partial TP)
      c) Trailing ratchet using CLOSE only (structure/ATR/pct)
      d) SL wick hit using LOW (long) / HIGH (short)
      e) Time-stop if candle_age >= max_hold_candles → exit at CLOSE

If nothing hits → ``time_exit_backtest_sim`` at last candle CLOSE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

_LOG = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Engine Exit Configs
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EngineExitConfig:
    """Per-engine exit behavior parameters."""

    trailing_enabled: bool = False
    trail_pct: float = 0.01  # 1% default trailing distance
    trail_atr_mult: float | None = None  # ATR-based trailing (overrides trail_pct)
    be_lock_enabled: bool = True
    be_trigger_atr_mult: float = 1.5  # price must move 1.5× ATR before BE lock
    be_trigger_r_mult: float | None = None  # BE lock at N×R (overrides ATR-based)
    be_buffer_pct: float = 0.001  # buffer for BE price (≈ 2× fees)
    max_hold_candles: int = 16  # time-stop in candle count
    unlimited_hold: bool = False  # disable time stop
    partial_tp_enabled: bool = False  # single-tier partial take-profit
    partial_tp_r: float = 1.5  # take partial at N×R
    partial_tp_fraction: float = 0.5  # fraction to close (0.5 = 50%)

    # Multi-tier partial TP (overrides single partial_tp_* when non-empty)
    # Each tuple: (r_multiple, close_fraction)
    # Example: ((1.0, 0.33), (2.0, 0.33)) → TP1 at 1R close 33%, TP2 at 2R close 33%
    partial_tp_tiers: tuple[tuple[float, float], ...] = ()

    # BE lock after first TP tier (move SL to entry + fees)
    be_after_tp1: bool = False
    be_after_tp1_buffer_pct: float = 0.002  # entry ± buffer (≈ round-trip fees)

    # Runner trailing mode: "atr" | "structure"
    runner_trail_mode: str = "atr"
    runner_trail_atr_mult: float = 2.0  # tighter ATR mult for runner
    runner_atr_buffer: float = 0.3  # ATR fraction buffer for structure trailing


# Registry — matches backtest_simulator.py ENGINE_MAX_AGE / TRAILING_ENGINES
# NOTE: Trailing + BE lock DISABLED for all MR engines after validation
# (EXIT_VALIDATION_SUMMARY.md: trailing destroys edge for MR, -0.41bps expectancy).
# Reserve trailing for trend-following engines (TITAN verified_trend).
ENGINE_EXIT_CONFIGS: dict[str, EngineExitConfig] = {
    "HYDRA": EngineExitConfig(trailing_enabled=False, be_lock_enabled=False, max_hold_candles=6),
    "NAUTILUS": EngineExitConfig(trailing_enabled=False, be_lock_enabled=False, max_hold_candles=12),
    "AEGEAN": EngineExitConfig(trailing_enabled=False, be_lock_enabled=False, max_hold_candles=8),
    "POSEIDON": EngineExitConfig(trailing_enabled=False, be_lock_enabled=False, max_hold_candles=24),
    "TITAN": EngineExitConfig(
        trailing_enabled=True,
        trail_atr_mult=2.5,
        be_lock_enabled=False,
        unlimited_hold=True,
        partial_tp_enabled=False,
        partial_tp_tiers=(
            (1.0, 0.33),   # TP1: 1R → close 33%
            (2.0, 0.33),   # TP2: 2R → close 33%
        ),                  # Runner: remaining 34%
        be_after_tp1=True,
        be_after_tp1_buffer_pct=0.002,
        runner_trail_mode="structure",
        runner_trail_atr_mult=2.0,
        runner_atr_buffer=0.3,
    ),
}

DEFAULT_EXIT_CONFIG = EngineExitConfig()  # trailing=False, max=16


def get_engine_exit_config(engine: str) -> EngineExitConfig:
    """Lookup config for *engine*. Never raises KeyError."""
    return ENGINE_EXIT_CONFIGS.get(engine, DEFAULT_EXIT_CONFIG)


# ─────────────────────────────────────────────────────────────────────
# Exit Result
# ─────────────────────────────────────────────────────────────────────

# Canonical exit_reason strings (R1)
REASON_STOP_LOSS = "stop_loss_hit"
REASON_BREAKEVEN_STOP = "breakeven_stop_hit"
REASON_TRAILING_STOP = "trailing_stop_hit"
REASON_TIME_STOP = "time_stop_hit"
REASON_TIME_EXIT = "time_exit_backtest_sim"
REASON_PARTIAL_TP = "partial_tp_hit"


@dataclass
class PartialExit:
    """A partial take-profit event during the trade."""

    fraction: float  # 0.5 = 50%
    exit_price: float
    exit_time: datetime
    candle_index: int


@dataclass
class ExitResult:
    """Result of bar-by-bar exit evaluation."""

    exit_price: float
    exit_time: datetime
    exit_reason: str  # one of REASON_* constants
    exit_candle_index: int  # 0-based index into candles list
    final_sl: float  # SL level at exit
    be_locked: bool  # was breakeven lock ever engaged?
    candles_evaluated: int  # total candles processed
    partial_exits: list[PartialExit] | None = None  # partial TP events


# ─────────────────────────────────────────────────────────────────────
# Structure Trailing Helper
# ─────────────────────────────────────────────────────────────────────


def _find_swing_low(lows: list[float], end: int, lookback: int = 20) -> float | None:
    """Find the last higher-low (swing low) in recent data for long trailing.

    Uses simple 3-bar pivot detection: lows[i] < lows[i-1] and lows[i] < lows[i+1].
    Returns the most recent swing low price, or None.
    """
    start = max(0, end - lookback)
    if end - start < 3:
        return None
    best = None
    for i in range(start + 1, end - 1):
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            best = lows[i]  # keep updating → last (most recent) wins
    return best


def _find_swing_high(highs: list[float], end: int, lookback: int = 20) -> float | None:
    """Find the last lower-high (swing high) in recent data for short trailing.

    Uses simple 3-bar pivot detection: highs[i] > highs[i-1] and highs[i] > highs[i+1].
    Returns the most recent swing high price, or None.
    """
    start = max(0, end - lookback)
    if end - start < 3:
        return None
    best = None
    for i in range(start + 1, end - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            best = highs[i]
    return best


def _structure_trail_level(
    highs: list[float],
    lows: list[float],
    current_index: int,
    side: str,
    atr_value: float,
    atr_buffer: float = 0.3,
    lookback: int = 20,
) -> float | None:
    """Compute structure-based trailing stop level.

    For long: last swing low - ATR buffer.
    For short: last swing high + ATR buffer.
    Returns None if no swing found (caller should fallback to ATR trailing).
    """
    buffer = atr_value * atr_buffer
    if side == "long":
        swing = _find_swing_low(lows, current_index, lookback)
        if swing is not None:
            return swing - buffer
    else:
        swing = _find_swing_high(highs, current_index, lookback)
        if swing is not None:
            return swing + buffer
    return None


# ─────────────────────────────────────────────────────────────────────
# Core Evaluation
# ─────────────────────────────────────────────────────────────────────


def evaluate_exit_bar_by_bar(
    *,
    candles: list[dict],
    side: str,
    entry_price: float,
    initial_stop_price: float,
    atr_pct: float,
    config: EngineExitConfig,
    candle_highs: list[float] | None = None,
    candle_lows: list[float] | None = None,
) -> ExitResult | None:
    """Iterate *candles* bar-by-bar with full exit logic.

    Parameters
    ----------
    candles:
        List of dicts with at least ``timestamp``, ``high``, ``low``, ``close``.
    side:
        ``"long"`` or ``"short"``.
    entry_price:
        Trade entry price.
    initial_stop_price:
        Initial stop-loss price (``entry * (1 ± stop_distance)``).
    atr_pct:
        ATR as fraction of price at entry.  ``0`` → BE lock disabled (R2).
    config:
        Engine-specific exit configuration.
    candle_highs:
        Full high prices list for structure trailing (optional).
    candle_lows:
        Full low prices list for structure trailing (optional).

    Returns
    -------
    ``ExitResult`` or ``None`` if *candles* is empty.
    """
    if not candles:
        return None

    current_sl = initial_stop_price
    be_locked = False
    candle_age = 0
    trailing_ratcheted = False
    partial_tp_taken = False
    partial_exits: list[PartialExit] = []

    # Pre-compute R distance for R-based features
    r_distance = abs(entry_price - initial_stop_price)

    # Multi-tier TP state
    use_tiers = len(config.partial_tp_tiers) > 0
    tiers_filled = 0  # how many tiers have been triggered
    runner_active = False  # all tiers done → runner mode

    for i, candle in enumerate(candles):
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        ts = candle["timestamp"]

        # a) Increment candle age
        candle_age += 1

        # b) Breakeven lock using CLOSE only (for engines using legacy BE)
        if config.be_lock_enabled and not be_locked:
            be_triggered = False
            if config.be_trigger_r_mult is not None and r_distance > 0:
                target_move = r_distance * config.be_trigger_r_mult
                if side == "long":
                    be_triggered = close >= entry_price + target_move
                else:
                    be_triggered = close <= entry_price - target_move
            elif atr_pct > 0:
                atr_distance = entry_price * atr_pct * config.be_trigger_atr_mult
                if side == "long":
                    be_triggered = close >= entry_price + atr_distance
                else:
                    be_triggered = close <= entry_price - atr_distance

            if be_triggered:
                if side == "long":
                    be_price = entry_price * (1 + 2 * config.be_buffer_pct)
                    if be_price > current_sl:
                        current_sl = be_price
                        be_locked = True
                else:
                    be_price = entry_price * (1 - 2 * config.be_buffer_pct)
                    if be_price < current_sl:
                        current_sl = be_price
                        be_locked = True

        # b2) Multi-tier TP check
        if use_tiers and r_distance > 0 and tiers_filled < len(config.partial_tp_tiers):
            tier_r, tier_frac = config.partial_tp_tiers[tiers_filled]
            tp_target = r_distance * tier_r
            if side == "long":
                hit = close >= entry_price + tp_target
            else:
                hit = close <= entry_price - tp_target
            if hit:
                partial_exits.append(PartialExit(
                    fraction=tier_frac,
                    exit_price=close,
                    exit_time=ts,
                    candle_index=i,
                ))
                tiers_filled += 1

                # After first tier: move SL to BE + fees if configured
                if tiers_filled == 1 and config.be_after_tp1:
                    if side == "long":
                        be_price = entry_price * (1 + config.be_after_tp1_buffer_pct)
                        if be_price > current_sl:
                            current_sl = be_price
                            be_locked = True
                    else:
                        be_price = entry_price * (1 - config.be_after_tp1_buffer_pct)
                        if be_price < current_sl:
                            current_sl = be_price
                            be_locked = True

                # If all tiers filled → activate runner mode
                if tiers_filled >= len(config.partial_tp_tiers):
                    runner_active = True

        # b3) Single partial TP check (legacy, when no tiers configured)
        elif not use_tiers and config.partial_tp_enabled and not partial_tp_taken and r_distance > 0:
            tp_target = r_distance * config.partial_tp_r
            if side == "long":
                hit = close >= entry_price + tp_target
            else:
                hit = close <= entry_price - tp_target
            if hit:
                partial_tp_taken = True
                partial_exits.append(PartialExit(
                    fraction=config.partial_tp_fraction,
                    exit_price=close,
                    exit_time=ts,
                    candle_index=i,
                ))

        # c) Trailing ratchet using CLOSE only
        if config.trailing_enabled:
            if runner_active and config.runner_trail_mode == "structure":
                # Structure-based trailing for runner
                atr_value = entry_price * atr_pct if atr_pct > 0 else 0.0
                struct_level = None
                if candle_highs is not None and candle_lows is not None and atr_value > 0:
                    struct_level = _structure_trail_level(
                        candle_highs, candle_lows,
                        current_index=i,
                        side=side,
                        atr_value=atr_value,
                        atr_buffer=config.runner_atr_buffer,
                    )
                if struct_level is not None:
                    # Use structure level
                    if side == "long" and struct_level > current_sl:
                        current_sl = struct_level
                        trailing_ratcheted = True
                    elif side == "short" and struct_level < current_sl:
                        current_sl = struct_level
                        trailing_ratcheted = True
                elif atr_pct > 0:
                    # Fallback to ATR trailing with runner mult
                    trail_dist = entry_price * atr_pct * config.runner_trail_atr_mult
                    if side == "long":
                        new_sl = close - trail_dist
                        if new_sl > current_sl:
                            current_sl = new_sl
                            trailing_ratcheted = True
                    else:
                        new_sl = close + trail_dist
                        if new_sl < current_sl:
                            current_sl = new_sl
                            trailing_ratcheted = True

            elif runner_active and config.runner_trail_mode == "atr" and atr_pct > 0:
                # Tighter ATR trailing for runner
                trail_dist = entry_price * atr_pct * config.runner_trail_atr_mult
                if side == "long":
                    new_sl = close - trail_dist
                    if new_sl > current_sl:
                        current_sl = new_sl
                        trailing_ratcheted = True
                else:
                    new_sl = close + trail_dist
                    if new_sl < current_sl:
                        current_sl = new_sl
                        trailing_ratcheted = True

            elif config.trail_atr_mult is not None and atr_pct > 0:
                # Standard ATR-based trailing (pre-runner or no tiers)
                trail_dist = entry_price * atr_pct * config.trail_atr_mult
                if side == "long":
                    new_sl = close - trail_dist
                    if new_sl > current_sl:
                        current_sl = new_sl
                        trailing_ratcheted = True
                else:
                    new_sl = close + trail_dist
                    if new_sl < current_sl:
                        current_sl = new_sl
                        trailing_ratcheted = True
            else:
                # Percentage-based trailing (original logic)
                if side == "long":
                    new_sl = close * (1 - config.trail_pct)
                    if new_sl > current_sl:
                        current_sl = new_sl
                        trailing_ratcheted = True
                else:
                    new_sl = close * (1 + config.trail_pct)
                    if new_sl < current_sl:
                        current_sl = new_sl
                        trailing_ratcheted = True

        # d) SL wick hit check using LOW (long) / HIGH (short)
        sl_hit = False
        if side == "long":
            sl_hit = low <= current_sl
        else:
            sl_hit = high >= current_sl

        if sl_hit:
            if trailing_ratcheted:
                reason = REASON_TRAILING_STOP
            elif be_locked:
                reason = REASON_BREAKEVEN_STOP
            else:
                reason = REASON_STOP_LOSS
            return ExitResult(
                exit_price=current_sl,
                exit_time=ts,
                exit_reason=reason,
                exit_candle_index=i,
                final_sl=current_sl,
                be_locked=be_locked,
                candles_evaluated=i + 1,
                partial_exits=partial_exits or None,
            )

        # e) Time-stop if candle_age >= max_hold_candles → exit at CLOSE
        if not config.unlimited_hold and candle_age >= config.max_hold_candles:
            return ExitResult(
                exit_price=close,
                exit_time=ts,
                exit_reason=REASON_TIME_STOP,
                exit_candle_index=i,
                final_sl=current_sl,
                be_locked=be_locked,
                candles_evaluated=i + 1,
                partial_exits=partial_exits or None,
            )

    # Nothing hit — exit at last candle close
    last = candles[-1]
    return ExitResult(
        exit_price=float(last["close"]),
        exit_time=last["timestamp"],
        exit_reason=REASON_TIME_EXIT,
        exit_candle_index=len(candles) - 1,
        final_sl=current_sl,
        be_locked=be_locked,
        candles_evaluated=len(candles),
        partial_exits=partial_exits or None,
    )
