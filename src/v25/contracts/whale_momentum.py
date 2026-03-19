"""Whale momentum signal contract for Hermes offensive boost."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class WhaleMomentumSignal(ArgusModel):
    symbol: str = Field(min_length=1, max_length=64)
    ts: datetime
    regime: str = Field(min_length=1, max_length=64)
    netflow_score: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"))
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    boost_c5: Decimal = Field(ge=Decimal("0"), le=Decimal("0.10"))
    allowed: bool
    reason: str = Field(min_length=1, max_length=256)
