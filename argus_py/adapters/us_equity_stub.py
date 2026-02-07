import os
from typing import List

from argus_py.data.loader import DataLoader
from argus_py.data.market_state import MarketState

from .base import MarketAdapter, MarketLoadRequest


class USEquityStubAdapter(MarketAdapter):
    """
    Initial stub for US equities. It loads local CSV if present and otherwise
    fails fast with a clear contract message.
    """

    name = "us_equity_stub"

    def load_market(self, request: MarketLoadRequest) -> MarketState:
        symbol = request.symbol.upper()
        candidates = self._candidate_files(request.data_dir, symbol, request.start_date, request.end_date)
        for path in candidates:
            if os.path.exists(path):
                bars = DataLoader.load_csv(path)
                return MarketState(
                    bars,
                    source_files=[os.path.basename(path)],
                    symbol_requested=symbol,
                    symbol_resolved=symbol,
                )

        expected = ", ".join(os.path.basename(p) for p in candidates)
        raise FileNotFoundError(
            f"US equity stub adapter could not find data for {symbol}. "
            f"Expected one of: {expected}"
        )

    @staticmethod
    def _candidate_files(data_dir: str, symbol: str, start_date: str, end_date: str) -> List[str]:
        files = []
        if start_date and end_date:
            files.append(os.path.join(data_dir, f"{symbol}_1m_{start_date}_{end_date}.csv"))
        files.append(os.path.join(data_dir, f"{symbol}.csv"))
        files.append(os.path.join(data_dir, f"{symbol}_1m.csv"))
        return files
