import time
import sys
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is in path
load_dotenv()

import asyncio
from src.data.exchange import ExchangeClient
from src.core.risk_manager import RiskManager
from src.core.microstructure import MicrostructureEngine
from src.strategies.trend_following import TrendFollowingStrategy
from src.connectors.bingx_websocket import BingXWebSocket
from src.data.data_factory import DataFactory
from src.core.darwin_engine import DarwinEngine
from src.core.reflector import Reflector
from src.core.advanced_backtester import AdvancedBacktester
from config.settings import SYMBOL, TIMEFRAME
import argparse
from src.core.reflector import TradeRecord # Needed for casting
from src.core.task_runner import run_backtest_task

def run_sync_research_cycle(data_factory, darwin, exchange, strategy):
    """
    Synchronous wrapper for CPU/IO heavy research tasks.
    Runs in Executor to avoid blocking the Event Loop.
    """
    print("\n[Research] Starting Continuous Evolution Cycle...")

    # 1. Sync Data
    print("[Research] Syncing Data...")
    fetch_wrapper = lambda start_time: exchange.fetch_ohlcv(limit=1000, start_time=start_time)
    feature_wrapper = lambda df: strategy.calculate_indicators(df)
    historical_data_lazy = data_factory.load_or_sync(SYMBOL, fetch_wrapper, feature_wrapper)

    # 2. Reflector Analysis on Closed Trades
    print("[Research] Fetching closed trades...")
    since_ts = int(time.time() * 1000) - (24 * 3600 * 1000)
    trades = exchange.fetch_closed_trades(since=since_ts)

    adjustment_vector = {}
    reflector = Reflector()

    if trades:
        print(f"[Research] Analyzing {len(trades)} recent trades...")
        last_trade_ccxt = trades[-1]
        trade_record = TradeRecord(
            id=str(last_trade_ccxt.get('id')),
            symbol=last_trade_ccxt.get('symbol'),
            direction=last_trade_ccxt.get('side').upper(),
            entry_time=last_trade_ccxt.get('timestamp'),
            exit_time=last_trade_ccxt.get('timestamp'),
            entry_price=float(last_trade_ccxt.get('price')),
            exit_price=float(last_trade_ccxt.get('price')),
            stop_loss=0.0,
            take_profit=0.0,
            pnl=0.0
        )

        print("[Research] Loading data for forensic analysis...")
        market_data = historical_data_lazy.collect()
        adj = reflector.run_post_mortem(trade_record, market_data)
        if adj:
            print(f"[Research] Reflector suggested: {adj.suggested_changes}")
            adjustment_vector.update(adj.suggested_changes)

    # 3. Evolution
    print("[Research] Evaluating current population with updated data...")
    darwin.evaluate_population(run_backtest_task, specific_symbol=SYMBOL)

    print("[Research] Evolving Strategy...")
    darwin.evolve(specific_symbol=SYMBOL, adjustment_vector=adjustment_vector)
    print("[Research] Cycle Complete.")

async def run_research_loop(data_factory, darwin, exchange, strategy, interval_hours=4):
    """
    Background loop for autonomous research and evolution.
    """
    loop = asyncio.get_running_loop()
    while True:
        print(f"\n[Research] Sleeping for {interval_hours} hours...")
        await asyncio.sleep(interval_hours * 3600)

        # Offload heavy sync/cpu work to thread pool
        await loop.run_in_executor(None, run_sync_research_cycle, data_factory, darwin, exchange, strategy)

async def run_bot(evolve_mode=False, live_mode=False):
    # Load Environment Variables
    env_mock_mode = os.getenv("USE_MOCK_MODE", "True").lower() == "true"

    # Priority: Command Line Flag > Env Var > Default True
    # If --live is passed, live_mode is True, so mock should be False.
    # If --live is NOT passed, check ENV.

    is_live = live_mode or (not env_mock_mode)
    use_mock = not is_live

    print(f"--- Starting Hedge Fund Bot (Async) ---")
    print(f"Symbol: {SYMBOL}, Timeframe: {TIMEFRAME}")
    print(f"Mode: {'LIVE' if is_live else 'MOCK'}")

    if is_live:
        api_key = os.getenv("BINGX_API_KEY", "")
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "********"
        print(f"[Connection] Using Live API Key: {masked_key}")

    # Initialize Components
    exchange = ExchangeClient(mock=use_mock)
    risk_manager = RiskManager()
    microstructure_engine = MicrostructureEngine()
    strategy = TrendFollowingStrategy(risk_manager)
    data_factory = DataFactory()

    # Initialize Darwin Engine
    darwin = DarwinEngine()
    darwin.register_asset(SYMBOL)
    darwin.load_champions()

    # Evolution Mode (One-off)
    if evolve_mode:
        print(">>> EVOLUTION MODE ACTIVATED (One-Off) <<<")
        # In Evolution Mode, enforce local data
        fetch_wrapper = lambda start_time: pd.DataFrame()
        feature_wrapper = lambda df: strategy.calculate_indicators(df)
        data_factory.load_or_sync(SYMBOL, fetch_wrapper, feature_wrapper, enforce_local=True)
        darwin.evolve(specific_symbol=SYMBOL)
        return

    # --- Live/Mock Trading Loop ---

    # 0. Data Factory Initialization
    print("Initializing Data Factory...")
    fetch_wrapper = lambda start_time: exchange.fetch_ohlcv(limit=1000, start_time=start_time)
    feature_wrapper = lambda df: strategy.calculate_indicators(df)
    data_factory.load_or_sync(SYMBOL, fetch_wrapper, feature_wrapper)
    print("Data Factory synced.")

    # --- WebSocket Setup ---
    async def on_depth_update(bids, asks):
        pass
    async def on_kline_update(close_price):
        pass

    ws_client = BingXWebSocket(
        symbol=SYMBOL,
        callback_depth=on_depth_update,
        callback_kline=on_kline_update
    )

    # Start Tasks
    tasks = []

    # 1. WebSocket
    tasks.append(asyncio.create_task(ws_client.connect()))

    # 2. Research Loop (4h)
    tasks.append(asyncio.create_task(run_research_loop(data_factory, darwin, exchange, strategy)))

    # 3. Main Trading Loop
    async def trading_loop():
        print("Components initialized. Starting trading loop...")
        try:
            while True:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # print(f"\n[{current_time}] Checking market...") # Reduced verbosity

                # 0. Sync Risk Manager
                balance = exchange.get_balance()
                risk_manager.update_balance(balance)

                # 1. Check Open Positions
                positions = exchange.fetch_positions()
                if positions:
                    # print(f"Open Position: {positions}")
                    await asyncio.sleep(60)
                    continue

                # 2. Fetch Data
                data = exchange.fetch_ohlcv(limit=300)
                if data.empty:
                    print("No data received. Retrying...")
                    await asyncio.sleep(60)
                    continue

                # 2.1 Update Microstructure
                if len(data) > 30:
                    returns = data['close'].pct_change().dropna()
                    microstructure_engine.update_volatility_async(returns)

                # 3. Update Indicators
                data = strategy.calculate_indicators(data)

                # 4. Generate Signal
                signal, metadata = strategy.generate_signal(data)

                if signal:
                    print(f"[{current_time}] Signal Detected: {signal.upper()}")
                    entry_price = metadata['entry_price']
                    stop_loss = metadata['stop_loss']

                    if risk_manager.check_trade_allowed():
                        base_size = risk_manager.calculate_position_size(entry_price, stop_loss, balance)
                        # Use method from class, not standalone function attribute
                        safe_size = microstructure_engine.get_safe_leverage(base_size)

                        if safe_size > 0:
                            print(f"Executing {signal.upper()} | Size: {safe_size:.4f}")
                            exchange.create_order(
                                signal, safe_size, type='market',
                                stop_loss=metadata['stop_loss'], take_profit=metadata['take_profit']
                            )

                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    tasks.append(asyncio.create_task(trading_loop()))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"\nCritical Error: {e}")
    finally:
        await ws_client.stop()

if __name__ == "__main__":
    sys.path.append(os.getcwd()) # Path Persistence Fix

    parser = argparse.ArgumentParser()
    parser.add_argument("--evolve", action="store_true", help="Run Evolution Mode (One-Off)")
    parser.add_argument("--live", action="store_true", help="Run in Live Mode (Real Money)")
    args = parser.parse_args()

    try:
        asyncio.run(run_bot(evolve_mode=args.evolve, live_mode=args.live))
    except KeyboardInterrupt:
        pass
