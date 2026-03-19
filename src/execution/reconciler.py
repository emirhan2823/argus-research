"""Reconciliation between local and exchange position state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ReconcileDiff:
    symbol: str
    local_qty: float
    exchange_qty: float
    delta: float
    severity: str  # minor|major


def reconcile_positions(
    *,
    local_positions: Mapping[str, float],
    exchange_positions: Mapping[str, float],
    minor_tolerance: float = 1e-6,
) -> list[ReconcileDiff]:
    diffs: list[ReconcileDiff] = []
    symbols = set(local_positions.keys()) | set(exchange_positions.keys())
    for symbol in sorted(symbols):
        local_qty = float(local_positions.get(symbol, 0.0))
        exch_qty = float(exchange_positions.get(symbol, 0.0))
        delta = exch_qty - local_qty
        if abs(delta) <= minor_tolerance:
            continue
        severity = "minor" if abs(delta) <= 0.01 else "major"
        diffs.append(
            ReconcileDiff(
                symbol=symbol,
                local_qty=local_qty,
                exchange_qty=exch_qty,
                delta=delta,
                severity=severity,
            )
        )
    return diffs
