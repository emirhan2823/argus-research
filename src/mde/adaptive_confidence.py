"""Adaptive Confidence Floor — dynamic minimum confidence based on recent performance.

Adjusts the minimum confidence threshold using a rolling window of recent
trade outcomes. Prevents consecutive losses from compounding by raising
the bar, and slightly relaxes when performance is strong.

Integration point: Before Step 7 (gates) — overrides GateInput.min_confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class AdaptiveFloorResult:
    """Result of adaptive confidence floor computation."""

    effective_min_confidence: float
    base_confidence: float
    adjustment: float
    recent_win_rate: float
    sample_size: int
    reason: str


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


_ENGINE_MAX_FLOORS: dict[str, float] = {
    "NAUTILUS": 0.55,
    "HYDRA": 0.55,
    "PHOENIX": 0.55,
    "AEGEAN": 0.55,
    "POSEIDON": 0.55,
}


def compute_adaptive_floor(
    *,
    base_min_confidence: float = 0.65,
    recent_trade_outcomes: Sequence[bool],  # True = win, False = loss
    lookback: int = 20,
    floor_low: float = 0.60,    # Minimum possible floor
    floor_high: float = 0.80,   # Maximum possible floor
    engine: str | None = None,  # Engine name for per-engine floor caps
) -> AdaptiveFloorResult:
    """Compute adaptive confidence floor from recent trade results.

    Win rate bands:
    - >= 65%: slight relaxation (-0.03)
    - 55-65%: no change (0.00)
    - 45-55%: tighten (+0.05)
    - < 45%:  significant tightening (+0.10)

    Engine-aware: NAUTILUS/HYDRA/PHOENIX/AEGEAN get a max floor cap of 0.55
    to prevent over-filtering structurally lower-confidence strategies.

    If fewer than 10 trades in history, uses base_min_confidence unchanged.
    """
    recent = list(recent_trade_outcomes[-lookback:]) if recent_trade_outcomes else []
    sample_size = len(recent)

    if sample_size < 10:
        base = base_min_confidence
        # Apply engine cap even for insufficient data
        if engine is not None:
            cap = _ENGINE_MAX_FLOORS.get(engine.upper())
            if cap is not None:
                base = min(base, cap)
        return AdaptiveFloorResult(
            effective_min_confidence=base,
            base_confidence=base_min_confidence,
            adjustment=0.0,
            recent_win_rate=0.0,
            sample_size=sample_size,
            reason=f"insufficient_data samples={sample_size}<10"
            + (f" [engine_cap={engine}]" if engine and engine.upper() in _ENGINE_MAX_FLOORS else ""),
        )

    win_rate = sum(1 for o in recent if o) / sample_size

    if win_rate >= 0.65:
        adjustment = -0.03
    elif win_rate >= 0.55:
        adjustment = 0.0
    elif win_rate >= 0.45:
        adjustment = 0.05
    else:
        adjustment = 0.10

    effective = _clamp(base_min_confidence + adjustment, floor_low, floor_high)

    # Apply engine-specific max floor cap
    engine_capped = False
    if engine is not None:
        cap = _ENGINE_MAX_FLOORS.get(engine.upper())
        if cap is not None and effective > cap:
            effective = cap
            engine_capped = True

    return AdaptiveFloorResult(
        effective_min_confidence=round(effective, 4),
        base_confidence=base_min_confidence,
        adjustment=adjustment,
        recent_win_rate=round(win_rate, 4),
        sample_size=sample_size,
        reason=f"adaptive_floor wr={win_rate:.2%} adj={adjustment:+.2f} → {effective:.3f}"
        + (f" [engine_cap={engine}]" if engine_capped else ""),
    )
