"""Risk cap helpers."""

from __future__ import annotations


def compute_effective_cap(phase_risk: float, global_per_trade_cap: float) -> float:
    """Return hard effective cap as the lower of phase/global caps."""

    return min(float(phase_risk), float(global_per_trade_cap))

