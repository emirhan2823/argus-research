import unittest
import os
import shutil
import csv
from argus_py.runner.cli import run
class MockArgs:
    def __init__(self, data_dir, symbol="BTCUSDT", start_balance=1000.0, mode="paper"):
        self.data_dir = data_dir
        self.symbol = symbol
        self.start_balance = start_balance
        self.mode = mode

class TestReportingFix(unittest.TestCase):
    def setUp(self):
        self.data_dir = "argus_py/data/"
        # Clean runs dir
        if os.path.exists("runs_test"):
            shutil.rmtree("runs_test")
            
    def test_metrics_integrity(self):
        # 1. Run Backtest
        args = MockArgs(self.data_dir)
        
        # Monkey patch reporter to use known dir or inspect CLI return?
        # CLI run returns nothing. Reporter decides dir timestamp.
        # We'll check the latest dir in 'runs'.
        
        run(args)
        
        # 2. Find latest run
        all_runs = sorted([os.path.join("runs", d) for d in os.listdir("runs") if os.path.isdir(os.path.join("runs", d))])
        latest_run = all_runs[-1]
        print(f"Checking run: {latest_run}")
        
        # 3. Check Metrics
        metrics_path = os.path.join(latest_run, "metrics.csv")
        self.assertTrue(os.path.exists(metrics_path))
        
        rows = []
        with open(metrics_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, ["Bar", "Timestamp", "Equity", "Balance", "UnrealizedPnL", "PositionQty"])
            for row in reader:
                rows.append(row)
                
        # Assertions
        self.assertGreater(len(rows), 10, "Should have more than 10 bars logged")
        
        first_row = rows[0]
        first_equity = float(first_row[2])
        self.assertAlmostEqual(first_equity, 1000.0, delta=0.01, msg="Initial equity should be start_balance")
        
        # Verify valid non-zero equity throughout (unless blown up)
        for r in rows:
            eq = float(r[2])
            self.assertGreater(eq, 0, "Equity should be positive")

if __name__ == "__main__":
    unittest.main()
