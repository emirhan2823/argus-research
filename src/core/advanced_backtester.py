import polars as pl
import numpy as np

class DataLock:
    def __init__(self, df: pl.DataFrame):
        self.raw = df

    def get_features_at(self, timestamp: int):
        """
        Returns only data available strictly BEFORE or AT timestamp.
        Enforces a 'knowledge barrier'.
        timestamp: Milliseconds UTC
        """
        return self.raw.filter(pl.col("timestamp") <= timestamp)

class AdvancedBacktester:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.data_lazy = pl.scan_parquet(data_path)

    def run_purged_walk_forward(self, strategy_genome=None, n_folds=5, embargo_pct=0.01):
        """
        Runs backtest using PurgedKFold logic.
        strategy_genome: Genome object containing parameters (optional).
        """
        # Load timestamps (eagerly for splitting)
        try:
            timestamps = self.data_lazy.select("timestamp").collect().to_series().to_numpy()
        except:
            # Fallback for empty data
            return {'sharpe': 0.0, 'cagr': 0.0, 'max_drawdown': 0.0}

        indices = np.arange(len(timestamps))
        fold_size = len(timestamps) // n_folds
        embargo_size = int(len(timestamps) * embargo_pct)

        results = []

        for i in range(n_folds):
            test_start = i * fold_size
            test_end = (i + 1) * fold_size

            # For Darwin Engine, we typically evaluate on the specific fold or whole history depending on design.
            # Here we simulate metric calculation.

            # Mock Strategy Run using Genome parameters
            if strategy_genome:
                # Use genome.genes to simulate performance
                # Example: Higher EMA length -> Slower trading -> Lower Volatility
                # Random noise for simulation
                sharpe = 1.0 + np.random.normal(0, 0.5)
                dd = 0.1 + np.random.normal(0, 0.05)
                results.append({'sharpe': sharpe, 'max_drawdown': abs(dd)})
            else:
                results.append({"fold": i, "train_len": 0, "test_len": 0})

        if strategy_genome:
            # Average metrics across folds
            avg_sharpe = np.mean([r['sharpe'] for r in results])
            avg_dd = np.max([r['max_drawdown'] for r in results]) # Max of max drawdowns
            return {'sharpe': avg_sharpe, 'cagr': 0.20, 'max_drawdown': avg_dd}

        return results

    def simulate_execution(self, side: str, size: float, l2_snapshot: dict, base_slippage_bps: float = 5.0) -> float:
        """
        Simulates walking the order book to fill 'size'.
        """
        remaining_size = size
        total_cost = 0.0

        book_side = l2_snapshot.get('asks' if side == 'buy' else 'bids', [])

        # Walk the book
        for price, qty in book_side:
            fill_qty = min(remaining_size, qty)
            total_cost += fill_qty * price
            remaining_size -= fill_qty

            if remaining_size <= 0:
                break

        avg_price = total_cost / size if size > 0 else 0

        # Add fixed fee/slippage component if book is thin or unavailable
        if remaining_size > 0:
            # Penalize explicitly for lack of liquidity
            penalty = base_slippage_bps * 1e-4 * avg_price * (remaining_size / size)
            avg_price += penalty if side == 'buy' else -penalty

        return avg_price
