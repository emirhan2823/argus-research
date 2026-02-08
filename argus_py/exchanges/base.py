from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict


@dataclass
class Ticker:
    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float


@dataclass
class OrderFill:
    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    commission: float


class ExchangeAdapter(ABC):
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        ...

    @abstractmethod
    async def get_balance(self, asset: str) -> float:
        ...

    @abstractmethod
    async def get_positions(self) -> Dict[str, float]:
        ...

    @abstractmethod
    async def market_order(self, symbol: str, side: str, qty: float) -> OrderFill:
        ...

    @abstractmethod
    async def close_position(self, symbol: str) -> OrderFill:
        ...
