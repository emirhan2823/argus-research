"""Sizing model for ARGUS MDE."""

from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class SizingInput:
    stop_distance: float
    atlas_mult: float
    sentinel_mult: float
    regime_conf: float
    dd_mult: float
    rsl_mult: float
    hermes_mult: float
    leverage_mult: float = 1.0
    base_risk_pct: float = 0.02
    min_risk_pct: float = 0.005
    max_risk_pct: float = 0.03
    max_position_size: float = 0.15


@dataclass(frozen=True)
class SizingResult:
    risk_per_trade: float
    position_size: float


def compute_size(inp: SizingInput) -> SizingResult:
    risk = (
        inp.base_risk_pct
        * inp.atlas_mult
        * inp.sentinel_mult
        * inp.regime_conf
        * inp.dd_mult
        * inp.rsl_mult
        * inp.hermes_mult
        * inp.leverage_mult
    )
    risk = _clamp(risk, inp.min_risk_pct, inp.max_risk_pct)
    position_size = _clamp(risk / max(inp.stop_distance, 1e-9), 0.0, inp.max_position_size)
    return SizingResult(risk_per_trade=risk, position_size=position_size)
