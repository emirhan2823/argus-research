import os
import tempfile
import unittest

from argus_py.adapters import MarketLoadRequest, build_market_adapter
from argus_py.adapters.bist_stub import BistStubAdapter
from argus_py.adapters.crypto_csv_adapter import CryptoCsvAdapter
from argus_py.adapters.us_equity_stub import USEquityStubAdapter


def _write_one_bar_csv(path: str) -> None:
    with open(path, "w") as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("1700000000000,100,110,90,105,1000\n")


def _write_bar_csv(path: str, ts_ms: int, close_px: float) -> None:
    with open(path, "w") as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write(f"{ts_ms},{close_px},{close_px+1},{close_px-1},{close_px},1000\n")


class TestMarketAdapters(unittest.TestCase):
    def test_factory_auto_crypto(self):
        adapter = build_market_adapter("crypto", "auto")
        self.assertIsInstance(adapter, CryptoCsvAdapter)

    def test_us_equity_stub_loads_local_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "AAPL.csv")
            _write_one_bar_csv(p)
            req = MarketLoadRequest(data_dir=tmp, symbol="AAPL")
            market = USEquityStubAdapter().load_market(req)
            self.assertEqual(len(market._all_bars), 1)
            self.assertEqual(market.symbol_resolved, "AAPL")

    def test_bist_stub_accepts_dot_is_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "THYAO.IS.csv")
            _write_one_bar_csv(p)
            req = MarketLoadRequest(data_dir=tmp, symbol="THYAO")
            market = BistStubAdapter().load_market(req)
            self.assertEqual(len(market._all_bars), 1)
            self.assertEqual(market.symbol_resolved, "THYAO.IS")

    def test_crypto_adapter_prefers_ranged_cache_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "BTCUSDT_1m_2024-01-01_2024-01-02.csv")
            with open(p, "w") as f:
                f.write("timestamp,open,high,low,close,volume\n")
                f.write("1700000000000,100,110,90,105,1000\n")
                f.write("1700000060000,101,111,91,106,1001\n")
            req = MarketLoadRequest(
                data_dir=tmp,
                symbol="BTCUSDT",
                start_date="2024-01-01",
                end_date="2024-01-02",
                max_bars=1,
            )
            market = CryptoCsvAdapter().load_market(req)
            self.assertEqual(len(market._all_bars), 1)
            self.assertEqual(market.symbol_requested, "BTCUSDT")

    def test_crypto_adapter_filters_range_before_max_bars_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Jan 1 2024 00:00:00 UTC
            _write_bar_csv(os.path.join(tmp, "BTCUSDT_1m_2024-01-01_2024-01-02.csv"), 1704067200000, 42000.0)
            # Mar 10 2024 00:00:00 UTC
            _write_bar_csv(os.path.join(tmp, "BTCUSDT_1m_2024-03-10_2024-03-11.csv"), 1710028800000, 68000.0)

            req = MarketLoadRequest(
                data_dir=tmp,
                symbol="BTCUSDT",
                start_date="2024-03-01",
                end_date="2024-04-01",
                max_bars=1,
            )
            market = CryptoCsvAdapter().load_market(req)

            self.assertEqual(len(market._all_bars), 1)
            self.assertAlmostEqual(market._all_bars[0].close, 68000.0)


if __name__ == "__main__":
    unittest.main()
