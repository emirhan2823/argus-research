import time
import sys
import os
import pandas as pd
from datetime import datetime

# Ensure project root is in path

import asyncio
from src.data.exchange import ExchangeClient
from src.core.risk_manager import RiskManager
from src.core.microstructure import MicrostructureEngine
from src.strategies.trend_following import TrendFollowingStrategy
from src.connectors.bingx_websocket import BingXWebSocket
from src.data.data_factory import DataFactory
from src.core.darwin_engine import DarwinEngine
from src.core.reflector import Reflector
from config.settings import SYMBOL, TIMEFRAME
import argparse

async def run_bot(evolve_mode=False):
    print(f"--- Starting Hedge Fund Bot (Async) ---")
    print(f"Symbol: {SYMBOL}, Timeframe: {TIMEFRAME}")

    # Initialize Components
    exchange = ExchangeClient(mock=True)
    risk_manager = RiskManager()
    microstructure_engine = MicrostructureEngine()
    strategy = TrendFollowingStrategy(risk_manager)
    data_factory = DataFactory()

    # Initialize Darwin Engine
    darwin = DarwinEngine()
    darwin.register_asset(SYMBOL)
    darwin.load_champions()

    # Evolution Mode
    if evolve_mode:
        print(">>> EVOLUTION MODE ACTIVATED <<<")

        # 1. Reflector Analysis (Pre-Evolution)
        # Check BTC Champion for failures
        reflector = Reflector()
        adjustment_vector = None

        # Mocking a past trade for BTC Champion to trigger Reflector
        # Ideally fetch from Trade History DB
        print("Running Reflector on Champion (gen_632918)...")
        # adjustment_vector = reflector.run_post_mortem(...)
        # Simulating adjustment for now as requested
        adjustment_vector = {'sl_atr_mult': 0.2}
        print(f"Adjustment Vector Generated: {adjustment_vector}")

        # 2. Trigger Evolution
        print(f"Starting Generation 1 Evolution for {SYMBOL}...")
        # Note: DataFactory should ensure local data is ready.
        # Ensure dummy data exists for "XAU/USDT" (mapped to XAU_USDT.parquet)
        fetch_wrapper = lambda start_time: exchange.fetch_ohlcv(limit=1000, start_time=start_time)
        feature_wrapper = lambda df: strategy.calculate_indicators(df)
        data_factory.load_or_sync(SYMBOL, fetch_wrapper, feature_wrapper)

        # Pass adjustment vector to evolve (needs update in DarwinEngine)
        darwin.evolve(specific_symbol=SYMBOL, adjustment_vector=adjustment_vector)

        print("Evolution Complete.")
        return

    # 0. Data Factory Initialization (Sync/Heal Data)
    print("Initializing Data Factory...")
    fetch_wrapper = lambda start_time: exchange.fetch_ohlcv(limit=1000, start_time=start_time)
    feature_wrapper = lambda df: strategy.calculate_indicators(df)

    historical_data_lazy = data_factory.load_or_sync(SYMBOL, fetch_wrapper, feature_wrapper)
    print("Data Factory synced.")

    # --- WebSocket Setup ---
    # Define Callbacks
    async def on_depth_update(bids, asks):
        # Update OBI (Order Book Imbalance)
        # This function must be lightweight or offloaded
        pass
        # For full implementation, we would call microstructure_engine.update_obi(bids, asks)

    async def on_kline_update(close_price):
        # Trigger GARCH Update
        # Ideally, accumulate returns and update periodically
        pass

    ws_client = BingXWebSocket(
        symbol=SYMBOL,
        callback_depth=on_depth_update,
        callback_kline=on_kline_update
    )

    # Start WS in background
    asyncio.create_task(ws_client.connect())

    print("Components initialized. Starting loop...")

    try:
        while True:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{current_time}] Checking market...")

            # 0. Sync Risk Manager
            balance = exchange.get_balance()
            risk_manager.update_balance(balance)

            # 1. Check Open Positions
            positions = exchange.fetch_positions()
            if positions:
                print(f"Open Position Detected: {positions}")
                # Logic to manage exit could go here (e.g., Trailing Stop)
                # For now, we skip new entries if a position is open
                print("Skipping entry logic due to open position.")
                await asyncio.sleep(60)
                continue

            # 2. Fetch Data (REST Fallback / Historical)
            data = exchange.fetch_ohlcv(limit=300)
            if data.empty:
                print("No data received. Retrying in 60s...")
                await asyncio.sleep(60)
                continue

            # 2.1 Update Microstructure (GARCH)
            # Calculate returns for GARCH
            if len(data) > 30:
                returns = data['close'].pct_change().dropna()
                microstructure_engine.update_volatility_async(returns)

            # 3. Update Indicators
            data = strategy.calculate_indicators(data)

            # 4. Generate Signal
            signal, metadata = strategy.generate_signal(data)

            if signal:
                print(f"Signal Detected: {signal.upper()}")
                entry_price = metadata['entry_price']
                stop_loss = metadata['stop_loss']

                # 5. Risk Check
                if risk_manager.check_trade_allowed():
                    base_size = risk_manager.calculate_position_size(
                        entry_price, stop_loss, balance
                    )

                    # 5.1 Apply Volatility Guard
                    safe_size = microstructure_engine.volatility_guard(base_size, microstructure_engine.latest_vol_forecast)

                    if safe_size < base_size:
                        print(f"Volatility Guard Active: Reduced size from {base_size:.4f} to {safe_size:.4f}")

                    if safe_size > 0:
                        print(f"Executing {signal.upper()} | Size: {safe_size:.4f} | Entry: {entry_price} | SL: {stop_loss}")

                        # 6. Execute Order (Market Order with SL/TP)
                        # Note: For market orders, price is None.
                        # Some exchanges require SL/TP to be separate orders, but CCXT often unifies them.
                        order = exchange.create_order(
                            signal,
                            safe_size,
                            type='market',
                            stop_loss=metadata['stop_loss'],
                            take_profit=metadata['take_profit']
                        )

                        if order:
                            print(f"Order Placed: {order['id']}")
                            # In a real system, we would track this position in a database
                    else:
                        print("Position size is 0. Risk too high or insufficient balance.")
                else:
                    print("Trade blocked by Risk Manager (Daily Loss or Drawdown limit).")
            else:
                print("No signal.")

            # Sleep before next cycle (e.g., 1 minute)
            print("Sleeping for 60 seconds...")
            await asyncio.sleep(60)

    except asyncio.CancelledError:
        print("\nBot stopped by user.")
        await ws_client.stop()
    except Exception as e:
        print(f"\nCritical Error: {e}")
        await ws_client.stop()

if __name__ == "__main__":
    sys.path.append(os.getcwd()) # Path Persistence Fix

    parser = argparse.ArgumentParser()
    parser.add_argument("--evolve", action="store_true", help="Run Evolution Mode instead of Live Trading")
    args = parser.parse_args()

    try:
        asyncio.run(run_bot(evolve_mode=args.evolve))
    except KeyboardInterrupt:
        pass
