from __future__ import annotations

from src.portfolio.allocator import PortfolioAllocator


def test_allocator_allows_valid_allocation() -> None:
    allocator = PortfolioAllocator()
    ok, reason = allocator.can_allocate(
        current_allocations={"crypto": 0.20, "equity": 0.20, "commodity": 0.05, "cash": 0.55},
        asset_class="crypto",
        position_pct=0.05,
        correlation_with_book=0.3,
        current_heat=0.02,
    )
    assert ok is True
    assert reason == "ok"


def test_allocator_rejects_high_correlation() -> None:
    allocator = PortfolioAllocator()
    ok, reason = allocator.can_allocate(
        current_allocations={"crypto": 0.10, "equity": 0.10, "commodity": 0.05, "cash": 0.75},
        asset_class="crypto",
        position_pct=0.03,
        correlation_with_book=0.9,
        current_heat=0.01,
    )
    assert ok is False
    assert reason == "correlation_limit_exceeded"


def test_allocator_rejects_bucket_limit_and_cash_floor() -> None:
    allocator = PortfolioAllocator()
    ok, reason = allocator.can_allocate(
        current_allocations={"crypto": 0.48, "equity": 0.20, "commodity": 0.10, "cash": 0.22},
        asset_class="crypto",
        position_pct=0.05,
        correlation_with_book=0.2,
        current_heat=0.02,
    )
    assert ok is False
    assert reason in {"max_crypto_allocation_exceeded", "min_cash_allocation_violated"}


def test_allocator_rejects_portfolio_heat() -> None:
    allocator = PortfolioAllocator()
    ok, reason = allocator.can_allocate(
        current_allocations={"crypto": 0.20, "equity": 0.20, "commodity": 0.05, "cash": 0.55},
        asset_class="commodity",
        position_pct=0.03,
        correlation_with_book=0.2,
        current_heat=0.09,
    )
    assert ok is False
    assert reason == "portfolio_heat_limit_exceeded"
