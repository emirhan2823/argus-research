import os
from typing import List

from argus_py.data.loader import DataLoader
from argus_py.data.market_state import MarketState

from .base import MarketAdapter, MarketLoadRequest


class BistStubAdapter(MarketAdapter):
    """
    Initial stub for BIST symbols. Accepts either THYAO or THYAO.IS naming.
    """

    name = "bist_stub"

    def load_market(self, request: MarketLoadRequest) -> MarketState:
        symbol = request.symbol.upper()
        symbols = [symbol]
        if not symbol.endswith(".IS"):
            symbols.append(f"{symbol}.IS")

        candidates = self._candidate_files(request.data_dir, symbols, request.start_date, request.end_date)
        for path, resolved in candidates:
            if os.path.exists(path):
                bars = DataLoader.load_csv(path)
                return MarketState(
                    bars,
                    source_files=[os.path.basename(path)],
                    symbol_requested=symbol,
                    symbol_resolved=resolved,
                )

        expected = ", ".join(os.path.basename(p) for p, _ in candidates)
        raise FileNotFoundError(
            f"BIST stub adapter could not find data for {symbol}. "
            f"Expected one of: {expected}"
        )

    @staticmethod
    def _candidate_files(data_dir: str, symbols: List[str], start_date: str, end_date: str) -> List[tuple]:
        candidates = []
        for sym in symbols:
            if start_date and end_date:
                candidates.append((os.path.join(data_dir, f"{sym}_1m_{start_date}_{end_date}.csv"), sym))
            candidates.append((os.path.join(data_dir, f"{sym}.csv"), sym))
            candidates.append((os.path.join(data_dir, f"{sym}_1m.csv"), sym))
        return candidates
