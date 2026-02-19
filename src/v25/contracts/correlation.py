"""Correlation engine contracts for ARGUS v2.5 (Phase A)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from src.v25.contracts.base import (
    ArgusModel,
    NonNegativeDecimal,
    RatioDecimal,
    SignedUnitDecimal,
    TimestampedModel,
)


class CorrelationPair(TimestampedModel):
    """State of a tracked asset pair."""

    pair_id: str  # e.g. "BTCUSDT_ETHUSDT"
    symbol_a: str
    symbol_b: str
    correlation: SignedUnitDecimal
    spread_zscore: Decimal
    half_life_bars: Decimal | None = None  # None if not mean-reverting
    is_cointegrated: bool = False
    cointegration_pvalue: Decimal | None = None
    regime: str = "STABLE"  # "STABLE" | "DIVERGING" | "CONVERGING" | "DECOUPLED"


class CorrelationSignal(TimestampedModel):
    """Trading signal generated from correlation state."""

    pair_id: str
    signal_type: str  # "MEAN_REVERSION" | "DECOUPLING_ARB" | "CONVERGENCE"
    direction_a: str  # "LONG" | "SHORT" | "NONE"
    direction_b: str
    confidence: RatioDecimal
    spread_zscore_at_signal: Decimal
    target_zscore: Decimal  # Expected reversion target
    stop_zscore: Decimal  # Stop loss z-score level
    reason: str


class CorrelationHealth(ArgusModel):
    """Health metrics for the correlation tracking system."""

    total_pairs: int = Field(ge=0)
    active_pairs: int = Field(ge=0)
    cointegrated_count: int = Field(ge=0)
    avg_correlation: Decimal
    min_half_life: Decimal | None = None
    last_update_age_seconds: NonNegativeDecimal
