from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

from .base import ExchangeAdapter, OrderFill, Ticker


class BinanceAdapter(ExchangeAdapter):
    """Async Binance Futures adapter with a unified interface."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        testnet: bool = True,
        base_url: Optional[str] = None,
        recv_window: int = 5000,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.recv_window = recv_window
        self.base_url = base_url or (
            "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"
        )
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _sign(self, params: Dict[str, Any]) -> str:
        query = urlencode(sorted(params.items()))
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = dict(params or {})
        headers: Dict[str, str] = {}

        if signed:
            payload["timestamp"] = int(time.time() * 1000)
            payload.setdefault("recvWindow", self.recv_window)
            payload["signature"] = self._sign(payload)
            headers["X-MBX-APIKEY"] = self.api_key

        url = f"{self.base_url}{path}"
        method_u = method.upper()

        if method_u == "GET":
            response = await self._client.get(url, params=payload, headers=headers)
        elif method_u == "POST":
            response = await self._client.post(url, params=payload, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    async def get_ticker(self, symbol: str) -> Ticker:
        data = await self._request("GET", "/fapi/v1/ticker/24hr", params={"symbol": symbol})
        return Ticker(
            symbol=symbol,
            bid=self._to_float(data.get("bidPrice")),
            ask=self._to_float(data.get("askPrice")),
            last=self._to_float(data.get("lastPrice")),
            volume_24h=self._to_float(data.get("volume")),
        )

    async def get_balance(self, asset: str) -> float:
        items = await self._request("GET", "/fapi/v2/balance", signed=True)
        if isinstance(items, list):
            for row in items:
                if str(row.get("asset", "")).upper() == asset.upper():
                    return self._to_float(row.get("availableBalance", row.get("balance", 0.0)))
        return 0.0

    async def get_positions(self) -> Dict[str, float]:
        account = await self._request("GET", "/fapi/v2/account", signed=True)
        positions: Dict[str, float] = {}
        for row in account.get("positions", []):
            symbol = str(row.get("symbol", ""))
            qty = self._to_float(row.get("positionAmt"))
            if symbol and qty != 0.0:
                positions[symbol] = qty
        return positions

    async def market_order(self, symbol: str, side: str, qty: float) -> OrderFill:
        payload = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": qty,
        }
        data = await self._request("POST", "/fapi/v1/order", params=payload, signed=True)

        executed_qty = self._to_float(data.get("executedQty"), qty)
        avg_price = self._to_float(data.get("avgPrice"))
        if avg_price == 0.0:
            cum_quote = self._to_float(data.get("cumQuote"))
            avg_price = cum_quote / executed_qty if executed_qty > 0 else 0.0

        return OrderFill(
            order_id=str(data.get("orderId", "")),
            symbol=symbol,
            side=side.upper(),
            price=avg_price,
            quantity=executed_qty,
            commission=self._to_float(data.get("commission")),
        )

    async def close_position(self, symbol: str) -> OrderFill:
        positions = await self.get_positions()
        qty = positions.get(symbol, 0.0)
        if qty == 0.0:
            return OrderFill(
                order_id="NO_POSITION",
                symbol=symbol,
                side="FLAT",
                price=0.0,
                quantity=0.0,
                commission=0.0,
            )

        side = "SELL" if qty > 0 else "BUY"
        return await self.market_order(symbol, side, abs(qty))
