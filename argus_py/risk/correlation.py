from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import pandas as pd


@dataclass(frozen=True)
class CorrelationAdjustment:
    symbol: str
    current_notional: float
    adjusted_notional: float
    scale: float
    max_abs_corr: float
    reason: str


class CorrelationRiskMonitor:
    """Scales position notionals when cross-asset correlation breaches limit."""

    def __init__(self, threshold: float = 0.7, min_scale: float = 0.3) -> None:
        if threshold <= 0.0 or threshold > 1.0:
            raise ValueError("threshold must be within (0, 1]")
        if min_scale <= 0.0 or min_scale > 1.0:
            raise ValueError("min_scale must be within (0, 1]")
        self.threshold = float(threshold)
        self.min_scale = float(min_scale)

    def correlation_matrix(self, prices: pd.DataFrame) -> pd.DataFrame:
        if prices.empty:
            raise ValueError("prices cannot be empty")
        returns = prices.pct_change().dropna(axis=0, how="any")
        if returns.empty:
            raise ValueError("insufficient price history")
        return returns.corr().fillna(0.0)

    def scale_positions(
        self,
        prices: pd.DataFrame,
        target_notional: Dict[str, float],
    ) -> Tuple[Dict[str, float], Dict[str, CorrelationAdjustment]]:
        corr = self.correlation_matrix(prices)
        adjusted: Dict[str, float] = {}
        details: Dict[str, CorrelationAdjustment] = {}

        for symbol, notional in target_notional.items():
            base = float(notional)
            if symbol not in corr.columns:
                adjusted[symbol] = base
                details[symbol] = CorrelationAdjustment(
                    symbol=symbol,
                    current_notional=base,
                    adjusted_notional=base,
                    scale=1.0,
                    max_abs_corr=0.0,
                    reason="No correlation data for symbol",
                )
                continue

            row = corr.loc[symbol].drop(labels=[symbol], errors="ignore").abs()
            max_corr = float(row.max()) if not row.empty else 0.0

            if max_corr <= self.threshold:
                scale = 1.0
                reason = "Within correlation limit"
            else:
                scale = max(self.min_scale, self.threshold / max_corr)
                reason = f"Scaled due to max_corr={max_corr:.3f} > threshold={self.threshold:.3f}"

            new_notional = base * scale
            adjusted[symbol] = new_notional
            details[symbol] = CorrelationAdjustment(
                symbol=symbol,
                current_notional=base,
                adjusted_notional=new_notional,
                scale=scale,
                max_abs_corr=max_corr,
                reason=reason,
            )

        return adjusted, details


__all__ = ["CorrelationRiskMonitor", "CorrelationAdjustment"]
