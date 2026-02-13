import unittest
from src.core.microstructure import calculate_obi_scalar
import pandas as pd

class TestMicrostructure(unittest.TestCase):

    def test_obi_scalar(self):
        # Create dummy order book
        bids = pd.DataFrame({'quantity': [100, 200, 300]}) # Total 600
        asks = pd.DataFrame({'quantity': [10, 20, 30]})    # Total 60

        # Imbalance = (600 - 60) / 660 = 0.81 (Strong Bid Support)

        # Long Trade + Positive Imbalance = 1.0 Scalar
        scalar = calculate_obi_scalar(bids, asks, "LONG")
        self.assertEqual(scalar, 1.0)

        # Short Trade + Positive Imbalance = 0.0 or 0.5 Scalar (Depending on threshold)
        # Imbalance 0.81 > 0.6 (Extreme Buy Pressure) -> VETO Short
        scalar_short = calculate_obi_scalar(bids, asks, "SHORT")
        self.assertEqual(scalar_short, 0.0)

if __name__ == '__main__':
    unittest.main()
