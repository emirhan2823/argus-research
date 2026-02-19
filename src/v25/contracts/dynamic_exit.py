"""Dynamic exit contracts for Phase H skeleton."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class ExitStage(str, Enum):
    ENTRY = "ENTRY"
    BREAKEVEN_LOCK = "BREAKEVEN_LOCK"
    PROFIT_CAPTURE = "PROFIT_CAPTURE"
    TREND_RIDER = "TREND_RIDER"


class ExitActionType(str, Enum):
    NOOP = "NOOP"
    UPDATE_STOP = "UPDATE_STOP"
    TAKE_PARTIAL = "TAKE_PARTIAL"


class DynamicExitState(ArgusModel):
    stage: ExitStage
    side: str = Field(default="LONG", pattern=r"^(LONG|SHORT)$")
    entry_price: Decimal = Field(gt=Decimal("0"))
    stop_price: Decimal = Field(gt=Decimal("0"))
    tp1_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    tp2_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    tp3_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    last_update_ts: datetime
    reason: str = Field(min_length=1, max_length=512)


class ExitAction(ArgusModel):
    action_type: ExitActionType
    new_stop_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    take_profit_fraction: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1"))
    stage_before: ExitStage
    stage_after: ExitStage
    reason: str = Field(min_length=1, max_length=512)
