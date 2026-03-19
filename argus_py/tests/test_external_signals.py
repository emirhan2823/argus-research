import os
import tempfile
import unittest

from argus_py.signals.external import ExternalSignalProvider


class TestExternalSignals(unittest.TestCase):
    def test_load_and_filter_by_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "signals.csv")
            with open(p, "w") as f:
                f.write("timestamp,symbol,source,direction,confidence,note\n")
                f.write("1700000000000,BTCUSDT,news_feed,BUY,0.8,headline\n")
                f.write("1700000060000,ETHUSDT,trader_x,SELL,0.9,copy\n")
            provider = ExternalSignalProvider.from_csv(p, symbol="BTCUSDT")
            self.assertEqual(provider.size, 1)
            s = provider.latest_for(bar_ts=1700000120.0, max_age_sec=600)
            self.assertIsNotNone(s)
            self.assertEqual(s.direction, "BUY")
            self.assertEqual(s.source, "news_feed")

    def test_latest_for_respects_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "signals.csv")
            with open(p, "w") as f:
                f.write("timestamp,symbol,source,direction,confidence,note\n")
                f.write("1709251200000,BTCUSDT,trader_y,LONG,1.0,entry\n")
            provider = ExternalSignalProvider.from_csv(p, symbol="BTCUSDT")
            # 2024-03-01T00:20:00 UTC
            ts = 1709252400.0
            recent = provider.latest_for(bar_ts=ts, max_age_sec=3600)
            stale = provider.latest_for(bar_ts=ts, max_age_sec=60)
            self.assertIsNotNone(recent)
            self.assertIsNone(stale)


if __name__ == "__main__":
    unittest.main()
