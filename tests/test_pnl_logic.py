import unittest
import sys
import os


from src.core.risk_manager import RiskManager

class TestPnLLogic(unittest.TestCase):

    def setUp(self):
        self.rm = RiskManager(initial_balance=10000.0)

    def test_daily_pnl_calculation(self):
        # Initial state: Start 10000, Current 10000
        self.assertEqual(self.rm.daily_pnl, 0.0)

        # Update balance: Profit +100
        self.rm.update_balance(10100.0)
        self.assertEqual(self.rm.daily_pnl, 100.0)

        # Update balance: Loss -200 (Total 9900)
        self.rm.update_balance(9900.0)
        self.assertEqual(self.rm.daily_pnl, -100.0)

    def test_reset_daily_pnl(self):
        self.rm.update_balance(10500.0)
        self.assertEqual(self.rm.daily_pnl, 500.0)

        # New day starts
        self.rm.reset_daily_pnl()
        self.assertEqual(self.rm.daily_pnl, 0.0)
        self.assertEqual(self.rm.start_of_day_balance, 10500.0)

        # Next trade loss
        self.rm.update_balance(10400.0)
        self.assertEqual(self.rm.daily_pnl, -100.0) # Relative to 10500

if __name__ == '__main__':
    unittest.main()
