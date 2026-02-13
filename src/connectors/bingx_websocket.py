import asyncio
import aiohttp
import json
import logging
import time
import numpy as np
import pandas as pd
from typing import Callable, Optional

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BingX_WS")

class BingXWebSocket:
    """
    Robust WebSocket connector for BingX Futures.
    Handles auto-reconnect, dual streams (Depth/Kline), and data buffering.
    """
    def __init__(self, symbol: str, callback_depth: Callable, callback_kline: Callable):
        self.symbol = symbol.replace('/', '-') # BingX format usually XAU-USDT
        self.url = "wss://open-api-swap.bingx.com/swap-market" # Example URL, check docs
        self.callback_depth = callback_depth
        self.callback_kline = callback_kline

        self.running = False
        self.ws = None
        self.session = None

        # Backoff Strategy
        self.reconnect_delay = 1
        self.max_reconnect_delay = 32

        # Throttling / Conflation
        self.last_depth_ts = 0
        self.depth_throttle_ms = 100 # Max 10 updates/sec

    async def connect(self):
        """
        Main connection loop with exponential backoff.
        """
        self.running = True
        self.session = aiohttp.ClientSession()

        while self.running:
            try:
                logger.info(f"Connecting to BingX WS ({self.symbol})...")
                async with self.session.ws_connect(self.url) as ws:
                    self.ws = ws
                    self.reconnect_delay = 1 # Reset backoff on success
                    logger.info("Connected!")

                    # Subscribe to Channels
                    await self._subscribe()

                    # Heartbeat Loop
                    asyncio.create_task(self._heartbeat())

                    # Listen Loop
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            # BingX sends compressed binary data (gzip) usually
                            # Need decompression here if applicable.
                            # For simplicity/mock, assuming text/json.
                            pass
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WS Error: {ws.exception()}")
                            break

            except Exception as e:
                logger.error(f"Connection Failed: {e}")

            if self.running:
                logger.warning(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _subscribe(self):
        """
        Subscribes to Depth and Kline channels.
        """
        # Example Subscription Payload (Check BingX API Docs for exact format)
        payload = {
            "id": "sub_depth_kline",
            "reqType": "sub",
            "dataType": f"{self.symbol}@depth20,{self.symbol}@kline_1m"
        }
        await self.ws.send_str(json.dumps(payload))

    async def _heartbeat(self):
        """
        Sends Ping every 30s to keep connection alive.
        """
        while self.running and self.ws and not self.ws.closed:
            try:
                await self.ws.send_str("Pong") # Or proper Ping frame
                await asyncio.sleep(30)
            except:
                break

    async def _handle_message(self, data: str):
        """
        Parses JSON and routes to appropriate callback.
        """
        try:
            if data == "Ping": # Server Ping
                await self.ws.send_str("Pong")
                return

            msg = json.loads(data)

            # Identify Data Type
            # Example structure: {"dataType": "XAU-USDT@depth20", "data": {...}}
            data_type = msg.get("dataType", "")

            if "depth" in data_type:
                # Throttling
                now = time.time() * 1000
                if now - self.last_depth_ts > self.depth_throttle_ms:
                    self.last_depth_ts = now
                    # Process Depth
                    # Convert raw dict to lightweight structure if needed
                    # e.g., bids/asks lists
                    bids = pd.DataFrame(msg['data']['bids'], columns=['price', 'quantity'], dtype=float)
                    asks = pd.DataFrame(msg['data']['asks'], columns=['price', 'quantity'], dtype=float)

                    # Execute Callback (async/sync safe)
                    if asyncio.iscoroutinefunction(self.callback_depth):
                        await self.callback_depth(bids, asks)
                    else:
                        self.callback_depth(bids, asks)

            elif "kline" in data_type:
                # Process Kline
                kline = msg['data'] # {'c': close, 'v': volume, ...}
                # Convert to standard format
                # Assuming simple close price for GARCH
                close_price = float(kline['c'])

                if asyncio.iscoroutinefunction(self.callback_kline):
                    await self.callback_kline(close_price)
                else:
                    self.callback_kline(close_price)

        except Exception as e:
            logger.error(f"Message Parse Error: {e} | Data: {data[:100]}")

    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
