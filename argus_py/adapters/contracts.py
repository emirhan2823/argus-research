from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol

from argus_py.data.market_state import Bar


@dataclass(frozen=True)
class MarketRequest:
    symbol: str
    interval: str
    limit: int
    now_ts: Optional[float] = None


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    decision: str
    direction: str
    price: float
    timestamp: float
    risk_pct: float
    leverage: float = 1.0
    custom_sl_price: Optional[float] = None
    custom_tp_price: Optional[float] = None


@dataclass(frozen=True)
class OrderResult:
    accepted: bool
    reason: str
    venue_order_id: Optional[str] = None


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    qty: float
    side: str
    entry_price: float


class MarketAdapter(Protocol):
    adapter_id: str
    asset_class: str
    venue_id: str

    def fetch_klines(self, request: MarketRequest) -> List[Bar]:
        raise NotImplementedError


class OrderAdapter(Protocol):
    adapter_id: str
    asset_class: str
    venue_id: str

    def submit_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError


class PositionAdapter(Protocol):
    adapter_id: str
    asset_class: str
    venue_id: str

    def get_position(self, symbol: str) -> PositionSnapshot:
        raise NotImplementedError

