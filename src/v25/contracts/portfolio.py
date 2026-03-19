"""Portfolio correlation/variance contracts (Phase 2 stubs)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from src.v25.contracts.base import ArgusModel


class CorrelationMatrix(ArgusModel):
    """Phase-2 correlation contract (stub, fields complete)."""

    timestamp: datetime
    window_days: int = Field(gt=0)
    assets: list[str]
    matrix: dict[str, dict[str, float]]
    rolling_correlation: float
    regime_correlation: Optional[float] = None
    is_decorrelated: bool


class PortfolioVariance(ArgusModel):
    """Phase-2 variance contract (stub, fields complete)."""

    timestamp: datetime
    assets: list[str]
    weights: dict[str, float]
    individual_vars: dict[str, float]
    covariance_matrix: dict[str, dict[str, float]]
    portfolio_variance: float = Field(ge=0.0)
    portfolio_vol: float = Field(ge=0.0)
    marginal_risk: dict[str, float]
    diversification_ratio: float = Field(gt=0.0)

