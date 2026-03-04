"""ARGUS v2.5 — Aggressive Break-Even Lock.

Snap stop-loss to break-even (including fees) once price moves 1× ATR
in our favor from the average entry price.

Why this is different from existing TrailingRules.breakeven_at_r:
1. Uses ATR (absolute volatility measure), not R-multiples (relative to stop)
2. Works on AVERAGE entry price (scale-in aware), not single entry
3. Includes fee offset so break-even actually means breaking even after costs

This module is self-contained, deterministic, and unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BreakevenConfig:
    """Break-even lock configuration."""

    enabled: bool = False
    trigger_atr_multiple: float = 1.0    # Snap to BE at 1× ATR profit
    include_fees: bool = True            # Account for round-trip fees in BE price
    default_fee_pct: float = 0.001       # 0.1% per side = 0.2% round-trip


# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BreakevenResult:
    """Output of check_breakeven_trigger()."""

    triggered: bool
    new_sl: float            # Updated stop-loss price
    breakeven_price: float   # The computed break-even price (entry + fees)
    profit_distance: float   # Current profit as multiple of ATR
    reason: str


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------


def compute_breakeven_price(
    *,
    avg_entry_price: float,
    side: str,
    fee_pct: float = 0.001,
    include_fees: bool = True,
) -> float:
    """Compute the true break-even price including round-trip fees.

    For longs: BE = entry × (1 + 2 × fee_pct)  — must clear entry + 2 sides
    For shorts: BE = entry × (1 - 2 × fee_pct) — must clear entry - 2 sides

    The 2× accounts for both the entry fee and the eventual exit fee.
    """
    if not include_fees or fee_pct <= 0:
        return avg_entry_price

    round_trip_cost_pct = 2.0 * fee_pct  # Entry + exit

    if side == "long":
        return avg_entry_price * (1.0 + round_trip_cost_pct)
    else:
        return avg_entry_price * (1.0 - round_trip_cost_pct)


def check_breakeven_trigger(
    *,
    side: str,
    avg_entry_price: float,
    current_price: float,
    atr: float,
    current_sl: float,
    config: BreakevenConfig | None = None,
    fee_pct: float | None = None,
) -> BreakevenResult:
    """Check if break-even lock should trigger and return updated SL.

    Trigger condition:
        Long:  current_price >= avg_entry + trigger_atr_multiple × ATR
        Short: current_price <= avg_entry - trigger_atr_multiple × ATR

    When triggered, new SL = breakeven_price (entry + fees).

    CRITICAL: SL never moves AGAINST the trade. If current_sl is already
    beyond BE, we don't move it backwards.

    Parameters
    ----------
    side : "long" or "short"
    avg_entry_price : Weighted average entry (from scale-in layers or single entry)
    current_price : Current market price
    atr : Current ATR value (absolute, not percentage)
    current_sl : Current stop-loss price
    config : Break-even configuration
    fee_pct : Override fee percentage (uses config default if None)
    """
    cfg = config or BreakevenConfig()

    if not cfg.enabled:
        return BreakevenResult(
            triggered=False, new_sl=current_sl,
            breakeven_price=avg_entry_price, profit_distance=0.0,
            reason="breakeven_disabled",
        )

    # Validate inputs
    if avg_entry_price <= 0 or not math.isfinite(avg_entry_price):
        return BreakevenResult(
            triggered=False, new_sl=current_sl,
            breakeven_price=avg_entry_price, profit_distance=0.0,
            reason="invalid_entry_price",
        )
    if atr <= 0 or not math.isfinite(atr):
        return BreakevenResult(
            triggered=False, new_sl=current_sl,
            breakeven_price=avg_entry_price, profit_distance=0.0,
            reason="invalid_atr",
        )

    effective_fee = fee_pct if fee_pct is not None else cfg.default_fee_pct

    # Compute break-even price
    be_price = compute_breakeven_price(
        avg_entry_price=avg_entry_price,
        side=side,
        fee_pct=effective_fee,
        include_fees=cfg.include_fees,
    )

    # Compute profit distance in ATR multiples
    trigger_distance = cfg.trigger_atr_multiple * atr

    if side == "long":
        profit = current_price - avg_entry_price
        profit_atr = profit / atr if atr > 0 else 0.0
        triggered = profit >= trigger_distance

        if triggered:
            # Move SL to BE, but never BELOW current SL (no regression)
            new_sl = max(current_sl, be_price)
            return BreakevenResult(
                triggered=True, new_sl=new_sl,
                breakeven_price=be_price, profit_distance=profit_atr,
                reason="breakeven_locked_long",
            )
    else:
        profit = avg_entry_price - current_price
        profit_atr = profit / atr if atr > 0 else 0.0
        triggered = profit >= trigger_distance

        if triggered:
            # Move SL to BE, but never ABOVE current SL for shorts
            new_sl = min(current_sl, be_price)
            return BreakevenResult(
                triggered=True, new_sl=new_sl,
                breakeven_price=be_price, profit_distance=profit_atr,
                reason="breakeven_locked_short",
            )

    return BreakevenResult(
        triggered=False, new_sl=current_sl,
        breakeven_price=be_price, profit_distance=profit_atr,
        reason=f"below_trigger ({profit_atr:.2f}R < {cfg.trigger_atr_multiple:.1f}R)",
    )
