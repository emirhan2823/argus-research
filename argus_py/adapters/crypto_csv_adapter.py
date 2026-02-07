import os
from datetime import datetime

from argus_py.data.loader import DataLoader
from argus_py.data.market_state import MarketState

from .base import MarketAdapter, MarketLoadRequest


class CryptoCsvAdapter(MarketAdapter):
    name = "crypto_csv"

    def load_market(self, request: MarketLoadRequest) -> MarketState:
        if request.start_date and request.end_date:
            cache_file = f"{request.symbol}_1m_{request.start_date}_{request.end_date}.csv"
            cache_path = os.path.join(request.data_dir, cache_file)
            if os.path.exists(cache_path):
                bars = DataLoader.load_csv(cache_path)
                if request.max_bars is not None and request.max_bars > 0 and len(bars) > request.max_bars:
                    bars = bars[-request.max_bars:]
                return MarketState(
                    bars,
                    source_files=[cache_file],
                    symbol_requested=request.symbol,
                    symbol_resolved=request.symbol,
                )

            # Range cache does not exist: load symbol dataset without bar cap,
            # then apply date-range filter first, and max_bars second.
            market = DataLoader.load_from_dir(
                request.data_dir,
                max_bars=None,
                symbol=request.symbol,
                strict_symbol=request.strict_symbol,
            )
            start_ts = datetime.strptime(request.start_date, "%Y-%m-%d").timestamp()
            end_ts = datetime.strptime(request.end_date, "%Y-%m-%d").timestamp()
            bars = [b for b in market._all_bars if start_ts <= b.timestamp < end_ts]
            if request.max_bars is not None and request.max_bars > 0 and len(bars) > request.max_bars:
                bars = bars[-request.max_bars:]
            return MarketState(
                bars,
                source_files=market.source_files,
                symbol_requested=request.symbol,
                symbol_resolved=market.symbol_resolved or request.symbol,
            )

        return DataLoader.load_from_dir(
            request.data_dir,
            max_bars=request.max_bars,
            symbol=request.symbol,
            strict_symbol=request.strict_symbol,
        )
