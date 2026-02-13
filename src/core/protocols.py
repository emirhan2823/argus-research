"""Shared protocol contracts for pluggable strategy dependencies."""

from __future__ import annotations

from typing import Protocol, Sequence


class ILeverageProvider(Protocol):
    """Chiron leverage policy contract."""

    def get_leverage_multiplier(
        self,
        *,
        symbol: str,
        asset_class: str,
        regime: str,
        confidence: float,
    ) -> float:
        ...


class IPriceForecaster(Protocol):
    """Oracle-compatible price forecasting contract."""

    def forecast_price(
        self,
        *,
        symbol: str,
        price_series: Sequence[float],
        horizon: int = 1,
    ) -> float:
        ...
