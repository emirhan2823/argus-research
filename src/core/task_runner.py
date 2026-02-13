from src.core.advanced_backtester import AdvancedBacktester
from src.data.data_factory import DataFactory
from config.settings import SYMBOL

# Top-level function for multiprocessing picklability
def run_backtest_task(genome, symbol):
    """
    Worker function for parallel backtesting.
    Instantiates its own backtester to avoid pickling large objects.
    """
    try:
        # Resolve path - DataFactory logic duplication or helper?
        # Ideally pass path as argument, but evaluate_population signature is fixed (genome, symbol)
        # We can standardize path based on symbol
        factory = DataFactory()
        parquet_path = factory.get_parquet_path(symbol)

        backtester = AdvancedBacktester(parquet_path)
        metrics = backtester.run_purged_walk_forward(strategy_genome=genome)
        return metrics
    except Exception as e:
        print(f"Task Error for {symbol}: {e}")
        return {'sharpe': 0.0, 'cagr': 0.0, 'max_drawdown': 1.0}
