import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.core.risk_manager import RiskManager
from config.settings import MAX_RISK_PER_TRADE, MAX_DAILY_LOSS, MAX_DRAWDOWN, LEVERAGE

class TestRiskManager(unittest.TestCase):

    def setUp(self):
        self.rm = RiskManager(initial_balance=10000.0)

    def test_position_sizing(self):
        # Account = 10000, Risk = 1% (100)
        # Entry = 2000, SL = 1900 (Diff = 100)
        # Size = 100 / 100 = 1.0 unit
        size = self.rm.calculate_position_size(2000, 1900, 10000)
        self.assertAlmostEqual(size, 1.0)

    def test_leverage_cap(self):
        # Account = 10000, Leverage = 5 (Max Value = 50000)
        # Entry = 100, SL = 99 (Diff = 1)
        # Risk Amount = 100
        # Theoretical Size = 100 / 1 = 100 units
        # Value = 100 * 100 = 10000 (Allowed, < 50000)

        # Try extreme leverage
        # Entry = 100, SL = 99.9 (Diff = 0.1)
        # Risk Amount = 100
        # Theoretical Size = 100 / 0.1 = 1000 units
        # Value = 1000 * 100 = 100000 ( > 50000 Max)
        # Should be capped at 500 units (50000 / 100)
        size = self.rm.calculate_position_size(100, 99.9, 10000)
        self.assertAlmostEqual(size, 500.0)

    def test_daily_loss_limit(self):
        # Max loss 2% = 200
        self.rm.daily_pnl = -201
        self.assertFalse(self.rm.check_trade_allowed())

        self.rm.daily_pnl = -199
        self.assertTrue(self.rm.check_trade_allowed())

    def test_max_drawdown(self):
        # Max DD 6%
        self.rm.peak_balance = 10000
        self.rm.update_balance(9300) # Drawdown 7%
        self.assertFalse(self.rm.check_trade_allowed())

        self.rm.update_balance(9500) # Drawdown 5%
        # Reset daily PnL to avoid triggering daily loss limit (-500 vs -200)
        self.rm.daily_pnl = 0
        self.assertTrue(self.rm.check_trade_allowed())

if __name__ == '__main__':
    unittest.main()
