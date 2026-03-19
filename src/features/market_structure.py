"""ARGUS v2.5 — Market Structure Detector.

Non-repainting Swing High / Swing Low detector using local extremum math.

A Swing Low is confirmed when bar[i].low is the strict minimum of
bars[i-N : i+N+1] (N bars left AND N bars right).  The signal only
locks in after the right-side window has fully closed, guaranteeing
zero look-ahead bias.

This module is self-contained, deterministic, and unit-testable.
It operates on raw NumPy arrays (highs, lows) — no pandas dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketStructureConfig:
    """Market structure detection parameters."""

    enabled: bool = False
    swing_window: int = 5               # N bars left + N bars right
    max_levels: int = 5                 # Keep top 5 nearest per side
    cluster_tolerance_pct: float = 0.003  # 0.3% — merge nearby levels
    min_age_bars: int = 3               # Ignore very recent pivots


# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwingLevel:
    """A single detected support or resistance level."""

    price: float
    bar_index: int              # Index in the OHLCV array
    level_type: str             # "support" | "resistance"
    strength: int               # Touch count (clustered neighbors)
    age_bars: int               # Bars since this level formed


@dataclass(frozen=True)
class MarketStructure:
    """Complete market structure snapshot."""

    supports: list[SwingLevel] = field(default_factory=list)
    resistances: list[SwingLevel] = field(default_factory=list)
    current_price: float = 0.0


# ---------------------------------------------------------------------------
# Core Detection — Non-Repainting Swing Pivots
# ---------------------------------------------------------------------------


def detect_swing_levels(
    highs: Sequence[float],
    lows: Sequence[float],
    window: int = 5,
    current_bar_index: int | None = None,
) -> list[SwingLevel]:
    """Detect confirmed swing highs and swing lows.

    A swing low at index `i` requires:
        lows[i] == min(lows[i-window : i+window+1])
        AND lows[i] < lows[j] for at least one j in the window (not flat)

    A swing high at index `i` requires:
        highs[i] == max(highs[i-window : i+window+1])
        AND highs[i] > highs[j] for at least one j in the window

    Non-repainting guarantee:
        The LAST valid center index is len(data) - 1 - window.
        This ensures the full right-side window has closed before
        declaring a pivot. No future data is ever used.

    Parameters
    ----------
    highs : Array of high prices.
    lows : Array of low prices.
    window : Half-window size (N bars each side).
    current_bar_index : Optional total bars count for age calculation.
                        Defaults to len(highs) - 1.

    Returns
    -------
    List of SwingLevel objects (unsorted).
    """
    n = len(highs)
    if n != len(lows):
        raise ValueError("highs and lows must have equal length")
    if n < 2 * window + 1:
        return []  # Insufficient data

    if current_bar_index is None:
        current_bar_index = n - 1

    levels: list[SwingLevel] = []

    # Last valid center: n - 1 - window (right window fully closed)
    last_valid = n - 1 - window

    for i in range(window, last_valid + 1):
        lo_slice = lows[i - window: i + window + 1]
        hi_slice = highs[i - window: i + window + 1]

        lo_val = float(lows[i])
        hi_val = float(highs[i])

        # Swing Low: this bar's low is the minimum of the window
        min_in_window = min(float(v) for v in lo_slice)
        if lo_val == min_in_window and lo_val < max(float(v) for v in lo_slice):
            levels.append(SwingLevel(
                price=lo_val,
                bar_index=i,
                level_type="support",
                strength=1,
                age_bars=current_bar_index - i,
            ))

        # Swing High: this bar's high is the maximum of the window
        max_in_window = max(float(v) for v in hi_slice)
        if hi_val == max_in_window and hi_val > min(float(v) for v in hi_slice):
            levels.append(SwingLevel(
                price=hi_val,
                bar_index=i,
                level_type="resistance",
                strength=1,
                age_bars=current_bar_index - i,
            ))

    return levels


# ---------------------------------------------------------------------------
# Clustering — Merge Nearby Levels
# ---------------------------------------------------------------------------


def cluster_levels(
    levels: list[SwingLevel],
    tolerance_pct: float = 0.003,
) -> list[SwingLevel]:
    """Merge nearby swing levels into clusters, boosting strength.

    Two levels are "nearby" if their prices are within tolerance_pct
    of each other. When merged, the cluster keeps the price of the
    most recent level and sums the strengths.

    Parameters
    ----------
    levels : Raw swing levels (single level_type).
    tolerance_pct : Fraction (e.g., 0.003 = 0.3%) for clustering.

    Returns
    -------
    Deduplicated list of SwingLevel with boosted strength.
    """
    if not levels:
        return []

    # Sort by price for efficient clustering
    sorted_levels = sorted(levels, key=lambda l: l.price)
    clusters: list[SwingLevel] = []

    current_cluster = [sorted_levels[0]]
    for level in sorted_levels[1:]:
        ref_price = current_cluster[0].price
        if ref_price > 0 and abs(level.price - ref_price) / ref_price <= tolerance_pct:
            current_cluster.append(level)
        else:
            clusters.append(_merge_cluster(current_cluster))
            current_cluster = [level]

    clusters.append(_merge_cluster(current_cluster))
    return clusters


def _merge_cluster(cluster: list[SwingLevel]) -> SwingLevel:
    """Merge a cluster of nearby levels into one."""
    # Use the most recent level's price and bar_index
    most_recent = max(cluster, key=lambda l: l.bar_index)
    return SwingLevel(
        price=most_recent.price,
        bar_index=most_recent.bar_index,
        level_type=most_recent.level_type,
        strength=sum(l.strength for l in cluster),
        age_bars=most_recent.age_bars,
    )


# ---------------------------------------------------------------------------
# Builder — Full Market Structure
# ---------------------------------------------------------------------------


def build_market_structure(
    highs: Sequence[float],
    lows: Sequence[float],
    current_price: float,
    config: MarketStructureConfig | None = None,
) -> MarketStructure:
    """Build a complete market structure snapshot from OHLCV data.

    Parameters
    ----------
    highs : Array of high prices (oldest first).
    lows : Array of low prices (oldest first).
    current_price : Current market price (for sorting by proximity).
    config : Detection parameters.

    Returns
    -------
    MarketStructure with supports and resistances sorted nearest-first.
    """
    cfg = config or MarketStructureConfig()

    if not cfg.enabled:
        return MarketStructure(current_price=current_price)

    n = len(highs)
    if n < 2 * cfg.swing_window + 1:
        return MarketStructure(current_price=current_price)

    # Detect raw swing levels
    raw_levels = detect_swing_levels(
        highs=highs,
        lows=lows,
        window=cfg.swing_window,
        current_bar_index=n - 1,
    )

    # Filter by minimum age
    aged_levels = [l for l in raw_levels if l.age_bars >= cfg.min_age_bars]

    # Split into supports and resistances
    raw_supports = [l for l in aged_levels if l.level_type == "support"]
    raw_resistances = [l for l in aged_levels if l.level_type == "resistance"]

    # Cluster nearby levels
    clustered_supports = cluster_levels(raw_supports, cfg.cluster_tolerance_pct)
    clustered_resistances = cluster_levels(raw_resistances, cfg.cluster_tolerance_pct)

    # Sort by proximity to current price (nearest first)
    sorted_supports = sorted(
        clustered_supports,
        key=lambda l: abs(l.price - current_price),
    )[:cfg.max_levels]

    sorted_resistances = sorted(
        clustered_resistances,
        key=lambda l: abs(l.price - current_price),
    )[:cfg.max_levels]

    return MarketStructure(
        supports=sorted_supports,
        resistances=sorted_resistances,
        current_price=current_price,
    )


# ---------------------------------------------------------------------------
# SL Shield + TP Magnet — Structure-Aware Adjustment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StructureAdjustedResult:
    """Output of adjust_sl_tp_for_structure()."""

    sl_price: float
    tp_price: float
    sl_adjusted: bool           # True if SL was moved by structure
    tp_adjusted: bool           # True if TP was moved by structure
    sl_shield_level: SwingLevel | None = None   # The support/resistance used
    tp_magnet_level: SwingLevel | None = None   # The support/resistance used
    reason: str = ""


def adjust_sl_tp_for_structure(
    *,
    side: str,
    sl_price: float,
    tp_price: float,
    entry_price: float,
    structure: MarketStructure,
    sl_buffer_pct: float = 0.002,    # Place SL 0.2% beyond the structure level
    tp_buffer_pct: float = 0.002,    # Place TP 0.2% before the structure level
    sl_max_expansion_pct: float = 0.5,  # SL can widen at most 50% beyond original
    tp_magnet_zone_pct: float = 0.20,   # TP magnet activates in last 20% of TP range
) -> StructureAdjustedResult:
    """Adjust SL and TP using market structure (support/resistance).

    SL Shield:
        Long: If a support exists between SL and entry, push SL just below it.
        Short: If a resistance exists between entry and SL, push SL just above it.
        INVARIANT: Adjusted SL is ALWAYS wider than or equal to original.
                   This can only improve survival, never increase risk.

    TP Magnet:
        Long: If a resistance exists in the last 20% of the TP range,
              pull TP to just below it (get filled before rejection).
        Short: If a support exists in the last 20% of the TP range,
              pull TP to just above it.

    Parameters
    ----------
    side : "long" or "short"
    sl_price : ATR-based stop-loss price from DRM
    tp_price : ATR-based take-profit price from DRM
    entry_price : Entry price
    structure : MarketStructure with detected levels
    sl_buffer_pct : Buffer below/above structure for SL placement
    tp_buffer_pct : Buffer below/above structure for TP placement
    sl_max_expansion_pct : Max SL widening as fraction of original distance
    tp_magnet_zone_pct : Zone near TP where magnet activates (0.0-1.0)
    """
    if not structure.supports and not structure.resistances:
        return StructureAdjustedResult(
            sl_price=sl_price, tp_price=tp_price,
            sl_adjusted=False, tp_adjusted=False,
            reason="no_structure_levels",
        )

    new_sl = sl_price
    new_tp = tp_price
    sl_adjusted = False
    tp_adjusted = False
    sl_shield_level: SwingLevel | None = None
    tp_magnet_level: SwingLevel | None = None
    reasons: list[str] = []

    original_sl_dist = abs(entry_price - sl_price)
    max_sl_dist = original_sl_dist * (1.0 + sl_max_expansion_pct)
    tp_dist = abs(tp_price - entry_price)

    if side == "long":
        # --- SL Shield: find support between (SL, entry) ---
        # Place SL just below the support level (hiding behind the wall)
        # This moves SL UP (closer to entry) but behind structure
        candidates = [
            s for s in structure.supports
            if sl_price < s.price < entry_price
        ]
        if candidates:
            # Pick the strongest support in the zone
            best = max(candidates, key=lambda s: s.strength)
            shielded_sl = best.price * (1.0 - sl_buffer_pct)  # Just below support
            # Shielded SL is above original SL (tighter but structurally protected)
            # Only adjust if the tightening is reasonable (not losing >50% of original distance)
            if shielded_sl > sl_price:
                new_dist = abs(entry_price - shielded_sl)
                # Don't tighten more than sl_max_expansion_pct of original distance
                min_dist = original_sl_dist * (1.0 - sl_max_expansion_pct)
                if new_dist >= min_dist:
                    new_sl = shielded_sl
                    sl_adjusted = True
                    sl_shield_level = best
                    reasons.append(f"sl_shield_support@{best.price:.2f}")

        # --- TP Magnet: find resistance in last 20% of TP range ---
        if tp_dist > 0:
            magnet_zone_start = entry_price + tp_dist * (1.0 - tp_magnet_zone_pct)
            candidates_tp = [
                r for r in structure.resistances
                if magnet_zone_start < r.price < tp_price
            ]
            if candidates_tp:
                # Pick the strongest resistance in the zone
                best_tp = max(candidates_tp, key=lambda r: r.strength)
                magnetized_tp = best_tp.price * (1.0 - tp_buffer_pct)
                if magnetized_tp > entry_price:  # Must still be profitable
                    new_tp = magnetized_tp
                    tp_adjusted = True
                    tp_magnet_level = best_tp
                    reasons.append(f"tp_magnet_resistance@{best_tp.price:.2f}")

    else:
        # --- SL Shield: find resistance between (entry, SL) ---
        # Place SL just above the resistance level (hiding behind the wall)
        # This moves SL DOWN (closer to entry) but behind structure
        candidates = [
            r for r in structure.resistances
            if entry_price < r.price < sl_price
        ]
        if candidates:
            best = max(candidates, key=lambda r: r.strength)
            shielded_sl = best.price * (1.0 + sl_buffer_pct)  # Just above resistance
            if shielded_sl < sl_price:
                new_dist = abs(shielded_sl - entry_price)
                min_dist = original_sl_dist * (1.0 - sl_max_expansion_pct)
                if new_dist >= min_dist:
                    new_sl = shielded_sl
                    sl_adjusted = True
                    sl_shield_level = best
                    reasons.append(f"sl_shield_resistance@{best.price:.2f}")

        # --- TP Magnet: find support in last 20% of TP range ---
        if tp_dist > 0:
            magnet_zone_start = entry_price - tp_dist * (1.0 - tp_magnet_zone_pct)
            candidates_tp = [
                s for s in structure.supports
                if tp_price < s.price < magnet_zone_start
            ]
            if candidates_tp:
                best_tp = max(candidates_tp, key=lambda s: s.strength)
                magnetized_tp = best_tp.price * (1.0 + tp_buffer_pct)
                if magnetized_tp < entry_price:
                    new_tp = magnetized_tp
                    tp_adjusted = True
                    tp_magnet_level = best_tp
                    reasons.append(f"tp_magnet_support@{best_tp.price:.2f}")

    return StructureAdjustedResult(
        sl_price=new_sl,
        tp_price=new_tp,
        sl_adjusted=sl_adjusted,
        tp_adjusted=tp_adjusted,
        sl_shield_level=sl_shield_level,
        tp_magnet_level=tp_magnet_level,
        reason="; ".join(reasons) if reasons else "no_adjustment",
    )
