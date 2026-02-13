from __future__ import annotations

from pathlib import Path
from typing import List

from argus_py.adapters.base import MarketAdapter, MarketLoadRequest
from argus_py.data.loader import DataLoader
from argus_py.data.market_state import MarketState


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
            if path.exists():
                bars = DataLoader.load_csv(str(path))
                return MarketState(
                    bars,
                    source_files=[path.name],
                    symbol_requested=symbol,
                    symbol_resolved=resolved,
                )

        expected = ", ".join(path.name for path, _ in candidates)
        raise FileNotFoundError(
            f"BIST stub adapter could not find data for {symbol}. "
            f"Expected one of: {expected}"
        )

    @staticmethod
    def _candidate_files(
        data_dir: str,
        symbols: List[str],
        start_date: str | None,
        end_date: str | None,
    ) -> List[tuple[Path, str]]:
        base_dir = Path(data_dir)
        candidates: List[tuple[Path, str]] = []
        for sym in symbols:
            if start_date and end_date:
                candidates.append((base_dir / f"{sym}_1m_{start_date}_{end_date}.csv", sym))
            candidates.append((base_dir / f"{sym}.csv", sym))
            candidates.append((base_dir / f"{sym}_1m.csv", sym))
        return candidates
