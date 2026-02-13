import unittest
import polars as pl
from src.core.advanced_backtester import DataLock

class TestDataLock(unittest.TestCase):

    def setUp(self):
        # Create a dummy dataframe spanning time 0 to 100
        self.df = pl.DataFrame({
            "timestamp": range(101),
            "price": range(101)
        })
        self.lock = DataLock(self.df)

    def test_future_leakage(self):
        # Target time t=50
        t = 50

        # Get filtered data
        # Note: DataLock returns a LazyFrame usually, or DataFrame.
        # Checking implementation:
        # class DataLock:
        #    def __init__(self, df: pl.DataFrame): self.raw = df
        #    def get_features_at(self, timestamp): return self.raw.filter(pl.col("timestamp") <= timestamp)
        # It returns a DataFrame (since input was DataFrame) or LazyFrame (if input was Lazy).
        # In this test input is DataFrame so output is DataFrame.

        result = self.lock.get_features_at(t)

        # Check Max Timestamp
        max_ts = result["timestamp"].max()

        self.assertLessEqual(max_ts, t, "Future data leaked! Max TS > Target TS")

        # Check Count
        # Should have 51 rows (0 to 50)
        self.assertEqual(len(result), 51)

        # Explicit check for t=51
        future_rows = result.filter(pl.col("timestamp") > t)
        self.assertTrue(future_rows.is_empty(), "Explicit future row found!")

if __name__ == '__main__':
    unittest.main()
