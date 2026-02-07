from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from argus_py.data.market_state import MarketState


@dataclass(frozen=True)
class MarketLoadRequest:
    data_dir: str
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_bars: Optional[int] = None
    strict_symbol: bool = True


class MarketAdapter(ABC):
    name = "base"

    @abstractmethod
    def load_market(self, request: MarketLoadRequest) -> MarketState:
        """Load market bars for backtest/research runtime."""
        raise NotImplementedError
