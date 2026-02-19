"""Stop widening resize helper."""

from __future__ import annotations


def recalculate_after_stop_widening(
    risk_per_trade: float,
    old_stop: float,
    stop_multiplier_delta: float,
    min_stop: float = 0.01,
    max_stop: float = 0.05,
) -> tuple[float, float]:
    """Recalculate stop + position size while preserving risk_per_trade."""

    unclamped_stop = float(old_stop) * (1.0 + float(stop_multiplier_delta))
    new_stop = max(float(min_stop), min(float(max_stop), unclamped_stop))
    new_size = float(risk_per_trade) / new_stop
    return new_stop, new_size

