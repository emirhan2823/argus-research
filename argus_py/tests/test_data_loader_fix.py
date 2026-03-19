
import unittest
import os
import shutil
import tempfile
from argus_py.data.loader import DataLoader

class TestDataLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def create_dummy_csv(self, filename):
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w') as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("1700000000,100,110,90,105,1000\n")
        return path

    def test_exact_match(self):
        self.create_dummy_csv("BTCUSDT.csv")
        market = DataLoader.load_from_dir(self.test_dir, symbol="BTCUSDT")
        self.assertEqual(market.symbol_resolved, "BTCUSDT")
        self.assertEqual(len(market._all_bars), 1)

    def test_fallback_single_file(self):
        # Only SAMPLE.csv exists, requesting BTCUSDT
        self.create_dummy_csv("SAMPLE.csv")
        market = DataLoader.load_from_dir(self.test_dir, symbol="BTCUSDT")
        # Should fallback to SAMPLE
        self.assertEqual(market.symbol_resolved, "SAMPLE") 
        self.assertEqual(os.path.basename(market.source_files[0]), "SAMPLE.csv")

    def test_fail_multiple_files_no_match(self):
        # Two files exist, neither matches
        self.create_dummy_csv("SAMPLE1.csv")
        self.create_dummy_csv("SAMPLE2.csv")
        
        with self.assertRaises(FileNotFoundError):
            DataLoader.load_from_dir(self.test_dir, symbol="BTCUSDT")

    def test_ms_timestamp_normalization(self):
        path = os.path.join(self.test_dir, "test.csv")
        with open(path, 'w') as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("1700000000000,100,110,90,105,1000\n") # ms timestamp
            
        market = DataLoader.load_from_dir(self.test_dir)
        market.set_time(0)
        self.assertEqual(market.latest_bar.timestamp, 1700000000.0)

if __name__ == '__main__':
    unittest.main()
