import unittest
from argus_py.broker.paper import PaperBroker

class TestRealism(unittest.TestCase):
    def test_fee_and_slippage_calc(self):
        # Config: 10bps fee, 5bps slippage, 2bps spread, use_bid_ask=True
        cfg = {
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
            "spread_bps": 2.0,
            "use_bid_ask": True
        }
        broker = PaperBroker(start_balance=1000, realism_config=cfg)
        
        # Test BUY Entry (Ask price)
        # Price 100
        # Ask = 100 * (1 + 2/10000 + 5/10000) = 100 * 1.0007 = 100.07
        p = broker._get_execution_price(100.0, "BUY", is_entry=True)
        self.assertAlmostEqual(p, 100.07, places=4)
        
        # Test SELL Entry (Bid price)
        # Bid = 100 * (1 - 2/10000 - 5/10000) = 100 * 0.9993 = 99.93
        p = broker._get_execution_price(100.0, "SELL", is_entry=True)
        self.assertAlmostEqual(p, 99.93, places=4)

    def test_guardrails_rejection(self):
        cfg = {
            "max_risk_per_trade_pct": 1.0, # 1% Max Risk
            "slippage_bps": 0,
            "fee_bps": 0
        }
        broker = PaperBroker(start_balance=1000, realism_config=cfg)
        
        # Try to execute trade with 5% risk
        # Price 100. SL 90. Dist 10.
        # Qty 5 -> Risk = 5 * 10 = 50. Equity 1000. Risk% = 5%.
        # execute_strategy logic calculates Qty based on risk_pct passed to it (usually from logic).
        # But if we force a massive risk via args?
        # Actually execute_strategy limits Qty to `risk_pct`.
        # The Guardrail checks if the *resulting* risk violates the CAP.
        # If `risk_pct` param passed to execute is 0.05, and cap is 0.01:
        
        success, reason = broker.execute_strategy(
            "BTC", "GO", "BUY", 100.0, 0, risk_pct=0.05, leverage=1.0
        )
        self.assertFalse(success)
        self.assertIn("REJECT_RISK_CAP", reason)

if __name__ == '__main__':
    unittest.main()
