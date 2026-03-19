"""Intelligence contracts for ARGUS v2.5."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from src.v25.contracts.base import (
    ArgusModel,
    NonNegativeDecimal,
    PositiveDecimal,
    RatioDecimal,
    SignedUnitDecimal,
    TimestampedModel,
)


class SentimentLabel(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class NewsCategory(str, Enum):
    REGULATORY = "REGULATORY"
    HACK = "HACK"
    PARTNERSHIP = "PARTNERSHIP"
    MACRO = "MACRO"
    TECHNICAL = "TECHNICAL"
    ADOPTION = "ADOPTION"
    SCAM = "SCAM"
    OTHER = "OTHER"


class NewsUrgency(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    HOURS = "HOURS"
    DAYS = "DAYS"
    IRRELEVANT = "IRRELEVANT"


class WhaleDirection(str, Enum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    UNKNOWN = "UNKNOWN"


class NewsAnalysis(TimestampedModel):
    analysis_id: UUID = Field(default_factory=uuid4)
    headline: str = Field(min_length=1, max_length=1024)
    source: str = Field(min_length=1, max_length=128)
    published_at: str = Field(min_length=1, max_length=64)
    sentiment: SentimentLabel
    impact_score: RatioDecimal
    affected_assets: tuple[str, ...] = Field(min_length=1)
    category: NewsCategory
    urgency: NewsUrgency
    confidence: RatioDecimal
    reasoning: str = Field(min_length=1, max_length=4096)
    model_name: str = Field(default="local-8b", min_length=1, max_length=128)
    model_version: str | None = Field(default=None, min_length=1, max_length=64)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    raw_output_json: dict[str, Any] = Field(default_factory=dict)


class WhaleAlert(TimestampedModel):
    alert_id: UUID = Field(default_factory=uuid4)
    chain: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=64)
    direction: WhaleDirection
    amount_asset: PositiveDecimal
    amount_usd: PositiveDecimal
    wallet_address: str | None = Field(default=None, min_length=8, max_length=256)
    wallet_label: str | None = Field(default=None, min_length=1, max_length=128)
    exchange: str | None = Field(default=None, min_length=1, max_length=64)
    tx_hash: str | None = Field(default=None, min_length=8, max_length=256)
    confidence: RatioDecimal
    source: str = Field(min_length=1, max_length=128)
    is_verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SentimentSnapshot(TimestampedModel):
    symbol: str | None = Field(default=None, min_length=1, max_length=64)
    news_score: SignedUnitDecimal
    social_score: SignedUnitDecimal
    onchain_score: SignedUnitDecimal
    macro_score: SignedUnitDecimal
    fear_greed_index: int | None = Field(default=None, ge=0, le=100)
    composite_score: SignedUnitDecimal
    confidence: RatioDecimal
    risk_modifier: NonNegativeDecimal = Decimal("1")
    dominant_sentiment: SentimentLabel
    urgent_event: bool = False
    headline_count: int = Field(default=0, ge=0)
    whale_alert_count: int = Field(default=0, ge=0)
    source_weights: dict[str, RatioDecimal] = Field(default_factory=dict)
    notes: str | None = Field(default=None, min_length=1, max_length=1024)


class WhaleMomentumSignal(TimestampedModel):
    """Aggregated whale flow momentum for trend amplification (Blueprint Pivot 4).

    Fields align with the TECHNICAL_BLUEPRINT specification and the
    ``whale_momentum_log`` DB table (FIX-02).
    """

    symbol: str = Field(min_length=1, max_length=64)
    net_flow_usd_24h: Decimal
    exchange_reserve_change_pct: Decimal
    stablecoin_mint_usd_24h: NonNegativeDecimal = Decimal("0")
    accumulation_addresses: int = Field(default=0, ge=0)
    is_bullish_flow: bool
    is_bearish_flow: bool
    momentum_score: SignedUnitDecimal
    sqs_boost: RatioDecimal
    size_modifier: NonNegativeDecimal = Decimal("1")
    confidence: RatioDecimal
