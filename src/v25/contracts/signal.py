"""Signal contracts for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import Field

from src.v25.contracts.base import (
    ArgusModel,
    PositiveDecimal,
    RatioDecimal,
    SignedUnitDecimal,
    TimestampedModel,
)


class RegimeType(str, Enum):
    TREND_STRONG = "TREND_STRONG"
    TREND_WEAK = "TREND_WEAK"
    CHOP = "CHOP"
    VOLATILE = "VOLATILE"
    CRISIS = "CRISIS"


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class TemplateName(str, Enum):
    TREND_PULLBACK = "TREND_PULLBACK"
    TREND_BREAKOUT = "TREND_BREAKOUT"
    CHOP_EXTREME = "CHOP_EXTREME"
    CHOP_FAILED_BREAKOUT = "CHOP_FAILED_BREAKOUT"
    CHOP_CORR_GAP = "CHOP_CORR_GAP"
    CHOP_MICRO_REVERSION = "CHOP_MICRO_REVERSION"
    CORR_MEAN_REVERSION = "CORR_MEAN_REVERSION"
    CORR_DECOUPLING_ARB = "CORR_DECOUPLING_ARB"
    VOLATILE_HIGH_SQS = "VOLATILE_HIGH_SQS"
    CRISIS_EXIT = "CRISIS_EXIT"


class SQSScore(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=16)
    regime: RegimeType
    template: TemplateName | None = None
    total_score: RatioDecimal
    regime_consistency: RatioDecimal
    trend_structure: RatioDecimal
    microstructure: RatioDecimal
    fee_adjusted_expectancy: RatioDecimal
    hermes_news_risk: RatioDecimal
    threshold_used: RatioDecimal
    passed: bool
    reason_if_failed: str | None = Field(default=None, min_length=1, max_length=512)
    model_version: str | None = Field(default=None, min_length=1, max_length=64)
    components: dict[str, RatioDecimal] = Field(default_factory=dict)


class ChopEdgeScore(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=16)
    regime: RegimeType = RegimeType.CHOP
    template: TemplateName
    range_definition_quality: RatioDecimal
    boundary_rejection_strength: RatioDecimal
    failed_breakout_quality: RatioDecimal
    liquidity_stability: RatioDecimal
    htf_alignment: RatioDecimal
    total_score: RatioDecimal
    threshold_go: RatioDecimal
    threshold_caution: RatioDecimal
    passed: bool
    notes: str | None = Field(default=None, min_length=1, max_length=512)


class SignalTemplate(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=16)
    regime: RegimeType
    name: TemplateName
    direction: SignalDirection
    confidence: RatioDecimal
    sqs_score: RatioDecimal
    edge_score: RatioDecimal | None = None
    entry_price: PositiveDecimal | None = None
    stop_loss_price: PositiveDecimal | None = None
    take_profit_price: PositiveDecimal | None = None
    expected_r_multiple: Decimal = Field(ge=Decimal("0"), max_digits=20, decimal_places=10)
    is_valid: bool
    invalid_reason: str | None = Field(default=None, min_length=1, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sentiment_bias: SignedUnitDecimal = Decimal("0")


class Signal(ArgusModel):
    """Backward-compatible signal contract used by Package-0 tests."""

    engine: str = Field(min_length=1, max_length=64)
    sub_strategy: str | None = Field(default=None, min_length=1, max_length=128)
    bias: Literal["long", "short", "flat"]
    confidence: float = Field(ge=0.0, le=1.0)
    stop_distance: float = Field(gt=0.0, le=0.10)
    take_profit_distance: float = Field(gt=0.0)
    expected_return: float
    atr: float = Field(gt=0.0)
    regime_at_signal: str = Field(min_length=1, max_length=64)
    timestamp: datetime


class SignalQualityScore(ArgusModel):
    """Backward-compatible SQS contract used by Package-0 tests."""

    total_score: float = Field(ge=0.0, le=1.0)
    regime_consistency: float = Field(ge=0.0, le=1.0)
    trend_range_structure: float = Field(ge=0.0, le=1.0)
    microstructure_quality: float = Field(ge=0.0, le=1.0)
    fee_adjusted_expectancy: float = Field(ge=0.0, le=1.0)
    hermes_news_risk: float = Field(ge=0.0, le=1.0)
    passed: bool
    threshold_used: float = Field(ge=0.0, le=1.0)
    reason_if_failed: str | None = Field(default=None, max_length=512)
    timestamp: datetime


class ConfidenceState(ArgusModel):
    """Backward-compatible confidence state contract used by Package-0 tests."""

    alignment_score: float = Field(ge=0.0, le=1.0)
    regime_confidence: float = Field(ge=0.0, le=1.0)
    signal_confidence: float = Field(ge=0.0, le=1.0)
    sqs_score: float = Field(ge=0.0, le=1.0)
    atlas_multiplier: float = Field(ge=0.0, le=1.5)
    composite: float = Field(ge=0.0, le=1.0)
    accel_eligible: bool
    timestamp: datetime
