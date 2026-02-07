from .base import MarketAdapter
from .bist_stub import BistStubAdapter
from .crypto_csv_adapter import CryptoCsvAdapter
from .us_equity_stub import USEquityStubAdapter


def build_market_adapter(asset_class: str = "crypto", adapter_name: str = "auto") -> MarketAdapter:
    asset = (asset_class or "crypto").lower()
    adapter = (adapter_name or "auto").lower()

    if adapter == "auto":
        if asset == "crypto":
            return CryptoCsvAdapter()
        if asset == "us_equity":
            return USEquityStubAdapter()
        if asset == "bist":
            return BistStubAdapter()
        raise ValueError(f"Unsupported asset_class={asset_class}")

    if adapter == "crypto_csv":
        return CryptoCsvAdapter()
    if adapter == "us_equity_stub":
        return USEquityStubAdapter()
    if adapter == "bist_stub":
        return BistStubAdapter()

    raise ValueError(f"Unsupported market_adapter={adapter_name}")
