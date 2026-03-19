"""Order-intent contracts for execution-agnostic action routing."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class OrderIntentType(str, Enum):
    NOOP = "NOOP"
    UPDATE_STOP = "UPDATE_STOP"
    TAKE_PARTIAL = "TAKE_PARTIAL"
    CLOSE_POSITION = "CLOSE_POSITION"


class OrderIntent(ArgusModel):
    action_type: OrderIntentType
    symbol: str = Field(min_length=1, max_length=64)
    new_stop_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    take_profit_fraction: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1"))
    reason: str = Field(min_length=1, max_length=512)
    source: str = Field(min_length=1, max_length=64)
    ts: datetime
