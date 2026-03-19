from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import hmac
import json
import time

import httpx

from .base import ExchangeAdapter, OrderFill, Ticker


class BybitAdapter(ExchangeAdapter):
    """Async Bybit v5 adapter with a unified interface."""

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
            "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        )
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _sign(self, timestamp: str, payload: str) -> str:
        prehash = f"{timestamp}{self.api_key}{self.recv_window}{payload}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            prehash.encode("utf-8"),
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
        payload = dict(params or {})
        headers: Dict[str, str] = {}
        method_u = method.upper()

        if signed:
            timestamp = str(int(time.time() * 1000))
            if method_u == "GET":
                payload_str = "&".join(f"{k}={v}" for k, v in sorted(payload.items()))
            else:
                payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

            headers.update(
                {
                    "X-BAPI-API-KEY": self.api_key,
                    "X-BAPI-TIMESTAMP": timestamp,
                    "X-BAPI-RECV-WINDOW": str(self.recv_window),
                    "X-BAPI-SIGN": self._sign(timestamp, payload_str),
                }
            )

        url = f"{self.base_url}{path}"
        if method_u == "GET":
            response = await self._client.get(url, params=payload, headers=headers)
        elif method_u == "POST":
            headers["Content-Type"] = "application/json"
            response = await self._client.post(url, json=payload, headers=headers)
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
        data = await self._request(
            "GET",
            "/v5/market/tickers",
            params={"category": "linear", "symbol": symbol},
        )
        rows = data.get("result", {}).get("list", [])
        row = rows[0] if rows else {}
        return Ticker(
            symbol=symbol,
            bid=self._to_float(row.get("bid1Price")),
            ask=self._to_float(row.get("ask1Price")),
            last=self._to_float(row.get("lastPrice")),
            volume_24h=self._to_float(row.get("volume24h")),
        )

    async def get_balance(self, asset: str) -> float:
        data = await self._request(
            "GET",
            "/v5/account/wallet-balance",
            params={"accountType": "UNIFIED"},
            signed=True,
        )
        accounts = data.get("result", {}).get("list", [])
        if not accounts:
            return 0.0

        coins = accounts[0].get("coin", [])
        for coin in coins:
            if str(coin.get("coin", "")).upper() == asset.upper():
                return self._to_float(coin.get("availableToWithdraw", coin.get("walletBalance", 0.0)))
        return 0.0

    async def get_positions(self) -> Dict[str, float]:
        data = await self._request(
            "GET",
            "/v5/position/list",
            params={"category": "linear", "settleCoin": "USDT"},
            signed=True,
        )

        positions: Dict[str, float] = {}
        for row in data.get("result", {}).get("list", []):
            symbol = str(row.get("symbol", ""))
            size = self._to_float(row.get("size"))
            side = str(row.get("side", "")).upper()
            qty = -size if side == "SELL" else size
            if symbol and qty != 0.0:
                positions[symbol] = qty
        return positions

    async def market_order(self, symbol: str, side: str, qty: float) -> OrderFill:
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side.upper().capitalize(),
            "orderType": "Market",
            "qty": str(qty),
        }
        data = await self._request("POST", "/v5/order/create", params=payload, signed=True)
        order_id = str(data.get("result", {}).get("orderId", ""))

        return OrderFill(
            order_id=order_id,
            symbol=symbol,
            side=side.upper(),
            price=0.0,
            quantity=qty,
            commission=0.0,
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
