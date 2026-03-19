from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AtlasCInputs:
    nvt_ratio: float
    mvrv_ratio: float
    exchange_reserve_change_7d: float
    active_address_change_7d: float
    funding_rate: float


@dataclass(frozen=True)
class AtlasCResult:
    score: float
    regime_bias: str
    components: dict[str, float]
    reason: str


class AtlasCEngine:
    """On-chain composite score engine for ATLAS-C."""

    def __init__(
        self,
        w_nvt: float = 0.23,
        w_mvrv: float = 0.27,
        w_reserves: float = 0.20,
        w_active: float = 0.20,
        w_funding: float = 0.10,
    ) -> None:
        total = w_nvt + w_mvrv + w_reserves + w_active + w_funding
        if abs(total - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1.0")
        self.weights = {
            "nvt": w_nvt,
            "mvrv": w_mvrv,
            "reserves": w_reserves,
            "active": w_active,
            "funding": w_funding,
        }

    def evaluate(self, x: AtlasCInputs) -> AtlasCResult:
        components = {
            "nvt": self._score_nvt(x.nvt_ratio),
            "mvrv": self._score_mvrv(x.mvrv_ratio),
            "reserves": self._score_reserves(x.exchange_reserve_change_7d),
            "active": self._score_active(x.active_address_change_7d),
            "funding": self._score_funding(x.funding_rate),
        }
        score = float(sum(self.weights[k] * components[k] for k in components))

        if score >= 62.0:
            bias = "RISK_ON"
        elif score <= 40.0:
            bias = "RISK_OFF"
        else:
            bias = "NEUTRAL"

        reason = (
            f"ATLAS-C score={score:.1f} bias={bias} | "
            f"nvt={components['nvt']:.1f} mvrv={components['mvrv']:.1f} "
            f"reserves={components['reserves']:.1f} active={components['active']:.1f} "
            f"funding={components['funding']:.1f}"
        )
        return AtlasCResult(score=score, regime_bias=bias, components=components, reason=reason)

    @staticmethod
    def _clip(v: float) -> float:
        return float(max(0.0, min(100.0, v)))

    def _score_nvt(self, nvt: float) -> float:
        # Lower NVT implies better valuation support.
        return self._clip(100.0 - ((nvt - 35.0) * 0.9))

    def _score_mvrv(self, mvrv: float) -> float:
        # Healthy region around 0.9-1.8.
        if mvrv <= 0.5:
            return 25.0
        if mvrv <= 1.8:
            return self._clip(60.0 + (1.8 - mvrv) * 25.0)
        return self._clip(55.0 - (mvrv - 1.8) * 22.0)

    def _score_reserves(self, change_7d: float) -> float:
        # Reserve outflow (negative change) bullish.
        return self._clip(50.0 + (-change_7d * 8.0))

    def _score_active(self, change_7d: float) -> float:
        return self._clip(50.0 + (change_7d * 6.0))

    def _score_funding(self, funding_rate: float) -> float:
        # Slightly positive is healthy; extreme positive/negative penalized.
        basis = 55.0 - abs(funding_rate * 10000.0) * 2.5
        if funding_rate < -0.0005:
            basis += 6.0
        return self._clip(basis)
