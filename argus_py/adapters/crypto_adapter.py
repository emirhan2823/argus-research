from __future__ import annotations

import time
from typing import List

import requests

from argus_py.adapters.contracts import (
    MarketRequest,
    OrderRequest,
    OrderResult,
    PositionSnapshot,
)
from argus_py.data.market_state import Bar


class CryptoAdapter:
    """
    Crypto backend for v2 runtime.
    Market data comes from Binance klines.
    Orders/positions are delegated to existing paper broker.
    """

    adapter_id = "crypto_adapter_v2"
    asset_class = "crypto"

    def __init__(self, broker, venue_id: str = "binance_spot_paper", timeout_sec: float = 10.0) -> None:
        self.broker = broker
        self.venue_id = str(venue_id or "binance_spot_paper")
        self.timeout_sec = float(timeout_sec)

    def fetch_klines(self, request: MarketRequest) -> List[Bar]:
        limit = max(1, int(request.limit))
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": str(request.symbol).upper(),
            "interval": str(request.interval),
            "limit": limit,
        }
        resp = requests.get(url, params=params, timeout=self.timeout_sec)
        if resp.status_code != 200:
            raise RuntimeError(f"Binance klines request failed: status={resp.status_code}")
        raw = resp.json()
        out: List[Bar] = []
        for row in raw:
            out.append(
                Bar(
                    timestamp=float(row[0]) / 1000.0,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        return out

    def submit_order(self, request: OrderRequest) -> OrderResult:
        accepted, reason = self.broker.execute_strategy(
            symbol=request.symbol,
            decision=request.decision,
            direction=request.direction,
            price=float(request.price),
            timestamp=float(request.timestamp),
            risk_pct=float(request.risk_pct),
            leverage=float(request.leverage),
            custom_sl_price=request.custom_sl_price,
            custom_tp_price=request.custom_tp_price,
        )
        oid = None
        if accepted and getattr(self.broker, "trades", None):
            oid = f"paper:{int(time.time() * 1000)}:{len(self.broker.trades)}"
        return OrderResult(accepted=bool(accepted), reason=str(reason), venue_order_id=oid)

    def get_position(self, symbol: str) -> PositionSnapshot:
        pos = getattr(self.broker, "details", {}).get(symbol)
        if pos is None:
            return PositionSnapshot(symbol=symbol, qty=0.0, side="FLAT", entry_price=0.0)
        qty = float(getattr(pos, "quantity", 0.0))
        side = str(getattr(pos, "side", "FLAT")).upper()
        entry = float(getattr(pos, "entry_price", 0.0))
        return PositionSnapshot(symbol=symbol, qty=qty, side=side, entry_price=entry)

