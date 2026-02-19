"""Position state contract for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class PositionState(ArgusModel):
    """Open position state tracked by risk and telemetry layers."""

    position_id: str
    symbol: str
    side: str
    capital_engine: str
    size: float = Field(gt=0.0)
    entry_price: float = Field(gt=0.0)
    current_price: float = Field(gt=0.0)
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sl_price: float = Field(gt=0.0)
    tp_price: Optional[float] = Field(default=None, gt=0.0)
    trailing_sl: Optional[float] = Field(default=None, gt=0.0)
    entry_time: datetime
    duration_hours: float = Field(ge=0.0)
    exchange_sl_order_id: str
    engine: str
    sub_strategy: str
    regime_at_entry: str
    sqs_at_entry: float = Field(ge=0.0, le=1.0)
    confidence_at_entry: float = Field(ge=0.0, le=1.0)

