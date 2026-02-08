from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class FeeModel:
    """Exchange fee configuration."""

    taker_bps: float = 4.0
    maker_bps: float = 2.0
    funding_bps: float = 1.0


@dataclass
class SlippageModel:
    """Market impact configuration."""

    base_bps: float = 2.0
    size_impact_bps: float = 1.0
    volatility_mult: float = 1.5


@dataclass
class RealismConfig:
    fees: FeeModel = field(default_factory=FeeModel)
    slippage: SlippageModel = field(default_factory=SlippageModel)


class RealismEngine:
    """Realistic fee and slippage calculator."""

    def __init__(self, config: RealismConfig = None):
        self.config = config or RealismConfig()

    def calculate_commission(self, quantity: float, price: float, is_taker: bool = True) -> float:
        fee_bps = self.config.fees.taker_bps if is_taker else self.config.fees.maker_bps
        notional = quantity * price
        return notional * (fee_bps / 10000.0)

    def calculate_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        atr: Optional[float] = None,
        volume_24h: Optional[float] = None,
    ) -> float:
        cfg = self.config.slippage
        notional = max(0.0, quantity * price)

        base = price * (cfg.base_bps / 10000.0)
        size_impact = price * (cfg.size_impact_bps / 10000.0) * np.sqrt(notional / 1000.0) if notional > 0 else 0.0

        vol_adj = 1.0
        if atr:
            atr_pct = (atr / price) * 100.0 if price > 0 else 0.0
            vol_adj = 1.0 + (atr_pct - 1.0) * (cfg.volatility_mult - 1.0)

        total = (base + size_impact) * max(0.5, vol_adj)

        return total if side == "BUY" else -total

    def calculate_funding(
        self,
        position_value: float,
        hours_held: float,
        avg_funding_rate: Optional[float] = None,
    ) -> float:
        rate_bps = avg_funding_rate if avg_funding_rate is not None else self.config.fees.funding_bps
        funding_periods = hours_held / 8.0
        return position_value * (rate_bps / 10000.0) * funding_periods

    def get_effective_price(
        self,
        price: float,
        quantity: float,
        side: str,
        atr: Optional[float] = None,
    ) -> float:
        slip = self.calculate_slippage(price, quantity, side, atr)
        if side == "BUY":
            return price + slip
        return price - abs(slip)

    def estimate_round_trip_cost(
        self,
        price: float,
        quantity: float,
        hold_hours: float = 24.0,
        atr: Optional[float] = None,
    ) -> dict:
        notional = quantity * price

        entry_commission = self.calculate_commission(quantity, price, is_taker=True)
        entry_slippage = abs(self.calculate_slippage(price, quantity, "BUY", atr)) * quantity

        exit_commission = self.calculate_commission(quantity, price, is_taker=True)
        exit_slippage = abs(self.calculate_slippage(price, quantity, "SELL", atr)) * quantity

        funding = self.calculate_funding(notional, hold_hours)

        total = entry_commission + exit_commission + entry_slippage + exit_slippage + funding

        return {
            "notional": notional,
            "entry_commission": entry_commission,
            "exit_commission": exit_commission,
            "entry_slippage": entry_slippage,
            "exit_slippage": exit_slippage,
            "funding": funding,
            "total_cost": total,
            "cost_bps": (total / notional) * 10000.0 if notional > 0 else 0.0,
        }
