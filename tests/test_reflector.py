import unittest
import numpy as np
import polars as pl
from src.core.reflector import Reflector, TradeRecord

class TestReflector(unittest.TestCase):

    def setUp(self):
        self.reflector = Reflector()

    def test_noise_classification(self):
        # Scenario: LONG Trade. Entry 100, SL 95 (Dist 5), TP 110.
        # Market drops to 94 (Hit SL), then rallies to 115.
        # This is a classic "Stop Hunt" / Noise failure.

        trade = TradeRecord(
            id="t1", symbol="TEST", direction="LONG",
            entry_time=100, exit_time=200,
            entry_price=100.0, exit_price=94.0,
            stop_loss=95.0, take_profit=110.0,
            pnl=-6.0
        )

        # Create Data
        # Drop to 94, then rally
        prices = [100, 98, 96, 94, 96, 100, 105, 112]
        df = pl.DataFrame({
            "timestamp": range(100, 100 + len(prices)),
            "high": prices,
            "low": prices,
            "close": prices
        })

        adj = self.reflector.run_post_mortem(trade, df)

        self.assertIsNotNone(adj)
        self.assertEqual(adj.reason, "NOISE")
        self.assertEqual(adj.suggested_changes["sl_atr_mult"], 0.2)

    def test_regime_shift_classification(self):
        # Scenario: Market crashes way below even 1.5x SL.
        # Entry 100, SL 95. Market goes to 80.

        trade = TradeRecord(
            id="t2", symbol="TEST", direction="LONG",
            entry_time=100, exit_time=200,
            entry_price=100.0, exit_price=95.0,
            stop_loss=95.0, take_profit=110.0,
            pnl=-5.0
        )

        prices = [100, 90, 80, 70] # Crash
        df = pl.DataFrame({
            "timestamp": range(100, 100 + len(prices)),
            "high": prices,
            "low": prices,
            "close": prices
        })

        adj = self.reflector.run_post_mortem(trade, df)

        self.assertIsNotNone(adj)
        self.assertEqual(adj.reason, "REGIME_SHIFT")

if __name__ == '__main__':
    unittest.main()
