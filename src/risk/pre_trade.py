"""Pre-trade risk checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PreTradeInput:
    asset_class: str
    position_size: float
    leverage: float
    trades_today: int
    stop_loss: float
    correlation_with_book: float
    within_funding_blackout: bool = False
    is_weekend: bool = False
    allocation_ok: bool = True
    max_position_size: float = 0.15
    max_leverage: float = 2.0
    max_trades_per_day: int = 15
    max_correlation: float = 0.6
    max_stop_crypto: float = 0.05
    max_stop_stock: float = 0.08
    max_stop_commodity: float = 0.06


@dataclass(frozen=True)
class PreTradeResult:
    approved: bool
    reason: str
    adjusted_position_size: float
    violations: tuple[str, ...] = field(default_factory=tuple)


class PreTradeChecker:
    def check(self, inp: PreTradeInput) -> PreTradeResult:
        violations: list[str] = []
        size = inp.position_size

        if size > inp.max_position_size:
            violations.append("position_size_limit")
        if inp.leverage > inp.max_leverage:
            violations.append("leverage_limit")
        if inp.trades_today >= inp.max_trades_per_day:
            violations.append("daily_trade_limit")
        if inp.asset_class == "crypto" and inp.within_funding_blackout:
            violations.append("funding_blackout")
        if inp.asset_class == "crypto" and inp.is_weekend:
            size *= 0.5
        if inp.correlation_with_book > inp.max_correlation:
            violations.append("correlation_limit")
        if inp.stop_loss <= 0:
            violations.append("stop_loss_non_positive")

        if inp.asset_class in {"us_equity", "index", "bist"}:
            max_stop = inp.max_stop_stock
        elif inp.asset_class == "commodity":
            max_stop = inp.max_stop_commodity
        else:
            max_stop = inp.max_stop_crypto

        if inp.stop_loss > max_stop:
            violations.append("stop_loss_too_wide")
        if not inp.allocation_ok:
            violations.append("allocation_limit")

        if violations:
            return PreTradeResult(
                approved=False,
                reason=violations[0],
                adjusted_position_size=max(size, 0.0),
                violations=tuple(violations),
            )

        return PreTradeResult(
            approved=True,
            reason="ok",
            adjusted_position_size=max(size, 0.0),
            violations=tuple(),
        )
