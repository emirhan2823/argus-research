"""Trading contracts for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from src.v25.contracts.base import (
    ArgusModel,
    NonNegativeDecimal,
    PositiveDecimal,
    RatioDecimal,
    TimestampedModel,
)
from src.v25.contracts.market import MarketVenue
from src.v25.contracts.signal import RegimeType, TemplateName


class TradeSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class CapitalEngine(str, Enum):
    CORE = "core"
    ACCEL = "accel"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_MARKET = "take_profit_market"


class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "POST_ONLY"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class LiquiditySide(str, Enum):
    MAKER = "maker"
    TAKER = "taker"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class OrderRequest(TimestampedModel):
    request_id: UUID = Field(default_factory=uuid4)
    client_order_id: str | None = Field(default=None, min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    venue: MarketVenue = MarketVenue.BINGX
    side: TradeSide
    order_type: OrderType
    time_in_force: TimeInForce = TimeInForce.GTC
    quantity: PositiveDecimal | None = None
    quote_quantity: PositiveDecimal | None = None
    limit_price: PositiveDecimal | None = None
    stop_price: PositiveDecimal | None = None
    leverage: PositiveDecimal = Decimal("1")
    reduce_only: bool = False
    post_only: bool = False
    strategy_tag: str | None = Field(default=None, min_length=1, max_length=128)
    template_name: TemplateName | None = None
    risk_id: str | None = Field(default=None, min_length=1, max_length=128)
    expire_time: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_order_fields(self) -> "OrderRequest":
        if self.quantity is None and self.quote_quantity is None:
            raise ValueError("Either quantity or quote_quantity must be provided")
        if self.order_type in {OrderType.LIMIT, OrderType.TAKE_PROFIT} and self.limit_price is None:
            raise ValueError("limit_price is required for limit-style orders")
        if self.order_type in {OrderType.STOP, OrderType.STOP_MARKET, OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_MARKET} and self.stop_price is None:
            raise ValueError("stop_price is required for stop/take-profit orders")
        if self.expire_time is not None and self.expire_time < self.timestamp:
            raise ValueError("expire_time must be >= timestamp")
        return self


class ExecutionFill(ArgusModel):
    fill_id: str = Field(min_length=1, max_length=128)
    order_id: str = Field(min_length=1, max_length=128)
    client_order_id: str | None = Field(default=None, min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    venue: MarketVenue = MarketVenue.BINGX
    side: TradeSide
    status: OrderStatus
    quantity: PositiveDecimal
    price: PositiveDecimal
    quote_amount: NonNegativeDecimal
    fee: NonNegativeDecimal = Decimal("0")
    fee_asset: str | None = Field(default=None, min_length=1, max_length=32)
    liquidity: LiquiditySide = LiquiditySide.TAKER
    slippage_pct: Decimal = Field(default=Decimal("0"), max_digits=20, decimal_places=10)
    executed_at: datetime
    exchange_trade_id: str | None = Field(default=None, min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Position(TimestampedModel):
    position_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    venue: MarketVenue = MarketVenue.BINGX
    side: TradeSide
    capital_engine: CapitalEngine
    status: PositionStatus = PositionStatus.OPEN
    quantity: PositiveDecimal
    entry_price: PositiveDecimal
    mark_price: PositiveDecimal
    leverage: PositiveDecimal
    notional: PositiveDecimal
    liquidation_price: PositiveDecimal | None = None
    unrealized_pnl: Decimal = Field(max_digits=38, decimal_places=18)
    unrealized_pnl_pct: Decimal = Field(max_digits=20, decimal_places=10)
    realized_pnl: Decimal = Field(default=Decimal("0"), max_digits=38, decimal_places=18)
    fees_paid: NonNegativeDecimal = Decimal("0")
    stop_loss_price: PositiveDecimal | None = None
    take_profit_price: PositiveDecimal | None = None
    opened_at: datetime
    updated_at: datetime
    regime_at_entry: RegimeType
    template_at_entry: TemplateName | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_position_timestamps(self) -> "Position":
        if self.updated_at < self.opened_at:
            raise ValueError("updated_at must be >= opened_at")
        return self


class TradeRecord(ArgusModel):
    trade_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    side: TradeSide
    capital_engine: CapitalEngine
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: PositiveDecimal
    exit_price: PositiveDecimal | None = None
    size: PositiveDecimal
    pnl: Decimal | None = Field(default=None, max_digits=38, decimal_places=18)
    pnl_pct: Decimal | None = Field(default=None, max_digits=20, decimal_places=10)
    fees: NonNegativeDecimal = Decimal("0")
    slippage: NonNegativeDecimal = Decimal("0")
    net_pnl_pct: Decimal | None = Field(default=None, max_digits=20, decimal_places=10)
    regime_at_entry: RegimeType
    regime_at_exit: RegimeType | None = None
    engine: str = Field(min_length=1, max_length=64)
    sub_strategy: str = Field(min_length=1, max_length=64)
    confidence: RatioDecimal
    sqs_score: RatioDecimal
    stop_distance: PositiveDecimal
    duration_hours: NonNegativeDecimal | None = None
    reason_entry: str = Field(min_length=1, max_length=512)
    reason_exit: str | None = Field(default=None, min_length=1, max_length=512)
    features_json: dict[str, Any] | None = None
    config_hash: str | None = Field(default=None, min_length=1, max_length=128)
    created_at: datetime
    fills: tuple[ExecutionFill, ...] = ()

    @model_validator(mode="after")
    def _validate_trade_times(self) -> "TradeRecord":
        if self.exit_time is not None and self.exit_time < self.entry_time:
            raise ValueError("exit_time must be >= entry_time")
        return self
