"""ARGUS v2.5 — Scale-In (DCA) Orchestrator.

Institutional-grade position scaling: never fire 100% on the first trigger.
Scout with 30%, reinforce with 70% when price improves or signal strengthens.

This module is self-contained, deterministic, and unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


SignalStrength = Literal["NORMAL", "STRONG", "VERY_STRONG"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaleInConfig:
    """Scale-In configuration — all defaults are conservative."""

    enabled: bool = False
    scout_pct: float = 0.30              # 30% allocation on NORMAL signal
    reinforcement_pct: float = 0.70      # 70% on STRONG / price-improved signal
    max_layers: int = 3                  # Maximum pyramid layers
    min_price_improvement_pct: float = 0.01  # 1% price must improve to add layer
    cooldown_minutes: int = 15           # Minimum time between layers
    max_avg_entry_deviation_pct: float = 0.05  # 5% max avg entry drift from first entry


# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaleInLayer:
    """Single entry layer within a scaled position."""

    layer_index: int
    entry_price: float
    quantity: float
    risk_budget_used: float      # Fraction of total risk budget consumed
    signal_strength: SignalStrength
    timestamp: datetime


@dataclass
class ScaleInPosition:
    """Mutable position state tracking all scale-in layers."""

    position_id: str
    symbol: str
    side: str                    # "long" | "short"
    layers: list[ScaleInLayer] = field(default_factory=list)
    total_risk_budget: float = 0.0   # Total risk allocated to this position
    risk_used: float = 0.0           # Risk budget consumed so far
    avg_entry_price: float = 0.0     # Weighted average entry
    status: str = "pending"          # "pending" | "scout" | "reinforced" | "full"


@dataclass(frozen=True)
class ScaleInDecision:
    """Output of should_scale_in()."""

    should_add: bool
    layer_size_pct: float            # Fraction of total budget for this layer
    reason: str
    layer_index: int = 0


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------


def compute_avg_entry(layers: list[ScaleInLayer]) -> float:
    """Compute weighted average entry price from layers.

    avg = sum(price_i * qty_i) / sum(qty_i)
    """
    if not layers:
        return 0.0
    total_qty = sum(l.quantity for l in layers)
    if total_qty <= 0:
        return 0.0
    return sum(l.entry_price * l.quantity for l in layers) / total_qty


def compute_layer_size(
    config: ScaleInConfig,
    total_budget: float,
    risk_used: float,
    signal_strength: SignalStrength,
    layer_index: int,
) -> float:
    """Compute risk allocation fraction for the next layer.

    Layer 0 (scout): scout_pct of total budget
    Layer 1+ (reinforcement): reinforcement portion, distributed across remaining layers

    Returns fraction of total_budget to use (0.0 to 1.0).
    """
    remaining = max(0.0, total_budget - risk_used)
    if remaining <= 0 or total_budget <= 0:
        return 0.0

    if layer_index == 0:
        # Scout entry: always use scout_pct
        return _clamp(config.scout_pct, 0.0, 1.0)

    # Reinforcement: use up to reinforcement_pct, but cap at remaining budget
    # For STRONG signals, fire full reinforcement. For NORMAL, fire half.
    if signal_strength in ("STRONG", "VERY_STRONG"):
        target = config.reinforcement_pct
    else:
        # NORMAL signal at improved price: use half the reinforcement budget
        target = config.reinforcement_pct * 0.5

    available_pct = remaining / total_budget
    return _clamp(target, 0.0, available_pct)


def _price_improved(
    side: str,
    first_entry: float,
    current_price: float,
    min_improvement_pct: float,
) -> bool:
    """Check if price has improved enough to justify adding a layer.

    For longs: price must have dropped by min_improvement_pct (cheaper entry).
    For shorts: price must have risen by min_improvement_pct (better short entry).
    """
    if first_entry <= 0:
        return False

    if side == "long":
        # Price should be LOWER for a better long entry
        improvement = (first_entry - current_price) / first_entry
    else:
        # Price should be HIGHER for a better short entry
        improvement = (current_price - first_entry) / first_entry

    return improvement >= min_improvement_pct


def should_scale_in(
    *,
    position: ScaleInPosition,
    current_price: float,
    signal_strength: SignalStrength,
    now: datetime,
    config: ScaleInConfig,
) -> ScaleInDecision:
    """Determine whether to add a new scale-in layer.

    Pure, deterministic function. No side effects.

    Returns ScaleInDecision with should_add=True if all conditions are met:
    1. Scale-in is enabled
    2. Position has room for more layers
    3. Risk budget not exhausted
    4. Price has improved sufficiently from first entry
    5. Cooldown period has elapsed since last layer
    """
    if not config.enabled:
        return ScaleInDecision(
            should_add=False, layer_size_pct=0.0,
            reason="scale_in_disabled",
        )

    n_layers = len(position.layers)

    # Max layers check
    if n_layers >= config.max_layers:
        return ScaleInDecision(
            should_add=False, layer_size_pct=0.0,
            reason=f"max_layers_reached ({n_layers}/{config.max_layers})",
            layer_index=n_layers,
        )

    # Risk budget check
    if position.risk_used >= position.total_risk_budget:
        return ScaleInDecision(
            should_add=False, layer_size_pct=0.0,
            reason="risk_budget_exhausted",
            layer_index=n_layers,
        )

    # First layer (scout) — always allowed
    if n_layers == 0:
        layer_size = compute_layer_size(
            config, position.total_risk_budget, position.risk_used,
            signal_strength, layer_index=0,
        )
        return ScaleInDecision(
            should_add=True,
            layer_size_pct=layer_size,
            reason="scout_entry",
            layer_index=0,
        )

    # Price improvement check (layers 1+)
    first_entry = position.layers[0].entry_price
    if not _price_improved(position.side, first_entry, current_price,
                           config.min_price_improvement_pct):
        return ScaleInDecision(
            should_add=False, layer_size_pct=0.0,
            reason="insufficient_price_improvement",
            layer_index=n_layers,
        )

    # Cooldown check
    last_layer = position.layers[-1]
    cooldown = timedelta(minutes=config.cooldown_minutes)
    if now - last_layer.timestamp < cooldown:
        remaining_secs = (cooldown - (now - last_layer.timestamp)).total_seconds()
        return ScaleInDecision(
            should_add=False, layer_size_pct=0.0,
            reason=f"cooldown_active ({remaining_secs:.0f}s remaining)",
            layer_index=n_layers,
        )

    # Max avg entry deviation check
    hypothetical_avg = _hypothetical_avg_entry(
        position.layers, current_price,
        compute_layer_size(config, position.total_risk_budget,
                           position.risk_used, signal_strength, n_layers),
    )
    if first_entry > 0:
        deviation = abs(hypothetical_avg - first_entry) / first_entry
        if deviation > config.max_avg_entry_deviation_pct:
            return ScaleInDecision(
                should_add=False, layer_size_pct=0.0,
                reason=f"avg_entry_deviation_too_large ({deviation:.3f})",
                layer_index=n_layers,
            )

    # All checks passed — add layer
    layer_size = compute_layer_size(
        config, position.total_risk_budget, position.risk_used,
        signal_strength, layer_index=n_layers,
    )
    if layer_size <= 0:
        return ScaleInDecision(
            should_add=False, layer_size_pct=0.0,
            reason="computed_layer_size_zero",
            layer_index=n_layers,
        )

    return ScaleInDecision(
        should_add=True,
        layer_size_pct=layer_size,
        reason="reinforcement_entry" if signal_strength in ("STRONG", "VERY_STRONG") else "price_improved_entry",
        layer_index=n_layers,
    )


def add_layer(
    *,
    position: ScaleInPosition,
    entry_price: float,
    quantity: float,
    risk_budget_used: float,
    signal_strength: SignalStrength,
    timestamp: datetime,
) -> ScaleInPosition:
    """Add a new layer to the position and update state.

    Mutates the position in-place and returns it for convenience.
    """
    layer = ScaleInLayer(
        layer_index=len(position.layers),
        entry_price=entry_price,
        quantity=quantity,
        risk_budget_used=risk_budget_used,
        signal_strength=signal_strength,
        timestamp=timestamp,
    )
    position.layers.append(layer)
    position.risk_used += risk_budget_used
    position.avg_entry_price = compute_avg_entry(position.layers)

    # Update status
    if len(position.layers) == 1:
        position.status = "scout"
    elif position.risk_used >= position.total_risk_budget * 0.95:
        position.status = "full"
    else:
        position.status = "reinforced"

    return position


def initial_position_size_pct(
    *,
    full_position_size: float,
    signal_strength: SignalStrength,
    config: ScaleInConfig,
) -> float:
    """Compute the initial (scout) position size when scale-in is active.

    If scale-in is disabled, returns full_position_size unchanged.
    If enabled, returns scout_pct * full_position_size.
    """
    if not config.enabled:
        return full_position_size

    if signal_strength in ("STRONG", "VERY_STRONG"):
        # Strong signals get a larger initial allocation
        return full_position_size * min(config.scout_pct + 0.20, 1.0)

    return full_position_size * config.scout_pct


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _hypothetical_avg_entry(
    existing_layers: list[ScaleInLayer],
    new_price: float,
    new_size_pct: float,
) -> float:
    """Compute what the avg entry would be if a new layer were added."""
    total_qty = sum(l.quantity for l in existing_layers)
    total_value = sum(l.entry_price * l.quantity for l in existing_layers)

    # Estimate new quantity proportionally
    avg_qty = total_qty / len(existing_layers) if existing_layers else 1.0
    new_qty = avg_qty * new_size_pct

    return (total_value + new_price * new_qty) / (total_qty + new_qty) if (total_qty + new_qty) > 0 else new_price
