import sys
import os
import pandas as pd
import polars as pl
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.darwin_engine import DarwinEngine
from src.core.advanced_backtester import AdvancedBacktester

def main():
    print("--- ARGUS v2.5: Executing Generation 0 Evolution ---")

    # 1. Setup Data (Synthetic for this run since we lack history)
    # We need a dummy parquet file for the backtester to "load",
    # even though our current backtester mock logic doesn't strictly read it for metrics calculation yet.
    data_dir = "data/time_machine"
    os.makedirs(data_dir, exist_ok=True)

    for symbol in ["BTC_USDT", "XAU_USDT"]:
        dummy_path = os.path.join(data_dir, f"{symbol}.parquet")
        if not os.path.exists(dummy_path):
            print(f"Generating synthetic data for {symbol}...")
            df = pl.DataFrame({
                "timestamp": np.arange(1000),
                "open": np.random.rand(1000) * 100,
                "high": np.random.rand(1000) * 100,
                "low": np.random.rand(1000) * 100,
                "close": np.random.rand(1000) * 100,
                "volume": np.random.rand(1000) * 1000
            })
            df.write_parquet(dummy_path)

    # 2. Initialize Darwin Engine
    # Pop Size 100 as requested
    engine = DarwinEngine(population_size=100)

    assets = ["BTC/USDT", "XAU/USDT"]
    backtester = AdvancedBacktester("data/time_machine/BTC_USDT.parquet") # Path is placeholder for mock run

    # 3. Evolution Loop
    for asset in assets:
        print(f"\n--- Evolving {asset} ---")
        engine.register_asset(asset)

        # Define evaluation wrapper
        # The backtester currently generates random metrics based on the genome to simulate "work"
        # Must be picklable (top-level) for multiprocessing
        pass

        print(f"Evaluating Population ({engine.pop_size} Genomes)...")
        # Direct call won't work with ProcessPoolExecutor for nested local functions.
        # We need to define eval_func at module level or use a class method if picklable.
        # For simplicity in this script, we can mock the evaluation loop serially or define a global helper.

        # Using serial evaluation for script to avoid pickling issues in one-off script
        for genome in engine.populations[asset]:
             metrics = backtester.run_purged_walk_forward(strategy_genome=genome)
             genome.metrics = metrics
             genome.fitness = engine.calculate_fitness(metrics)

        # 4. Reporting
        pop = engine.populations[asset]
        # Sort by fitness
        sorted_pop = sorted(pop, key=lambda x: x.fitness, reverse=True)
        top_3 = sorted_pop[:3]

        print(f"\n>> {asset} GENERATION 0 LEADERBOARD <<")
        print(f"{'Rank':<5} | {'ID':<15} | {'Fitness':<8} | {'Sharpe':<8} | {'CAGR':<8} | {'MaxDD':<8}")
        print("-" * 65)

        for i, genome in enumerate(top_3):
            m = genome.metrics
            print(f"{i+1:<5} | {genome.id:<15} | {genome.fitness:<8.2f} | {m.get('sharpe',0):<8.2f} | {m.get('cagr',0):<8.2%} | {m.get('max_drawdown',0):<8.2%}")

    # 5. Save Champions
    print("\nSaving Champions to data/champions.json...")
    engine.save_champions()
    print("Done.")

if __name__ == "__main__":
    main()
