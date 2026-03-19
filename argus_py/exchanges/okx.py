from __future__ import annotations

from typing import Any, Dict, Optional
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from .base import ExchangeAdapter, OrderFill, Ticker


class OKXAdapter(ExchangeAdapter):
    """Async OKX adapter with a unified interface."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        *,
        testnet: bool = True,
        base_url: str = "https://www.okx.com",
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.testnet = testnet
        self.base_url = base_url
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _iso_ts(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        prehash = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            prehash.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        payload = dict(params or {})
        method_u = method.upper()
        headers: Dict[str, str] = {}

        req_path = path
        body = ""
        if method_u == "GET" and payload:
            req_path = f"{path}?{urlencode(payload)}"
        elif method_u != "GET" and payload:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True)

        if signed:
            ts = self._iso_ts()
            headers.update(
                {
                    "OK-ACCESS-KEY": self.api_key,
                    "OK-ACCESS-PASSPHRASE": self.passphrase,
                    "OK-ACCESS-TIMESTAMP": ts,
                    "OK-ACCESS-SIGN": self._sign(ts, method_u, req_path, body),
                }
            )
            if self.testnet:
                headers["x-simulated-trading"] = "1"

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
        data = await self._request("GET", "/api/v5/market/ticker", params={"instId": symbol})
        rows = data.get("data", [])
        row = rows[0] if rows else {}
        return Ticker(
            symbol=symbol,
            bid=self._to_float(row.get("bidPx")),
            ask=self._to_float(row.get("askPx")),
            last=self._to_float(row.get("last")),
            volume_24h=self._to_float(row.get("vol24h")),
        )

    async def get_balance(self, asset: str) -> float:
        data = await self._request(
            "GET",
            "/api/v5/account/balance",
            params={"ccy": asset.upper()},
            signed=True,
        )
        accounts = data.get("data", [])
        if not accounts:
            return 0.0

        for detail in accounts[0].get("details", []):
            if str(detail.get("ccy", "")).upper() == asset.upper():
                return self._to_float(detail.get("availEq", detail.get("eq", 0.0)))
        return 0.0

    async def get_positions(self) -> Dict[str, float]:
        data = await self._request("GET", "/api/v5/account/positions", signed=True)
        positions: Dict[str, float] = {}

        for row in data.get("data", []):
            symbol = str(row.get("instId", ""))
            qty = self._to_float(row.get("pos"))
            side = str(row.get("posSide", row.get("side", ""))).lower()
            if side in {"short", "sell"}:
                qty = -abs(qty)
            if symbol and qty != 0.0:
                positions[symbol] = qty

        return positions

    async def market_order(self, symbol: str, side: str, qty: float) -> OrderFill:
        payload = {
            "instId": symbol,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "market",
            "sz": str(qty),
        }
        data = await self._request("POST", "/api/v5/trade/order", params=payload, signed=True)
        rows = data.get("data", [])
        row = rows[0] if rows else {}

        return OrderFill(
            order_id=str(row.get("ordId", "")),
            symbol=symbol,
            side=side.upper(),
            price=self._to_float(row.get("fillPx")),
            quantity=self._to_float(row.get("fillSz"), qty),
            commission=self._to_float(row.get("fee")),
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
