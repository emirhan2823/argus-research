"""Validated sizing contract for Phase G."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class ValidatedSizing(ArgusModel):
    """Fee-aware sizing output with Gate 9 decision."""

    symbol: str = Field(min_length=1, max_length=64)
    ts: datetime
    risk_usd: Decimal = Field(gt=Decimal("0"))
    sl_pct: Decimal = Field(gt=Decimal("0"))
    notional_usd: Decimal = Field(gt=Decimal("0"))
    leverage: Decimal | None = Field(default=None, gt=Decimal("0"))
    qty: Decimal | None = Field(default=None, gt=Decimal("0"))
    fee_est_usd: Decimal = Field(ge=Decimal("0"))
    fee_risk_ratio: Decimal = Field(ge=Decimal("0"))
    net_risk_usd: Decimal = Field(ge=Decimal("0"))
    passed_gate9: bool
    reason: str = Field(min_length=1, max_length=512)
