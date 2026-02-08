from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

import hashlib
import hmac
import time

import httpx


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class LiveConfig:
    api_key: str
    api_secret: str
    testnet: bool = True
    base_url: Optional[str] = None
    max_order_value: float = 100.0
    max_daily_volume: float = 1000.0
    require_confirmation: bool = True

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = "https://testnet.binancefuture.com" if self.testnet else "https://fapi.binance.com"


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    reduce_only: bool = False


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    fill_price: Optional[float]
    fill_quantity: Optional[float]
    commission: Optional[float]
    error: Optional[str]


class LiveBroker:
    """
    Live Binance Futures broker with safety guardrails.

    SAFETY FEATURES:
    - Testnet by default
    - Max order value cap
    - Max daily volume cap
    - Optional confirmation prompt
    - All orders logged
    """

    def __init__(self, config: LiveConfig, client: Optional[httpx.Client] = None):
        self.config = config
        self.daily_volume = 0.0
        self.orders_today = []
        self._client = client or httpx.Client(timeout=10.0)

    def _sign(self, params: Dict) -> str:
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.config.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict) -> Dict:
        payload = dict(params)
        payload["timestamp"] = int(time.time() * 1000)
        payload["signature"] = self._sign(payload)

        headers = {"X-MBX-APIKEY": self.config.api_key}
        url = f"{self.config.base_url}{endpoint}"

        if method == "GET":
            response = self._client.get(url, params=payload, headers=headers)
        else:
            response = self._client.post(url, params=payload, headers=headers)

        response.raise_for_status()
        return response.json()

    def get_account(self) -> Dict:
        return self._request("GET", "/fapi/v2/account", {})

    def get_positions(self) -> Dict[str, float]:
        account = self.get_account()
        positions: Dict[str, float] = {}
        for pos in account.get("positions", []):
            amt = float(pos.get("positionAmt", 0.0))
            if amt != 0:
                positions[str(pos["symbol"])] = amt
        return positions

    def get_balance(self) -> float:
        account = self.get_account()
        for asset in account.get("assets", []):
            if asset.get("asset") == "USDT":
                return float(asset.get("availableBalance", 0.0))
        return 0.0

    def _check_safety(self, order: OrderRequest, notional: float) -> Tuple[bool, str]:
        if notional > self.config.max_order_value:
            return False, f"Order value ${notional:.2f} exceeds max ${self.config.max_order_value}"

        if self.daily_volume + notional > self.config.max_daily_volume:
            return False, f"Would exceed daily volume limit ${self.config.max_daily_volume}"

        return True, "OK"

    def execute(self, order: OrderRequest, current_price: float) -> OrderResult:
        notional = order.quantity * current_price

        safe, reason = self._check_safety(order, notional)
        if not safe:
            return OrderResult(False, None, None, None, None, reason)

        if self.config.require_confirmation:
            print("LIVE ORDER CONFIRMATION")
            print(f"  {order.side.value} {order.quantity} {order.symbol}")
            print(f"  Notional: ${notional:.2f}")
            confirm = input("  Type 'YES' to confirm: ")
            if confirm != "YES":
                return OrderResult(False, None, None, None, None, "User cancelled")

        try:
            params = {
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.order_type.value,
                "quantity": order.quantity,
            }
            if order.reduce_only:
                params["reduceOnly"] = "true"
            if order.order_type == OrderType.LIMIT and order.price is not None:
                params["price"] = order.price
                params["timeInForce"] = "GTC"

            result = self._request("POST", "/fapi/v1/order", params)

            self.daily_volume += notional
            self.orders_today.append({"time": time.time(), "order": order, "result": result})

            return OrderResult(
                success=True,
                order_id=str(result.get("orderId")) if result.get("orderId") is not None else None,
                fill_price=float(result.get("avgPrice", current_price)),
                fill_quantity=float(result.get("executedQty", order.quantity)),
                commission=float(result.get("commission", 0.0)),
                error=None,
            )
        except Exception as exc:
            return OrderResult(False, None, None, None, None, str(exc))

    def close_position(self, symbol: str, current_price: float) -> OrderResult:
        positions = self.get_positions()
        if symbol not in positions:
            return OrderResult(False, None, None, None, None, "No position")

        qty = abs(positions[symbol])
        side = OrderSide.SELL if positions[symbol] > 0 else OrderSide.BUY

        return self.execute(
            OrderRequest(symbol=symbol, side=side, quantity=qty, reduce_only=True),
            current_price,
        )
