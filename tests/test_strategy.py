import unittest
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.strategies.trend_following import TrendFollowingStrategy
from src.core.risk_manager import RiskManager

class TestStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = TrendFollowingStrategy(risk_manager=None)

    def test_indicators_calculation(self):
        # Create dummy data
        dates = pd.date_range(start='2023-01-01', periods=300, freq='4h')
        data = pd.DataFrame({
            'open': np.linspace(100, 200, 300),
            'high': np.linspace(101, 201, 300),
            'low': np.linspace(99, 199, 300),
            'close': np.linspace(100, 200, 300),
            'volume': 1000
        }, index=dates)

        data = self.strategy.calculate_indicators(data)

        self.assertIn('ema_short', data.columns)
        self.assertIn('ema_long', data.columns)
        self.assertIn('rsi', data.columns)
        self.assertIn('atr', data.columns)

    def test_no_signal_without_data(self):
        empty_df = pd.DataFrame()
        signal, meta = self.strategy.generate_signal(empty_df)
        self.assertIsNone(signal)

if __name__ == '__main__':
    unittest.main()
