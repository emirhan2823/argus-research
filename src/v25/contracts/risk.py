"""Risk contracts for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field, model_validator

from src.v25.contracts.base import (
    ArgusModel,
    NonNegativeDecimal,
    PositiveDecimal,
    RatioDecimal,
    TimestampedModel,
)
from src.v25.contracts.signal import RegimeType
from src.v25.contracts.trade import CapitalEngine


class CircuitBreakerLevel(int, Enum):
    NORMAL = 0
    REDUCED_SIZE = 1
    TREND_ONLY = 2
    EXIT_ONLY = 3
    LOCKDOWN = 4


class RiskLimits(TimestampedModel):
    per_trade_risk: dict[RegimeType, RatioDecimal]
    max_gross_exposure: dict[RegimeType, RatioDecimal]
    min_cash_reserve: dict[RegimeType, RatioDecimal]
    daily_loss_cap_by_regime: dict[RegimeType, RatioDecimal]
    total_daily_loss_cap: RatioDecimal
    max_leverage: PositiveDecimal
    drawdown_levels: tuple[RatioDecimal, RatioDecimal, RatioDecimal, RatioDecimal]
    cooldown_after_2_losses_min: int = Field(default=60, ge=0)
    block_after_3_losses_until_eod: bool = True
    same_asset_quarantine_hours: int = Field(default=24, ge=0)
    black_swan_price_drop_15m_pct: RatioDecimal
    black_swan_spread_mult: PositiveDecimal
    black_swan_funding_rate_max: NonNegativeDecimal
    black_swan_volume_spike_mult: PositiveDecimal
    max_exchange_api_errors: int = Field(default=3, ge=1)
    config_version: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_regime_maps(self) -> "RiskLimits":
        expected = set(RegimeType)
        for name, regime_map in (
            ("per_trade_risk", self.per_trade_risk),
            ("max_gross_exposure", self.max_gross_exposure),
            ("min_cash_reserve", self.min_cash_reserve),
            ("daily_loss_cap_by_regime", self.daily_loss_cap_by_regime),
        ):
            if set(regime_map.keys()) != expected:
                raise ValueError(f"{name} must include all RegimeType keys")
        return self


class PositionSize(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    regime: RegimeType
    capital_engine: CapitalEngine
    equity: PositiveDecimal
    available_equity: NonNegativeDecimal
    risk_pct: RatioDecimal
    risk_amount: NonNegativeDecimal
    stop_distance_pct: PositiveDecimal
    stop_distance_abs: PositiveDecimal
    quantity: PositiveDecimal
    notional: PositiveDecimal
    leverage: PositiveDecimal
    gross_exposure_pct: RatioDecimal
    net_exposure_pct: Decimal = Field(max_digits=20, decimal_places=10)
    equity_momentum_multiplier: NonNegativeDecimal = Decimal("1")
    accel_multiplier: NonNegativeDecimal = Decimal("1")
    circuit_breaker_multiplier: NonNegativeDecimal = Decimal("1")
    source: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _validate_available_equity(self) -> "PositionSize":
        if self.available_equity > self.equity:
            raise ValueError("available_equity cannot exceed equity")
        return self


class CircuitBreakerState(ArgusModel):
    level: CircuitBreakerLevel
    drawdown_pct: RatioDecimal
    daily_loss_pct: RatioDecimal
    peak_equity: PositiveDecimal
    current_equity: PositiveDecimal
    trading_enabled: bool
    new_entries_enabled: bool
    exit_only_mode: bool
    reason: str = Field(min_length=1, max_length=512)
    entered_at: datetime
    cooldown_until: datetime | None = None
    consecutive_losses: int = Field(default=0, ge=0)
    quarantined_symbols: tuple[str, ...] = ()
    manual_override_required: bool = False

    @model_validator(mode="after")
    def _validate_cooldown(self) -> "CircuitBreakerState":
        if self.cooldown_until is not None and self.cooldown_until < self.entered_at:
            raise ValueError("cooldown_until must be >= entered_at")
        return self
