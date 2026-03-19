import unittest
from argus_py.data.market_state import Bar, MarketState

class TestMarketState(unittest.TestCase):
    def setUp(self):
        self.bars = [
            Bar(100, 10, 12, 9, 11, 100),
            Bar(200, 11, 13, 10, 12, 200),
            Bar(300, 12, 14, 11, 13, 300)
        ]
        self.market = MarketState(self.bars)

    def test_initialization(self):
        # Should start at -1
        with self.assertRaises(ValueError):
            _ = self.market.latest_bar

    def test_history_limitation(self):
        self.market.set_time(1) # At Bar 200
        
        # Should see 100 and 200
        hist = self.market.history
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[-1].timestamp, 200)
        
        # Should NOT see 300
        self.assertTrue(all(b.timestamp <= 200 for b in hist))
        
    def test_advance(self):
        self.market.set_time(0)
        self.assertEqual(self.market.latest_bar.timestamp, 100)
        
        res = self.market.advance()
        self.assertTrue(res)
        self.assertEqual(self.market.latest_bar.timestamp, 200)
        
        res = self.market.advance()
        self.assertTrue(res)
        self.assertEqual(self.market.latest_bar.timestamp, 300)
        
        res = self.market.advance()
        self.assertFalse(res) # End of data

if __name__ == '__main__':
    unittest.main()
