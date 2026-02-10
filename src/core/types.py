"""ARGUS v2.0 — Core data models.

All models: pydantic v2, frozen=True, strict=True, extra='forbid'.
NaN rejection on all non-Optional float fields via model_validator.
Multi-asset aware: all relevant models carry asset_class field.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArgusModel(BaseModel):
    """Base model for all ARGUS data contracts."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    @model_validator(mode="after")
    def _reject_nan(self) -> "ArgusModel":
        for field_name, field_info in self.__class__.model_fields.items():
            val = getattr(self, field_name)
            if isinstance(val, float) and math.isnan(val):
                # Allow NaN only for Optional fields that default to None
                if field_info.default is not None:
                    raise ValueError(f"NaN not allowed for field '{field_name}'")
        return self


class FeatureVector(ArgusModel):
    """Feature snapshot for a single symbol at a single timestamp.

    Core technical features (17) are required for ALL asset classes.
    Crypto-native features (7) are Optional — None for non-crypto.
    """

    timestamp: datetime
    symbol: str
    asset_class: str  # "crypto" | "us_equity" | "commodity" | "index" | "bist"

    # --- Volatility (6) ---
    atr_14: float
    atr_14_pct: float
    atr_ratio_5_20: float
    realized_vol_20d: float
    parkinson_vol: float
    bb_width: float

    # --- Trend (6) ---
    adx_14: float
    price_vs_ma200: float
    ema_21_vs_55: float
    lr_slope_20: float
    supertrend_dir: int  # +1 / -1
    aroon_osc: float

    # --- Momentum (5) ---
    rsi_14: float
    bb_pct_b: float
    roc_10: float
    willr_14: float
    cci_20: float

    # --- Volume (5) ---
    volume_ratio: float
    obv_slope_10: float
    vwap_dev_pct: float
    cmf_20: float
    volume_delta: float

    # --- Microstructure (5) — Some Optional for non-crypto ---
    spread_pct: float
    orderbook_imbalance: Optional[float] = None
    trade_flow_imbalance: Optional[float] = None
    depth_ratio: Optional[float] = None
    large_trade_ratio: Optional[float] = None

    # --- Crypto-Native (7) — ALL Optional, None for non-crypto ---
    funding_rate: Optional[float] = None
    funding_pctile_30d: Optional[float] = None
    oi_change_4h_pct: Optional[float] = None
    oi_change_24h_pct: Optional[float] = None
    liquidation_est: Optional[float] = None
    long_short_ratio: Optional[float] = None
    basis_pct: Optional[float] = None

    # --- Cross-Asset (4) — Optional ---
    btc_dominance_delta_24h: Optional[float] = None
    btc_eth_corr_30d: Optional[float] = None
    total_mcap_momentum: Optional[float] = None
    stablecoin_flow: Optional[float] = None

    # --- Statistical (4) ---
    return_autocorr_20: float
    hurst_exponent: float
    entropy_50: float
    frac_diff_price: float

    # --- Sentiment (3) — from HERMES ---
    hermes_sentiment_score: Optional[float] = None  # -100 to +100
    hermes_sentiment_confidence: Optional[float] = None
    hermes_urgency: Optional[str] = None  # "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"

    # --- ML Output (8) — None if not active ---
    chronos_forecast_1h: Optional[float] = None
    chronos_confidence_width: Optional[float] = None
    lgbm_direction: Optional[int] = None
    lgbm_confidence: Optional[float] = None
    meta_label_score: Optional[float] = None
    regime_prob_trending: Optional[float] = None
    regime_prob_ranging: Optional[float] = None
    regime_prob_volatile: Optional[float] = None


class RegimeState(ArgusModel):
    """Current regime determination snapshot."""

    regime: str  # "TRENDING" | "RANGING" | "VOLATILE" | "CRISIS"
    confidence: float = Field(ge=0.0, le=1.0)
    stability: float = Field(ge=0.0, le=1.0)
    direction: Optional[int] = None  # +1 / -1 / None
    pending_transition: Optional[str] = None
    candles_in_regime: int = Field(ge=0)
    rule_regime: str
    ml_regime: str
    hermes_override: Optional[str] = None  # If HERMES forced regime change
    timestamp: datetime


class EngineSignal(ArgusModel):
    """Signal output from an engine."""

    engine: str  # "TITAN" | "NAUTILUS" | "PHOENIX" | "HERMES"
    sub_strategy: str
    asset_class: str
    symbol: str
    bias: str  # "long" | "short"
    confidence: float = Field(ge=0.0, le=1.0)
    stop_distance: float = Field(gt=0.0, le=0.10)  # Wider for stocks
    expected_return: float
    atr: float


class Decision(ArgusModel):
    """Final trading decision before execution."""

    action: str  # "long" | "short" | "hold" | "close_all" | "reduce" | "adjust_sl" | "adjust_tp"
    asset_class: str
    symbol: str
    execution_mode: str  # "auto" | "advisory"
    position_size: float = Field(ge=0.0, le=0.15)
    leverage: float = Field(ge=1.0, le=3.0)
    stop_loss: float = Field(ge=0.0, le=0.10)  # Wider for stocks
    take_profit: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    engine: Optional[str] = None
    reason: str
    # Advisory fields (for human operator)
    suggested_entry_price: Optional[float] = None
    tp_levels: Optional[list[float]] = None  # Multiple TP targets
    conditional_alerts: Optional[list[str]] = None  # "If price reaches X, do Y"
    timestamp: datetime


class NewsSentiment(ArgusModel):
    """HERMES news sentiment output."""

    headline: str
    source: str
    asset_class: str
    affected_symbols: list[str]
    sentiment_score: float = Field(ge=-100.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    action: str  # "NONE" | "BLOCK_ENTRY" | "CLOSE_POSITION" | "ADJUST_SL" | "ADJUST_TP" | "ALERT_ONLY"
    reasoning: str
    timestamp: datetime


class RiskVerdict(ArgusModel):
    """Output of the risk verification layer."""

    approved: bool
    reason: str
    adjusted_decision: Optional[Decision] = None
    risk_level: int = Field(ge=0, le=4)


class ExecutionResult(ArgusModel):
    """Result of an order execution attempt."""

    success: bool
    execution_mode: str  # "auto" | "advisory"
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None
    slippage: Optional[float] = None
    fees: Optional[float] = None
    sl_order_id: Optional[str] = None
    advisory_message: Optional[str] = None  # For advisory mode
    reason: str
    timestamp: datetime


class Position(ArgusModel):
    """A currently open position."""

    symbol: str
    asset_class: str
    side: str  # "long" | "short"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sl_price: float
    tp_price: Optional[float] = None
    entry_time: datetime
    duration_hours: float
    exchange_sl_order_id: str  # MUST exist for auto mode
    execution_mode: str  # "auto" | "advisory"


class PortfolioState(ArgusModel):
    """Full portfolio snapshot."""

    total_equity: float
    available_balance: float
    positions: list[Position]
    has_positions: bool
    daily_pnl: float
    daily_pnl_pct: float
    drawdown: float
    peak_equity: float
    trades_today: int
    consecutive_losses: int
    equity_ma_20d: float
    # Multi-asset allocation
    allocation_crypto_pct: float
    allocation_equity_pct: float
    allocation_commodity_pct: float
    allocation_cash_pct: float
    timestamp: datetime


class TradeRecord(ArgusModel):
    """Completed trade record for telemetry."""

    trade_id: str
    symbol: str
    asset_class: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fees: float
    slippage: float
    net_pnl_pct: float
    regime_at_entry: str
    regime_at_exit: str
    engine: str
    sub_strategy: str
    confidence_at_entry: float
    stop_distance: float
    duration_hours: float
    features_at_entry: dict
    reason_entry: str
    reason_exit: str
    execution_mode: str  # "auto" | "advisory"


class TelemetryEvent(ArgusModel):
    """Generic telemetry event record."""

    event_type: str
    timestamp: datetime
    run_id: str
    inputs_hash: Optional[str] = None
