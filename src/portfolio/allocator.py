"""Portfolio allocation and heat constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AllocationLimits:
    max_crypto_pct: float = 0.50
    max_equity_pct: float = 0.40
    max_commodity_pct: float = 0.20
    min_cash_pct: float = 0.10
    max_portfolio_heat: float = 0.10
    max_correlation: float = 0.60


def _bucket(asset_class: str) -> str:
    if asset_class == "crypto":
        return "crypto"
    if asset_class in {"us_equity", "index", "bist"}:
        return "equity"
    if asset_class == "commodity":
        return "commodity"
    return "equity"


@dataclass
class PortfolioAllocator:
    limits: AllocationLimits = AllocationLimits()

    def can_allocate(
        self,
        *,
        current_allocations: Mapping[str, float],
        asset_class: str,
        position_pct: float,
        correlation_with_book: float,
        current_heat: float,
    ) -> tuple[bool, str]:
        if correlation_with_book > self.limits.max_correlation:
            return False, "correlation_limit_exceeded"
        if current_heat + position_pct > self.limits.max_portfolio_heat:
            return False, "portfolio_heat_limit_exceeded"

        projected = self.projected_allocations(
            current_allocations=current_allocations,
            asset_class=asset_class,
            position_pct=position_pct,
        )

        if projected["crypto"] > self.limits.max_crypto_pct:
            return False, "max_crypto_allocation_exceeded"
        if projected["equity"] > self.limits.max_equity_pct:
            return False, "max_equity_allocation_exceeded"
        if projected["commodity"] > self.limits.max_commodity_pct:
            return False, "max_commodity_allocation_exceeded"
        if projected["cash"] < self.limits.min_cash_pct:
            return False, "min_cash_allocation_violated"
        return True, "ok"

    def projected_allocations(
        self,
        *,
        current_allocations: Mapping[str, float],
        asset_class: str,
        position_pct: float,
    ) -> dict[str, float]:
        out = {
            "crypto": float(current_allocations.get("crypto", 0.0)),
            "equity": float(current_allocations.get("equity", 0.0)),
            "commodity": float(current_allocations.get("commodity", 0.0)),
            "cash": float(current_allocations.get("cash", 1.0)),
        }
        bucket = _bucket(asset_class)
        out[bucket] += position_pct
        out["cash"] -= position_pct
        return out
