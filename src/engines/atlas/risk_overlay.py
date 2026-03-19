"""ATLAS overlay: transforms macro/flow context into risk multiplier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import REGIME_CRISIS


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class AtlasRiskOverlay:
    risk_on_mult: tuple[float, float] = (1.0, 1.5)
    risk_neutral_mult: tuple[float, float] = (0.7, 1.0)
    risk_off_mult: tuple[float, float] = (0.2, 0.5)
    crisis_mult: float = 0.0

    def compute_multiplier(
        self,
        *,
        regime: str,
        asset_class: str,
        btc_dominance_delta_24h: Optional[float] = None,
        total_mcap_momentum: Optional[float] = None,
        stablecoin_flow: Optional[float] = None,
        vix_level: Optional[float] = None,
        yield_curve_slope: Optional[float] = None,
    ) -> float:
        if regime == REGIME_CRISIS:
            return self.crisis_mult

        if asset_class == "crypto":
            return self._crypto_multiplier(
                btc_dominance_delta_24h=btc_dominance_delta_24h,
                total_mcap_momentum=total_mcap_momentum,
                stablecoin_flow=stablecoin_flow,
            )

        return self._macro_multiplier(vix_level=vix_level, yield_curve_slope=yield_curve_slope)

    def _crypto_multiplier(
        self,
        *,
        btc_dominance_delta_24h: Optional[float],
        total_mcap_momentum: Optional[float],
        stablecoin_flow: Optional[float],
    ) -> float:
        dom = btc_dominance_delta_24h or 0.0
        mcap = total_mcap_momentum or 0.0
        flow = stablecoin_flow or 0.0

        score = (mcap * 10.0) + (flow / 1_000_000.0) - (dom * 2.0)
        if score > 0.5:
            return _clamp(self.risk_on_mult[0] + score * 0.2, *self.risk_on_mult)
        if score < -0.5:
            return _clamp(self.risk_off_mult[1] + score * 0.2, *self.risk_off_mult)
        return _clamp(0.85 + score * 0.1, *self.risk_neutral_mult)

    def _macro_multiplier(
        self,
        *,
        vix_level: Optional[float],
        yield_curve_slope: Optional[float],
    ) -> float:
        vix = vix_level if vix_level is not None else 20.0
        slope = yield_curve_slope if yield_curve_slope is not None else 0.0

        if vix < 18 and slope > 0:
            return 1.10
        if vix > 28 or slope < -0.25:
            return 0.40
        return 0.85
