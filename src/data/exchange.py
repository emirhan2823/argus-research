import ccxt
import pandas as pd
import time
import os
import sys

# Ensure we can import from config

from config.settings import BINGX_API_KEY, BINGX_SECRET_KEY, SYMBOL, TIMEFRAME

class ExchangeClient:
    """
    Wrapper for CCXT exchange interface.
    Handles connection, data fetching, and order execution.
    """

    def __init__(self, exchange_id='bingx', mock=False):
        self.mock = mock
        self.symbol = SYMBOL
        self.timeframe = TIMEFRAME

        if not self.mock:
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class({
                'apiKey': BINGX_API_KEY,
                'secret': BINGX_SECRET_KEY,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future', # or 'swap' depending on exchange
                }
            })
        else:
            self.exchange = None
            print("Exchange Client initialized in MOCK mode.")

    def fetch_ohlcv(self, limit=1000, start_time: int = None):
        """
        Fetches historical OHLCV data.
        Returns a DataFrame with columns: open, high, low, close, volume.
        start_time: Milliseconds UTC
        """
        if self.mock:
            # Generate dummy data for testing purposes if needed, or return empty DF
            print("Mock fetch_ohlcv called.")
            return pd.DataFrame()

        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit, since=start_time)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"Error fetching OHLCV: {e}")
            return pd.DataFrame()

    def get_balance(self):
        """
        Fetches account balance (USDT).
        """
        if self.mock:
            return 10000.0

        try:
            balance = self.exchange.fetch_balance()
            return balance['total']['USDT'] # Adjust key based on specific exchange response
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0

    def create_order(self, side, amount, price=None, type='limit', stop_loss=None, take_profit=None):
        """
        Places an order.
        side: 'buy' or 'sell'
        amount: Quantity
        price: Price (for limit orders)
        type: 'limit' or 'market'
        stop_loss: Trigger price for SL
        take_profit: Trigger price for TP
        """
        params = {}
        if stop_loss:
            params['stopLoss'] = stop_loss
        if take_profit:
            params['takeProfit'] = take_profit

        if self.mock:
            print(f"MOCK ORDER: {side} {amount} @ {price} ({type}) | SL: {stop_loss} | TP: {take_profit}")
            return {'id': 'mock_order_id', 'status': 'closed'}

        try:
            order = self.exchange.create_order(self.symbol, type, side, amount, price, params=params)
            print(f"Order placed: {order['id']}")
            return order
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def fetch_positions(self):
        """
        Fetches open positions.
        Returns a list of positions.
        """
        if self.mock:
            # Return empty list to simulate no positions, or a mock position if testing exits
            return []

        try:
            positions = self.exchange.fetch_positions([self.symbol])
            # Filter for active positions (size > 0)
            active_positions = [p for p in positions if float(p['contracts']) > 0]
            return active_positions
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def fetch_closed_trades(self, since: int = None):
        """
        Fetches closed trades (for Reflector analysis).
        since: Timestamp in ms
        """
        if self.mock:
            return []

        try:
            # fetch_my_trades or fetch_closed_orders depending on exchange support
            trades = self.exchange.fetch_my_trades(self.symbol, since=since)
            return trades
        except Exception as e:
            print(f"Error fetching closed trades: {e}")
            return []
