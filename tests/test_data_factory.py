import unittest
import shutil
import os
import pandas as pd
import numpy as np
import time
from src.data.data_factory import DataFactory

class TestDataFactory(unittest.TestCase):

    def setUp(self):
        self.test_dir = "tests/data_factory_test"
        self.factory = DataFactory(data_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_schema_hashing(self):
        # 1. Compute Hash for Feature Set A
        cols_a = ["open", "close", "rsi"]
        hash_a = self.factory._compute_schema_hash(cols_a)

        # 2. Compute Hash for Feature Set B (Changed)
        cols_b = ["open", "close", "rsi", "garch"]
        hash_b = self.factory._compute_schema_hash(cols_b)

        self.assertNotEqual(hash_a, hash_b)

        # Order shouldn't matter
        cols_a_scrambled = ["rsi", "open", "close"]
        # Note: logic in factory uses json.dumps(columns), so implementation should sort
        # Let's check implementation
        # Implementation: s = json.dumps(columns) -> Depends on input order
        # The caller (DataFactory.load_or_sync) sorts the columns.
        # But _compute_schema_hash just dumps.
        # Let's verify _compute_schema_hash behavior as is:
        hash_a_scrambled = self.factory._compute_schema_hash(cols_a_scrambled)
        self.assertNotEqual(hash_a, hash_a_scrambled) # Expect different because simple json dump

    def test_fetch_wrapper(self):
        # Mock fetch function
        def mock_fetch(start_time):
            # Return dummy pandas df
            df = pd.DataFrame({
                'open': [100], 'close': [101]
            }, index=[1000]) # Timestamp index
            return df

        polars_df = self.factory._fetch_data(mock_fetch, 1000)
        self.assertIn("timestamp", polars_df.columns)
        self.assertEqual(polars_df["timestamp"][0], 1000)

if __name__ == '__main__':
    unittest.main()
