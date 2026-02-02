from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class Bar:
    timestamp: float  # Unix timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def dt(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

class MarketState:
    """
    Time-traveling data container.
    Guarantees no lookahead bias by restricting access to bars beyond current_index.
    """
    def __init__(self, bars: List[Bar], source_files: List[str] = None, symbol_requested: str = None, symbol_resolved: str = None):
        self._all_bars = bars
        self._current_idx = -1
        self.source_files = source_files or []
        self.symbol_requested = symbol_requested
        self.symbol_resolved = symbol_resolved

    def set_time(self, index: int):
        if index < 0 or index >= len(self._all_bars):
            raise ValueError(f"Index {index} out of bounds (0-{len(self._all_bars)-1})")
        self._current_idx = index

    @property
    def latest_bar(self) -> Bar:
        if self._current_idx < 0:
            raise ValueError("MarketState not initialized (idx=-1)")
        return self._all_bars[self._current_idx]

    @property
    def history(self) -> List[Bar]:
        """Returns bars from start up to current_index (inclusive)."""
        if self._current_idx < 0:
             return []
        return self._all_bars[:self._current_idx+1]
        
    @property
    def current_price(self) -> float:
        return self.latest_bar.close

    @property
    def can_advance(self) -> bool:
        return self._current_idx < len(self._all_bars) - 1

    def advance(self) -> bool:
        if self.can_advance:
            self._current_idx += 1
            return True
        return False
