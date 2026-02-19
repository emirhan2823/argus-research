"""Ledger event contract for ARGUS v2.5."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.v25.contracts.base import ArgusModel


class LedgerEvent(ArgusModel):
    """Append-only financial event record."""

    event_id: str
    event_type: str
    symbol: str
    capital_engine: str
    amount: float
    balance_after: float
    equity_after: float
    position_id: Optional[str] = None
    metadata: dict[str, Any]
    timestamp: datetime

