import unittest
import polars as pl
import numpy as np
from src.core.integrity_manager import IntegrityManager

class TestIntegrityManager(unittest.TestCase):

    def setUp(self):
        self.manager = IntegrityManager()

    def test_outlier_detection(self):
        # Create stable series (mean=100, std~0)
        prices = [100.0] * 99
        # Inject Outlier (1000.0) at index 99 -> Huge Z-Score
        prices.append(1000.0)

        df = pl.DataFrame({"close": prices})

        # Detect
        # Window=100 covers whole series
        flagged = self.manager.detect_and_flag_outliers(df, z_threshold=4.0, window=100)

        # Check if last row is flagged
        last_row = flagged.tail(1)
        self.assertTrue(last_row["is_outlier"][0], "Outlier not flagged!")

        # Check normal row
        first_row = flagged.head(1)
        self.assertFalse(first_row["is_outlier"][0], "Normal data flagged falsely!")

    def test_gap_analysis(self):
        # Create timestamps with a gap
        # 0, 60000, 120000, (GAP -> 300000), 360000
        timestamps = [0, 60000, 120000, 300000, 360000]
        df = pl.DataFrame({"timestamp": timestamps})

        report = self.manager.analyze_gaps(df, expected_interval_ms=60000)

        # Should detect 1 gap
        self.assertEqual(len(report), 1)

        # Gap starts at 300000 (current timestamp) relative to previous (120000)
        # Delta = 180000 (3 mins)
        # Missing candles = (180000 / 60000) - 1 = 2

        gap = report[0]
        self.assertEqual(gap["gap_duration_ms"], 180000)
        self.assertEqual(gap["missing_candles"], 2)

    def test_cross_check(self):
        # Primary (BingX)
        primary = pl.DataFrame({
            "timestamp": [1000, 2000],
            "close": [100.0, 100.0]
        })

        # Secondary (Binance) -> Row 2 has 1% deviation (101.0 vs 100.0) > 0.3%
        secondary = pl.DataFrame({
            "timestamp": [1000, 2000],
            "close": [100.0, 101.0]
        })

        report = self.manager.check_cross_exchange_integrity(primary, secondary, tolerance_pct=0.3)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["anomaly_count"], 1)
        self.assertAlmostEqual(report["max_deviation"], 0.990099, places=4)

if __name__ == '__main__':
    unittest.main()
