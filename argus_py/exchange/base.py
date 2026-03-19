from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ExchangeOrder:
    symbol: str
    side: str # BUY, SELL
    type: str # MARKET, LIMIT
    quantity: float
    price: Optional[float]
    client_order_id: str
    params: Dict[str, Any]

@dataclass
class OrderResult:
    success: bool
    order_id: str
    client_order_id: str
    error_message: Optional[str] = None
    filled_qty: float = 0.0
    filled_price: float = 0.0

class ExchangeAdapter(ABC):
    """
    Abstract Base Class for Exchange Adapters.
    Enforces a common interface for fetching data and placing orders.
    """
    
    @abstractmethod
    def get_public_candles(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """
        Fetch OHLCV candles. 
        Returns list of dicts: {'timestamp': ms, 'open': float, ...}
        """
        pass

    @abstractmethod
    def get_balance(self, asset: str) -> float:
        """
        Get available balance for a specific asset (e.g. USDT).
        """
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current open position for symbol.
        Returns None if no position, else dict with quantity, entryPrice, etc.
        """
        pass

    @abstractmethod
    def place_order(self, order: ExchangeOrder) -> OrderResult:
        """
        Place an order on the exchange.
        """
        pass
        
    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel a specific order.
        """
        pass
