import unittest

from argus_py.portfolio.allocator import PortfolioAllocatorV1


class TestPortfolioAllocatorV1(unittest.TestCase):
    def test_clamped_by_exposure(self):
        alloc = PortfolioAllocatorV1(
            risk_budget_pct=1.0,
            max_asset_exposure_pct=35.0,
            assumed_stop_loss_pct=2.0,
        )
        d = alloc.allocate_single_asset(requested_risk_pct=0.01, current_asset_exposure_pct=0.0)
        # Exposure cap implies max risk 35% * 2% = 0.7%
        self.assertAlmostEqual(d.allowed_risk_pct, 0.7, places=6)
        self.assertEqual(d.reason, "CLAMPED_BY_MAX_ASSET_EXPOSURE")
        self.assertFalse(d.blocked)

    def test_clamped_by_budget(self):
        alloc = PortfolioAllocatorV1(
            risk_budget_pct=0.3,
            max_asset_exposure_pct=100.0,
            assumed_stop_loss_pct=2.0,
        )
        d = alloc.allocate_single_asset(requested_risk_pct=0.01, current_asset_exposure_pct=0.0)
        self.assertAlmostEqual(d.allowed_risk_pct, 0.3, places=6)
        self.assertEqual(d.reason, "CLAMPED_BY_RISK_BUDGET")
        self.assertFalse(d.blocked)

    def test_blocked_when_no_remaining_exposure(self):
        alloc = PortfolioAllocatorV1(
            risk_budget_pct=1.0,
            max_asset_exposure_pct=35.0,
            assumed_stop_loss_pct=2.0,
        )
        d = alloc.allocate_single_asset(requested_risk_pct=0.01, current_asset_exposure_pct=35.0)
        self.assertTrue(d.blocked)
        self.assertEqual(d.reason, "MAX_ASSET_EXPOSURE_REACHED")
        self.assertAlmostEqual(d.allowed_risk_pct, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
