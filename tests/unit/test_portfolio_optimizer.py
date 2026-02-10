from __future__ import annotations

from argus_py.portfolio.optimizer import AllocationCandidate, OptimizerConstraints, PortfolioOptimizerV2


def test_portfolio_optimizer_respects_symbol_and_asset_caps() -> None:
    opt = PortfolioOptimizerV2(
        OptimizerConstraints(
            gross_cap_pct=100.0,
            per_symbol_cap_pct=15.0,
            per_asset_cap_pct={"crypto": 20.0, "stock": 60.0, "defi": 20.0},
            cvar_limit_pct=10.0,
        )
    )
    result = opt.optimize(
        [
            AllocationCandidate("BTCUSDT", "crypto", 90.0, 20.0, 40.0),
            AllocationCandidate("ETHUSDT", "crypto", 85.0, 18.0, 45.0),
            AllocationCandidate("AAPL", "stock", 80.0, 10.0, 25.0),
        ]
    )
    assert result.target_weights_pct["BTCUSDT"] <= 15.0
    assert result.target_weights_pct["ETHUSDT"] <= 15.0
    crypto_total = result.target_weights_pct["BTCUSDT"] + result.target_weights_pct["ETHUSDT"]
    assert crypto_total <= 20.0 + 1e-9


def test_portfolio_optimizer_applies_cvar_scaling() -> None:
    opt = PortfolioOptimizerV2(
        OptimizerConstraints(
            gross_cap_pct=100.0,
            per_symbol_cap_pct=100.0,
            per_asset_cap_pct={"crypto": 100.0},
            cvar_limit_pct=0.5,
        )
    )
    result = opt.optimize(
        [
            AllocationCandidate("BTCUSDT", "crypto", 90.0, 12.0, 250.0),
            AllocationCandidate("ETHUSDT", "crypto", 80.0, 10.0, 220.0),
        ]
    )
    assert result.scale_applied < 1.0
    assert result.reason == "CVAR_SCALED"
    assert result.cvar_proxy_pct <= 0.5 + 1e-9
