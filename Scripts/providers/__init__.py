"""Provider registry for multi-provider backfill tooling."""

from __future__ import annotations

from typing import Any

from Scripts.providers.base import OHLCVProvider
from Scripts.providers.binance_provider import BinanceProvider
from Scripts.providers.bybit_provider import BybitProvider
from Scripts.providers.kraken_provider import KrakenProvider
from Scripts.providers.okx_provider import OkxProvider

_PROVIDERS: dict[str, type[OHLCVProvider]] = {
    "binance": BinanceProvider,
    "okx": OkxProvider,
    "kraken": KrakenProvider,
    "bybit": BybitProvider,
}


def available_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())


def create_provider(name: str, **kwargs: Any) -> OHLCVProvider:
    key = name.strip().lower()
    if key not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {', '.join(available_providers())}")
    provider_cls = _PROVIDERS[key]
    return provider_cls(**kwargs)
