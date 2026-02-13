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

    def run_purged_walk_forward(self, strategy_func, n_folds=5, embargo_pct=0.01):
        """
        Runs backtest using PurgedKFold logic.
        """
        # Load timestamps (eagerly for splitting)
        # Assuming sorted
        timestamps = self.data_lazy.select("timestamp").collect().to_series().to_numpy()

        indices = np.arange(len(timestamps))
        fold_size = len(timestamps) // n_folds
        embargo_size = int(len(timestamps) * embargo_pct)

        results = []

        for i in range(n_folds):
            test_start = i * fold_size
            test_end = (i + 1) * fold_size

            # Train indices: All indices EXCEPT [test_start - purge : test_end + embargo]
            # Simplifying purge to 0 for this example, focusing on embargo
            train_mask = (indices < test_start) | (indices > test_end + embargo_size)

            train_indices = indices[train_mask]
            test_indices = indices[test_start:test_end]

            print(f"Fold {i+1}/{n_folds}: Train Size: {len(train_indices)}, Test Size: {len(test_indices)}")

            # Here we would filter the LazyFrame based on these indices and run the strategy
            # For this skeleton, we just log the split.
            results.append({"fold": i, "train_len": len(train_indices), "test_len": len(test_indices)})

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
