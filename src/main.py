import time
import sys
import os
import pandas as pd
from datetime import datetime

# Ensure project root is in path

from src.data.exchange import ExchangeClient
from src.core.risk_manager import RiskManager
from src.core.microstructure import MicrostructureEngine
from src.strategies.trend_following import TrendFollowingStrategy
from config.settings import SYMBOL, TIMEFRAME

def main():
    print(f"--- Starting Hedge Fund Bot ---")
    print(f"Symbol: {SYMBOL}, Timeframe: {TIMEFRAME}")

    # Initialize Components
    # Set mock=True for safety during initial run. User can change this later.
    exchange = ExchangeClient(mock=True)
    risk_manager = RiskManager()
    microstructure_engine = MicrostructureEngine()
    strategy = TrendFollowingStrategy(risk_manager)

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
                time.sleep(60)
                continue

            # 2. Fetch Data
            data = exchange.fetch_ohlcv(limit=300)
            if data.empty:
                print("No data received. Retrying in 60s...")
                time.sleep(60)
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
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"\nCritical Error: {e}")

if __name__ == "__main__":
    main()
