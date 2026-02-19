"""Pre-trade risk checks."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from decimal import Decimal

from src.risk.validated_sizer import compute_validated_size
from src.v25.contracts.validated_sizing import ValidatedSizing


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
    symbol: str = "UNKNOWN"
    ts: datetime | None = None
    risk_usd: Decimal | None = None
    entry_price: Decimal | None = None
    equity_usd: Decimal | None = None
    fee_bps: Decimal = Decimal("5")
    slippage_bps: Decimal = Decimal("3")
    gate9_threshold: Decimal = Decimal("0.30")
    gate9_epsilon: Decimal = Decimal("0.000001")
    stop_loss_is_pct: bool = True


@dataclass(frozen=True)
class PreTradeResult:
    approved: bool
    reason: str
    adjusted_position_size: float
    violations: tuple[str, ...] = field(default_factory=tuple)
    sizing_snapshot: dict[str, str] = field(default_factory=dict)
    validated_notional_usd: str | None = None
    validated_sizing: ValidatedSizing | None = None


class PreTradeChecker:
    @staticmethod
    def _validated_sizing_snapshot(sizing: ValidatedSizing | None) -> dict[str, str]:
        if sizing is None:
            return {}
        return {
            "risk_usd": str(sizing.risk_usd),
            "sl_pct": str(sizing.sl_pct),
            "notional_usd": str(sizing.notional_usd),
            "fee_est_usd": str(sizing.fee_est_usd),
            "fee_risk_ratio": str(sizing.fee_risk_ratio),
        }

    def check(self, inp: PreTradeInput) -> PreTradeResult:
        violations: list[str] = []
        size = inp.position_size
        validated_sizing: ValidatedSizing | None = None
        max_leverage_limit = None
        if hasattr(inp, "max_leverage") and getattr(inp, "max_leverage") is not None:
            max_leverage_limit = float(getattr(inp, "max_leverage"))

        if size > inp.max_position_size:
            violations.append("position_size_limit")
        if max_leverage_limit is not None and inp.leverage > max_leverage_limit:
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

        if not violations:
            try:
                sl_value = Decimal(str(inp.stop_loss))
                if inp.stop_loss_is_pct:
                    sl_pct = sl_value
                else:
                    if inp.entry_price is None or inp.entry_price <= Decimal("0"):
                        raise ValueError("entry_price must be > 0 when stop_loss_is_pct=False")
                    sl_pct = sl_value / inp.entry_price

                risk_usd = inp.risk_usd
                if risk_usd is None:
                    # Backward-compatible fallback: infer risk budget from existing pre-trade inputs.
                    risk_usd = Decimal(str(size)) * sl_pct

                max_leverage: Decimal | None = None
                if hasattr(inp, "max_leverage") and getattr(inp, "max_leverage") is not None:
                    max_leverage = Decimal(str(getattr(inp, "max_leverage")))

                validated_sizing = compute_validated_size(
                    symbol=inp.symbol,
                    ts=inp.ts or datetime.now(timezone.utc),
                    risk_usd=risk_usd,
                    sl_pct=sl_pct,
                    price=inp.entry_price,
                    equity_usd=inp.equity_usd,
                    max_leverage=max_leverage,
                    fee_bps=inp.fee_bps,
                    slippage_bps=inp.slippage_bps,
                    gate9_threshold=Decimal(str(getattr(inp, "gate9_threshold", Decimal("0.30")))),
                    gate9_epsilon=Decimal(str(getattr(inp, "gate9_epsilon", Decimal("0.000001")))),
                )
            except ValueError as exc:
                violations.append(f"validated_sizing_invalid:{exc}")
            else:
                if not validated_sizing.passed_gate9:
                    violations.append("validated_sizing_reject")

        if violations:
            reason = violations[0]
            if validated_sizing is not None and not validated_sizing.passed_gate9:
                reason = validated_sizing.reason
            return PreTradeResult(
                approved=False,
                reason=reason,
                adjusted_position_size=max(size, 0.0),
                violations=tuple(violations),
                sizing_snapshot=self._validated_sizing_snapshot(validated_sizing),
                validated_notional_usd=(str(validated_sizing.notional_usd) if validated_sizing is not None else None),
                validated_sizing=validated_sizing,
            )

        return PreTradeResult(
            approved=True,
            reason="ok",
            adjusted_position_size=max(size, 0.0),
            violations=tuple(),
            sizing_snapshot=self._validated_sizing_snapshot(validated_sizing),
            validated_notional_usd=(str(validated_sizing.notional_usd) if validated_sizing is not None else None),
            validated_sizing=validated_sizing,
        )
