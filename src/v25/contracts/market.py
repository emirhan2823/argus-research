"""Market contracts for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

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


class MarketSnapshot(TimestampedModel):
    """Backward-compatible market snapshot contract used by Package-0 tests."""

    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=16)
    open: float = Field(gt=0.0)
    high: float = Field(gt=0.0)
    low: float = Field(gt=0.0)
    close: float = Field(gt=0.0)
    volume: float = Field(ge=0.0)
    quote_volume: float = Field(default=0.0, ge=0.0)
    trades_count: int = Field(default=0, ge=0)
    funding_rate: float | None = None
    open_interest: float | None = Field(default=None, ge=0.0)
    mark_price: float | None = Field(default=None, gt=0.0)
    orderbook_bids_5: list[tuple[float, float]] = Field(default_factory=list)
    orderbook_asks_5: list[tuple[float, float]] = Field(default_factory=list)
    data_quality_score: float = Field(ge=0.0, le=1.0)
    source: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _validate_prices(self) -> "MarketSnapshot":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open/close/low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open/close/high")
        return self


class FeatureVector(TimestampedModel):
    """Backward-compatible feature vector contract used by Package-0 tests."""

    symbol: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)

    atr_14: float = Field(gt=0.0)
    atr_14_pct: float
    atr_ratio_5_20: float
    realized_vol_20d: float
    parkinson_vol: float
    bb_width: float
    adx_14: float
    price_vs_ma200: float
    ema_21_vs_55: float
    lr_slope_20: float
    supertrend_dir: int = Field(ge=-1, le=1)
    aroon_osc: float
    rsi_14: float
    bb_pct_b: float
    roc_10: float
    willr_14: float
    cci_20: float

    volume_ratio: float = Field(ge=0.0)
    obv_slope_10: float
    vwap_dev_pct: float
    cmf_20: float
    volume_delta: float

    spread_pct: float = Field(ge=0.0)
    orderbook_imbalance: float
    trade_flow_imbalance: float
    depth_ratio: float = Field(ge=0.0)
    large_trade_ratio: float = Field(ge=0.0)

    funding_rate: float | None = None
    funding_pctile_30d: float | None = None
    oi_change_4h_pct: float | None = None
    oi_change_24h_pct: float | None = None
    liquidation_est: float | None = None
    long_short_ratio: float | None = None
    basis_pct: float | None = None

    btc_dominance_delta_24h: float | None = None
    btc_eth_corr_30d: float | None = None
    total_mcap_momentum: float | None = None
    stablecoin_flow: float | None = None

    return_autocorr_20: float | None = None
    hurst_exponent: float | None = None
    entropy_50: float | None = None
    frac_diff_price: float | None = None

    hermes_sentiment_score: float = Field(ge=-100.0, le=100.0)
    hermes_sentiment_confidence: float = Field(ge=0.0, le=1.0)
    hermes_urgency: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"]

    chronos_forecast_1h: float | None = None
    chronos_confidence_width: float | None = None
    lgbm_direction: int | None = Field(default=None, ge=-1, le=1)
    lgbm_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    meta_label_score: float | None = Field(default=None, ge=0.0, le=1.0)

    regime_prob_trending: float = Field(ge=0.0, le=1.0)
    regime_prob_ranging: float = Field(ge=0.0, le=1.0)
    regime_prob_volatile: float = Field(ge=0.0, le=1.0)
