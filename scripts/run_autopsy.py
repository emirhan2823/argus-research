import argparse
import sys
import os
import json
import pandas as pd
import polars as pl

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.data.exchange import ExchangeClient
from src.data.data_factory import DataFactory
from src.strategies.trend_following import TrendFollowingStrategy
from src.core.advanced_backtester import AdvancedBacktester
from src.core.reflector import Reflector, TradeRecord
from src.core.darwin_engine import Genome

def run_autopsy(symbol, genome_id):
    print(f"--- ARGUS v2.5: Running Autopsy on {symbol} / {genome_id} ---")

    # 1. Initialize Components
    exchange = ExchangeClient(mock=True)
    strategy = TrendFollowingStrategy(risk_manager=None) # No risk manager needed for indicator calc
    data_factory = DataFactory()

    # 2. Load Data
    print("Loading Data...")
    fetch_wrapper = lambda start_time: exchange.fetch_ohlcv(limit=1000, start_time=start_time)
    feature_wrapper = lambda df: strategy.calculate_indicators(df)

    # Force local if possible to ensure we analyze what we backtested, or sync if missing
    historical_data_lazy = data_factory.load_or_sync(symbol, fetch_wrapper, feature_wrapper)
    market_data = historical_data_lazy.collect()

    # 3. Re-Run Backtest to Find Max Loss Trade
    # We need the parquet path for Backtester
    parquet_path = data_factory.get_parquet_path(symbol)
    backtester = AdvancedBacktester(parquet_path)

    # Create a dummy genome if ID provided, or load from champions
    # For now, creating a random/default genome to simulate the process
    # In a real scenario, we'd load the specific genome from a DB/File
    genome = Genome.random({'ema_short': (10, 50), 'ema_long': (50, 200), 'rsi_period': (14, 14)})
    genome.id = genome_id

    print(f"Running Backtest for Genome {genome.id}...")
    # We need a backtest method that returns TRADES, not just metrics.
    # AdvancedBacktester._run_vectorized_strategy calculates returns but doesn't output TradeRecord objects yet.
    # We will invoke a new method `extract_trades` (to be implemented)
    trades = backtester.extract_trades(genome)

    if not trades:
        print("No trades found. Autopsy aborted.")
        return

    # 4. Identify Max Loss Trade
    loss_trades = [t for t in trades if t.pnl < 0]
    if not loss_trades:
        print("No losing trades found! Strategy is perfect (or buggy).")
        return

    worst_trade = min(loss_trades, key=lambda t: t.pnl)
    print(f"Max Loss Trade Identified: {worst_trade.id} (PnL: {worst_trade.pnl:.2f})")

    # 5. Run Reflector
    reflector = Reflector()
    print("Running Reflector Post-Mortem...")
    adj_vector = reflector.run_post_mortem(worst_trade, market_data)

    if adj_vector:
        print(f"Diagnosis: {adj_vector.reason}")
        print(f"Suggested Adjustments: {adj_vector.suggested_changes}")

        # 6. Save Outputs
        report_path = "specs/v2.5/16_BTC_FORENSIC_REPORT.md"
        blueprint_path = "data/evolution_blueprint.json"

        # Markdown Report
        with open(report_path, "w") as f:
            f.write(f"# ARGUS Forensic Report: {symbol}\n\n")
            f.write(f"**Genome ID:** {genome_id}\n")
            f.write(f"**Worst Trade:** {worst_trade}\n\n")
            f.write(f"## Diagnosis\n")
            f.write(f"**Reason:** {adj_vector.reason}\n")
            f.write(f"**Adjustments:** `{json.dumps(adj_vector.suggested_changes)}`\n")

        # JSON Blueprint
        blueprint = {
            "symbol": symbol,
            "failed_genome_id": genome_id,
            "adjustment_vector": adj_vector.suggested_changes,
            "timestamp": int(pd.Timestamp.now().timestamp())
        }
        with open(blueprint_path, "w") as f:
            json.dump(blueprint, f, indent=4)

        print(f"Report saved to {report_path}")
        print(f"Blueprint saved to {blueprint_path}")
    else:
        print("Reflector could not determine a cause or data was insufficient.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, required=True, help="Trading Symbol (e.g. BTC/USDT)")
    parser.add_argument("--genome", type=str, required=True, help="Genome ID to analyze")
    args = parser.parse_args()

    run_autopsy(args.symbol, args.genome)
