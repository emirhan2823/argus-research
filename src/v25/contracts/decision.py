"""Decision contracts for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class TradeDecision(ArgusModel):
    """Final trade intent after gates and risk."""

    action: Literal["long", "short", "hold", "close_all", "reduce"]
    capital_engine: Literal["core", "accel"]
    position_size_pct: float = Field(ge=0.0, le=0.15)
    leverage: float = Field(ge=1.0, le=3.0)
    stop_loss_pct: float = Field(ge=0.01, le=0.05)
    take_profit_pct: float = Field(gt=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    engine: Optional[str] = None
    sub_strategy: Optional[str] = None
    reason: str
    sqs_at_decision: float = Field(ge=0.0, le=1.0)
    regime_at_decision: str
    timestamp: datetime


class SizingDecision(ArgusModel):
    """Sizer trace contract with multipliers and final outputs."""

    raw_risk_pct: float = Field(ge=0.0)
    atlas_mult: float = Field(ge=0.0)
    sentinel_mult: float = Field(ge=0.0)
    regime_conf_mult: float = Field(ge=0.0)
    dd_mult: float = Field(ge=0.0)
    rsl_mult: float = Field(ge=0.0)
    equity_curve_mult: float = Field(ge=0.0)
    final_risk_pct: float = Field(ge=0.005, le=0.03)
    position_size_pct: float = Field(ge=0.0, le=0.15)
    leverage: float = Field(ge=1.0, le=3.0)
    capital_engine: Literal["core", "accel"]
    kelly_fraction: Optional[float] = Field(default=None, ge=0.0)
    timestamp: datetime


class ExecutionPlan(ArgusModel):
    """Execution plan contract (stub in Package 0)."""

    order_type: Literal["market", "limit", "aggressive_limit", "passive_limit"]
    urgency: Literal["EMERGENCY", "HIGH", "NORMAL", "LOW"]
    side: Literal["buy", "sell"]
    symbol: str
    quantity: float = Field(gt=0.0)
    price: Optional[float] = Field(default=None, gt=0.0)
    sl_price: float = Field(gt=0.0)
    tp_price: Optional[float] = Field(default=None, gt=0.0)
    timeout_ms: int = Field(gt=0)
    max_slippage_pct: float = Field(ge=0.0)
    timestamp: datetime

