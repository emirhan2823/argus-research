"""Fee/slippage single source of truth for ARGUS v2.5."""

from __future__ import annotations

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class FeeModel(ArgusModel):
    """Runtime fee model used by SQS/backtest/time-machine."""

    maker_fee_pct: float = Field(gt=0.0)
    taker_fee_pct: float = Field(gt=0.0)
    spread_estimate_pct: float = Field(gt=0.0)
    slippage_base_pct: float = Field(gt=0.0)
    slippage_per_10k: float = Field(gt=0.0)
    backtest_cost_mult: float = Field(gt=0.0)

    @property
    def live_round_trip(self) -> float:
        return (
            self.maker_fee_pct
            + self.taker_fee_pct
            + self.spread_estimate_pct
            + self.slippage_base_pct
        )

    @property
    def backtest_round_trip(self) -> float:
        return self.live_round_trip * self.backtest_cost_mult

    def estimate_slippage(self, notional_usd: float) -> float:
        return self.slippage_base_pct + self.slippage_per_10k * (float(notional_usd) / 10000.0)

