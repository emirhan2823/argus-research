"""Market contracts for ARGUS v2.5."""

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


class MarketVenue(str, Enum):
    BINGX = "bingx"
    BINANCE = "binance"
    YAHOO = "yahoo"
    COINGECKO = "coingecko"
    INTERNAL = "internal"


class OHLCV(ArgusModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=16)
    open_time: datetime
    close_time: datetime
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal
    quote_volume: NonNegativeDecimal = Decimal("0")
    trades_count: int = Field(default=0, ge=0)
    vwap: PositiveDecimal | None = None
    venue: MarketVenue = MarketVenue.BINGX
    is_final: bool = True

    @model_validator(mode="after")
    def _validate_ohlc(self) -> "OHLCV":
        max_price = max(self.open, self.close, self.low)
        min_price = min(self.open, self.close, self.high)
        if self.high < max_price:
            raise ValueError("high must be >= open, close, and low")
        if self.low > min_price:
            raise ValueError("low must be <= open, close, and high")
        if self.close_time < self.open_time:
            raise ValueError("close_time must be >= open_time")
        return self


class OrderbookLevel(ArgusModel):
    price: PositiveDecimal
    size: NonNegativeDecimal
    order_count: int | None = Field(default=None, ge=0)


class Orderbook(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    venue: MarketVenue = MarketVenue.BINGX
    bids: tuple[OrderbookLevel, ...] = Field(min_length=1)
    asks: tuple[OrderbookLevel, ...] = Field(min_length=1)
    best_bid: PositiveDecimal
    best_ask: PositiveDecimal
    mid_price: PositiveDecimal
    spread_abs: NonNegativeDecimal
    spread_pct: RatioDecimal
    checksum: str | None = Field(default=None, min_length=1, max_length=128)
    sequence_id: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_spread(self) -> "Orderbook":
        if self.best_ask < self.best_bid:
            raise ValueError("best_ask must be >= best_bid")
        return self


class Ticker(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    venue: MarketVenue = MarketVenue.BINGX
    last_price: PositiveDecimal
    bid_price: PositiveDecimal
    ask_price: PositiveDecimal
    mark_price: PositiveDecimal | None = None
    index_price: PositiveDecimal | None = None
    high_24h: PositiveDecimal
    low_24h: PositiveDecimal
    volume_24h: NonNegativeDecimal
    turnover_24h: NonNegativeDecimal
    open_interest: NonNegativeDecimal | None = None
    funding_rate: Decimal | None = None
    price_change_24h: Decimal
    price_change_pct_24h: Decimal

    @model_validator(mode="after")
    def _validate_ticker_prices(self) -> "Ticker":
        if self.ask_price < self.bid_price:
            raise ValueError("ask_price must be >= bid_price")
        if self.high_24h < max(self.last_price, self.low_24h):
            raise ValueError("high_24h must be >= last_price and low_24h")
        if self.low_24h > min(self.last_price, self.high_24h):
            raise ValueError("low_24h must be <= last_price and high_24h")
        return self


class FundingRate(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    venue: MarketVenue = MarketVenue.BINGX
    funding_rate: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"), max_digits=20, decimal_places=10)
    predicted_funding_rate: Decimal | None = Field(
        default=None,
        ge=Decimal("-1"),
        le=Decimal("1"),
        max_digits=20,
        decimal_places=10,
    )
    funding_interval_hours: int = Field(default=8, ge=1, le=24)
    next_funding_time: datetime
    mark_price: PositiveDecimal | None = None
    index_price: PositiveDecimal | None = None

    @model_validator(mode="after")
    def _validate_schedule(self) -> "FundingRate":
        if self.next_funding_time < self.timestamp:
            raise ValueError("next_funding_time must be >= timestamp")
        return self
