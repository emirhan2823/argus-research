from __future__ import annotations

from argus_py.execution import ExecutionRealismModel, OrderSide, UrgencyLevel
from argus_py.execution.realism import RealismContext


def test_execution_realism_partial_fill_on_depth_limit() -> None:
    model = ExecutionRealismModel(depth_caps_usd={"crypto": 1000.0})
    ctx = RealismContext(
        symbol="BTCUSDT",
        asset_class="crypto",
        venue_id="sim",
        side=OrderSide.BUY,
        urgency=UrgencyLevel.NORMAL,
        regime="HIGH_VOL_CHOP",
        market_price=100.0,
        requested_qty=25.0,  # 2500 notional > depth cap
    )
    plan = model.plan(ctx)
    assert plan.fill_ratio < 1.0
    assert plan.adjusted_qty < ctx.requested_qty
    assert plan.status_hint in {"PARTIAL", "REJECTED_LIQUIDITY"}


def test_execution_realism_latency_and_slippage_increase_with_urgency() -> None:
    model = ExecutionRealismModel()
    low = model.plan(
        RealismContext(
            symbol="BTCUSDT",
            asset_class="crypto",
            venue_id="sim",
            side=OrderSide.BUY,
            urgency=UrgencyLevel.LOW,
            regime="RANGE",
            market_price=100.0,
            requested_qty=1.0,
        )
    )
    high = model.plan(
        RealismContext(
            symbol="BTCUSDT",
            asset_class="crypto",
            venue_id="sim",
            side=OrderSide.BUY,
            urgency=UrgencyLevel.CRITICAL,
            regime="RANGE",
            market_price=100.0,
            requested_qty=1.0,
        )
    )
    assert high.slippage_bps > low.slippage_bps
    assert high.latency_ms < low.latency_ms
