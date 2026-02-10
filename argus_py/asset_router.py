from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from argus_py.adapters.contracts import (
    MarketAdapter,
    MarketRequest,
    OrderAdapter,
    OrderRequest,
    OrderResult,
    PositionAdapter,
    PositionSnapshot,
)
from argus_py.adapters.crypto_adapter import CryptoAdapter
from argus_py.adapters.defi_sim_adapter import DefiSimAdapter
from argus_py.adapters.stock_sim_adapter import StockSimAdapter
from argus_py.data.market_state import Bar


@dataclass(frozen=True)
class RouteSnapshot:
    requested_asset_class: str
    requested_venue_id: str
    effective_asset_class: str
    effective_venue_id: str
    adapter_id: str
    fallback_used: bool
    error: Optional[str] = None

    def telemetry_tags(self) -> Dict[str, str]:
        tags = {
            "asset_class": self.effective_asset_class,
            "venue_id": self.effective_venue_id,
            "asset_class_requested": self.requested_asset_class,
            "venue_id_requested": self.requested_venue_id,
            "adapter_id": self.adapter_id,
        }
        if self.fallback_used:
            tags["router_fallback"] = "1"
        return tags


class AssetRouter:
    """
    Unified v2 routing for market/order/position adapters.

    Safety contract:
    - Adapter errors never raise to caller.
    - Router returns empty bars or rejected orders with error details.
    - Optional fallback to crypto backend when selected backend fails.
    """

    def __init__(
        self,
        *,
        broker,
        asset_class: str = "crypto",
        venue_id: str = "auto",
        allow_fallback: bool = True,
    ) -> None:
        self.requested_asset_class = str(asset_class or "crypto").lower()
        self.requested_venue_id = str(venue_id or "auto").lower()
        self.allow_fallback = bool(allow_fallback)

        self._adapters = self._build_adapters(broker=broker, venue_id=self.requested_venue_id)
        self._primary_key = self.requested_asset_class if self.requested_asset_class in self._adapters else "crypto"
        self._fallback_key = "crypto"

        self._last_route = RouteSnapshot(
            requested_asset_class=self.requested_asset_class,
            requested_venue_id=self.requested_venue_id,
            effective_asset_class=self._primary_key,
            effective_venue_id=self._adapters[self._primary_key].venue_id,
            adapter_id=self._adapters[self._primary_key].adapter_id,
            fallback_used=False,
            error=None,
        )

    @property
    def route(self) -> RouteSnapshot:
        return self._last_route

    @property
    def market(self) -> MarketAdapter:
        return self._adapters[self._primary_key]

    @property
    def order(self) -> OrderAdapter:
        return self._adapters[self._primary_key]

    @property
    def position(self) -> PositionAdapter:
        return self._adapters[self._primary_key]

    def telemetry_tags(self) -> Dict[str, str]:
        return self._last_route.telemetry_tags()

    def fetch_klines(self, *, symbol: str, interval: str, limit: int, now_ts: Optional[float] = None) -> List[Bar]:
        request = MarketRequest(symbol=symbol, interval=interval, limit=limit, now_ts=now_ts)
        bars, route = self._try_fetch_with_fallback(request)
        self._last_route = route
        return bars

    def submit_order(
        self,
        *,
        symbol: str,
        decision: str,
        direction: str,
        price: float,
        timestamp: float,
        risk_pct: float,
        leverage: float = 1.0,
        custom_sl_price: Optional[float] = None,
        custom_tp_price: Optional[float] = None,
    ) -> OrderResult:
        adapter = self._adapters[self._primary_key]
        request = OrderRequest(
            symbol=symbol,
            decision=decision,
            direction=direction,
            price=float(price),
            timestamp=float(timestamp),
            risk_pct=float(risk_pct),
            leverage=float(leverage),
            custom_sl_price=custom_sl_price,
            custom_tp_price=custom_tp_price,
        )
        try:
            result = adapter.submit_order(request)
            self._last_route = RouteSnapshot(
                requested_asset_class=self.requested_asset_class,
                requested_venue_id=self.requested_venue_id,
                effective_asset_class=adapter.asset_class,
                effective_venue_id=adapter.venue_id,
                adapter_id=adapter.adapter_id,
                fallback_used=False,
                error=None,
            )
            return result
        except Exception as exc:
            self._last_route = RouteSnapshot(
                requested_asset_class=self.requested_asset_class,
                requested_venue_id=self.requested_venue_id,
                effective_asset_class=adapter.asset_class,
                effective_venue_id=adapter.venue_id,
                adapter_id=adapter.adapter_id,
                fallback_used=False,
                error=str(exc),
            )
            return OrderResult(accepted=False, reason=f"ROUTER_ORDER_ERROR: {exc}", venue_order_id=None)

    def get_position(self, symbol: str) -> PositionSnapshot:
        adapter = self._adapters[self._primary_key]
        try:
            snap = adapter.get_position(symbol)
            self._last_route = RouteSnapshot(
                requested_asset_class=self.requested_asset_class,
                requested_venue_id=self.requested_venue_id,
                effective_asset_class=adapter.asset_class,
                effective_venue_id=adapter.venue_id,
                adapter_id=adapter.adapter_id,
                fallback_used=False,
                error=None,
            )
            return snap
        except Exception as exc:
            self._last_route = RouteSnapshot(
                requested_asset_class=self.requested_asset_class,
                requested_venue_id=self.requested_venue_id,
                effective_asset_class=adapter.asset_class,
                effective_venue_id=adapter.venue_id,
                adapter_id=adapter.adapter_id,
                fallback_used=False,
                error=str(exc),
            )
            return PositionSnapshot(symbol=symbol, qty=0.0, side="FLAT", entry_price=0.0)

    def _try_fetch_with_fallback(self, request: MarketRequest) -> Tuple[List[Bar], RouteSnapshot]:
        primary = self._adapters[self._primary_key]
        try:
            bars = primary.fetch_klines(request)
            route = RouteSnapshot(
                requested_asset_class=self.requested_asset_class,
                requested_venue_id=self.requested_venue_id,
                effective_asset_class=primary.asset_class,
                effective_venue_id=primary.venue_id,
                adapter_id=primary.adapter_id,
                fallback_used=False,
                error=None,
            )
            return bars, route
        except Exception as primary_exc:
            if self.allow_fallback and self._primary_key != self._fallback_key:
                fallback = self._adapters[self._fallback_key]
                try:
                    bars = fallback.fetch_klines(request)
                    route = RouteSnapshot(
                        requested_asset_class=self.requested_asset_class,
                        requested_venue_id=self.requested_venue_id,
                        effective_asset_class=fallback.asset_class,
                        effective_venue_id=fallback.venue_id,
                        adapter_id=fallback.adapter_id,
                        fallback_used=True,
                        error=f"primary_failed:{primary_exc}",
                    )
                    return bars, route
                except Exception as fallback_exc:
                    route = RouteSnapshot(
                        requested_asset_class=self.requested_asset_class,
                        requested_venue_id=self.requested_venue_id,
                        effective_asset_class=primary.asset_class,
                        effective_venue_id=primary.venue_id,
                        adapter_id=primary.adapter_id,
                        fallback_used=True,
                        error=f"primary_failed:{primary_exc};fallback_failed:{fallback_exc}",
                    )
                    return [], route
            route = RouteSnapshot(
                requested_asset_class=self.requested_asset_class,
                requested_venue_id=self.requested_venue_id,
                effective_asset_class=primary.asset_class,
                effective_venue_id=primary.venue_id,
                adapter_id=primary.adapter_id,
                fallback_used=False,
                error=str(primary_exc),
            )
            return [], route

    def _build_adapters(self, *, broker, venue_id: str) -> Dict[str, object]:
        venue = str(venue_id or "auto")
        crypto_venue = "binance_spot_paper" if venue in {"", "auto"} else venue
        return {
            "crypto": CryptoAdapter(broker=broker, venue_id=crypto_venue),
            "stock": StockSimAdapter(broker=broker, venue_id="stock_sim_paper"),
            "defi": DefiSimAdapter(broker=broker, venue_id="defi_sim_paper"),
        }

