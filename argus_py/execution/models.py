from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ExecutionIntent:
    symbol: str
    side: OrderSide
    qty: float
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    urgency: UrgencyLevel = UrgencyLevel.NORMAL
    client_order_id: Optional[str] = None
    reduce_only: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExchangeOrder:
    order_id: str
    status: str
    filled_qty: float
    avg_price: float
    side: OrderSide
    symbol: str


@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    order_id: Optional[str]
    status: str
    reason: str
    stop_loss_enforced: bool
    reconciliation_delta: float
    requested_qty: float = 0.0
    filled_qty: float = 0.0
    avg_price: float = 0.0
    metadata: Dict[str, object] = field(default_factory=dict)


__all__ = [
    "OrderSide",
    "UrgencyLevel",
    "ExecutionIntent",
    "ExchangeOrder",
    "ExecutionResult",
]
