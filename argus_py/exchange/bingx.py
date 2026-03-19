import os
import time
import hmac
import hashlib
import requests
import json
from typing import List, Dict, Optional
from argus_py.exchange.base import ExchangeAdapter, ExchangeOrder, OrderResult

class BingXAdapter(ExchangeAdapter):
    BASE_URL = "https://open-api.bingx.com" # Check docs for actual URL
    
    def __init__(self, api_key: str = None, api_secret: str = None, dry_run: bool = True):
        self.api_key = api_key or os.environ.get("BINGX_API_KEY")
        self.api_secret = api_secret or os.environ.get("BINGX_SECRET")
        self.dry_run = dry_run
        
        if not self.dry_run and (not self.api_key or not self.api_secret):
             print("WARNING: BingX Adapter initialized in LIVE mode without keys! Forcing Dry Run.")
             self.dry_run = True

    def _sign(self, params: Dict) -> str:
        """
        Generate signature for BingX API.
        Sort params, create query string, sign with HMAC SHA256.
        """
        params_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode("utf-8"), 
            params_str.encode("utf-8"), 
            hashlib.sha256
        ).hexdigest()

    def get_public_candles(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """
        Fetch candles from BingX.
        Mapping interval names if necessary (e.g. 15m -> 15m).
        """
        endpoint = "/openApi/spot/v2/market/kline" # Example generic endpoint
        # In real impl, check docs for exact endpoint (spot vs swap)
        
        # Placeholder for connection
        # If no internet, return empty or mock? 
        # For this exercise, we assume connectivity will exist in live.
        # But during my coding session I can't hit it.
        # so I will just return empty list or raise.
        # However, the user wants "Paper -> Live Bridge", so maybe I should allow
        # downloading data via the existing DataLoader for backfill, and only use this for live updates?
        # For now, implementing the request structure.
        
        try:
            params = {
               "symbol": symbol,
               "interval": interval,
               "limit": limit
            }
            # resp = requests.get(f"{self.BASE_URL}{endpoint}", params=params)
            # return self._parse_candles(resp.json())
            return [] 
        except Exception as e:
            print(f"BingX Error: {e}")
            return []

    def get_balance(self, asset: str) -> float:
        if self.dry_run:
            return 1000.0 # Mock balance
            
        # Implementation for live balance fetch
        return 0.0

    def get_position(self, symbol: str) -> Optional[Dict]:
        if self.dry_run:
            return None
        return None

    def place_order(self, order: ExchangeOrder) -> OrderResult:
        if self.dry_run:
            # Emulate success
            print(f"[DRY_RUN] Placing Order: {order}")
            return OrderResult(
                success=True,
                order_id=f"dry_{int(time.time())}",
                client_order_id=order.client_order_id
            )
            
        # Real Order Implementation
        # 1. Prepare params
        # 2. Sign
        # 3. POST /openApi/spot/v1/trade/order (Example)
        
        print(f"[LIVE] Placing Order: {order}")
        # result = requests.post(...)
        
        # Stub
        return OrderResult(success=False, order_id="", client_order_id=order.client_order_id, error_message="Not Implemented")

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        if self.dry_run: return True
        return False
