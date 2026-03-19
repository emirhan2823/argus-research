import unittest
import os
import shutil
from argus_py.data.loader import DataLoader, Bar

class TestRealBTCPipeline(unittest.TestCase):
    TEST_DIR = "test_data_strict"
    
    def setUp(self):
        os.makedirs(self.TEST_DIR, exist_ok=True)
        # Create BTCUSDT.csv
        with open(os.path.join(self.TEST_DIR, "BTCUSDT.csv"), 'w') as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("1704067200000,42000,42100,41900,42050,1.0\n")
            
        # Create BTCUSDT_month.csv (Friend)
        with open(os.path.join(self.TEST_DIR, "BTCUSDT_month.csv"), 'w') as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("1704067260000,42050,42150,42000,42100,1.0\n")

    def tearDown(self):
        shutil.rmtree(self.TEST_DIR)

    def test_strict_loader_no_friends(self):
        """Test that strict loader only loads the exact file if strict_symbol=True"""
        # Strict Load
        market = DataLoader.load_from_dir(self.TEST_DIR, symbol="BTCUSDT", strict_symbol=True)
        # Should only have 1 bar (from BTCUSDT.csv), ignoring "friend"
        # Wait, my logic prefers exact match. 
        # "BTCUSDT.csv" is exact. "BTCUSDT_month.csv" is friend.
        # My implementation: if exact match exists, filter to [exact_match].
        # So len should be 1.
        
        self.assertEqual(len(market._all_bars), 1, "Strict loader should ignore friend file if exact match exists")
        self.assertEqual(market._all_bars[0].close, 42050.0)

    def test_strict_loader_fail_if_missing(self):
        """Test that strict loader raises error if symbol missing"""
        with self.assertRaises(FileNotFoundError):
            DataLoader.load_from_dir(self.TEST_DIR, symbol="ETHUSDT", strict_symbol=True)

if __name__ == '__main__':
    unittest.main()
