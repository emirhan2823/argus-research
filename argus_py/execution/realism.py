from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .models import OrderSide, UrgencyLevel


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


@dataclass(frozen=True)
class RealismContext:
    symbol: str
    asset_class: str
    venue_id: str
    side: OrderSide
    urgency: UrgencyLevel
    regime: str
    market_price: float
    requested_qty: float


@dataclass(frozen=True)
class RealismPlan:
    adjusted_qty: float
    adjusted_price: float
    fill_ratio: float
    slippage_bps: float
    latency_ms: int
    depth_cap_notional: float
    status_hint: str
    reason: str


class ExecutionRealismModel:
    """
    Deterministic execution realism model:
    - orderbook depth based partial fills
    - regime/urgency-dependent slippage
    - latency bucket estimation
    """

    def __init__(
        self,
        *,
        depth_caps_usd: Dict[str, float] | None = None,
        urgency_slippage_bps: Dict[UrgencyLevel, float] | None = None,
        regime_slippage_mult: Dict[str, float] | None = None,
        urgency_latency_ms: Dict[UrgencyLevel, int] | None = None,
        min_fill_ratio: float = 0.08,
    ) -> None:
        self.depth_caps_usd = depth_caps_usd or {
            "crypto": 20_000.0,
            "stock": 15_000.0,
            "defi": 4_000.0,
        }
        self.urgency_slippage_bps = urgency_slippage_bps or {
            UrgencyLevel.LOW: 2.0,
            UrgencyLevel.NORMAL: 6.0,
            UrgencyLevel.HIGH: 12.0,
            UrgencyLevel.CRITICAL: 20.0,
        }
        self.regime_slippage_mult = regime_slippage_mult or {
            "LOW_VOL_CALM": 0.8,
            "RANGE": 1.0,
            "TREND": 1.1,
            "CHOP": 1.4,
            "HIGH_VOL_CHOP": 1.6,
            "BULL_TREND": 1.1,
            "BEAR_TREND": 1.2,
        }
        self.urgency_latency_ms = urgency_latency_ms or {
            UrgencyLevel.LOW: 520,
            UrgencyLevel.NORMAL: 320,
            UrgencyLevel.HIGH: 180,
            UrgencyLevel.CRITICAL: 120,
        }
        self.min_fill_ratio = _clamp(min_fill_ratio, 0.01, 1.0)

    def plan(self, ctx: RealismContext) -> RealismPlan:
        market_price = max(1e-9, float(ctx.market_price))
        requested_qty = max(0.0, float(ctx.requested_qty))
        requested_notional = requested_qty * market_price
        asset_class = str(ctx.asset_class or "crypto").lower()
        regime = str(ctx.regime or "RANGE").upper()

        base_depth = float(self.depth_caps_usd.get(asset_class, self.depth_caps_usd["crypto"]))
        depth_regime_mult = 1.0
        if regime in {"HIGH_VOL_CHOP", "CHOP"}:
            depth_regime_mult = 0.70
        elif regime in {"LOW_VOL_CALM"}:
            depth_regime_mult = 1.15
        depth_cap = max(100.0, base_depth * depth_regime_mult)

        if requested_notional <= 0.0:
            fill_ratio = 0.0
        else:
            fill_ratio = min(1.0, depth_cap / requested_notional)
        if 0.0 < fill_ratio < self.min_fill_ratio:
            fill_ratio = 0.0

        adjusted_qty = requested_qty * fill_ratio
        urgency_bps = float(self.urgency_slippage_bps.get(ctx.urgency, 6.0))
        regime_mult = float(self.regime_slippage_mult.get(regime, 1.0))
        pressure = (requested_notional / depth_cap) if depth_cap > 0 else 1.0
        pressure_mult = 1.0 + max(0.0, pressure - 1.0) * 0.40
        slippage_bps = urgency_bps * regime_mult * pressure_mult

        slip_frac = slippage_bps / 10_000.0
        if ctx.side == OrderSide.BUY:
            adjusted_price = market_price * (1.0 + slip_frac)
        else:
            adjusted_price = market_price * max(0.01, (1.0 - slip_frac))

        latency = int(round(float(self.urgency_latency_ms.get(ctx.urgency, 320)) * regime_mult))
        if fill_ratio <= 0.0:
            status = "REJECTED_LIQUIDITY"
            reason = "depth too thin for minimum fill ratio"
        elif fill_ratio < 0.999:
            status = "PARTIAL"
            reason = f"depth-limited fill ({fill_ratio:.2%})"
        else:
            status = "FILLED"
            reason = "full fill"

        return RealismPlan(
            adjusted_qty=float(adjusted_qty),
            adjusted_price=float(adjusted_price),
            fill_ratio=float(fill_ratio),
            slippage_bps=float(slippage_bps),
            latency_ms=int(latency),
            depth_cap_notional=float(depth_cap),
            status_hint=status,
            reason=reason,
        )


__all__ = ["ExecutionRealismModel", "RealismContext", "RealismPlan"]
