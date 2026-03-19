"""Regime contracts for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class RegimeState(ArgusModel):
    """Detected market regime and its confidence state."""

    regime: Literal["TREND", "CHOP", "VOLATILE", "CRISIS"]
    sub_regime: Optional[Literal["STRONG_TREND", "WEAK_TREND"]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    stability: float = Field(ge=0.0, le=1.0)
    direction: Optional[int] = None
    pending_transition: Optional[str] = None
    candles_in_regime: int = Field(ge=0)
    rule_regime: str
    ml_regime: str
    chop_midpoint: Optional[float] = None
    timestamp: datetime

