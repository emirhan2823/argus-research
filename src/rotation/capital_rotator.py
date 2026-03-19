"""Multi-Asset Capital Rotation Layer.

Scores assets by trend strength and allocates capital to the top N.
Integrates with the EngineOrchestrator to modulate position sizing.

Supports dynamic universe updates from SONAR scanner.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from src.core.types import FeatureVector

if TYPE_CHECKING:
    from src.scanner.sonar import SonarScore


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize value to [0, 1] range. Clamps at boundaries."""
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


@dataclass(frozen=True)
class AssetTrendScore:
    """Trend score breakdown for a single asset."""

    symbol: str
    trend_score: float  # composite [0, 1]
    adx_norm: float
    ema_slope_norm: float
    structure_score: float
    volume_score: float
    rank: int = 0


@dataclass(frozen=True)
class RotationDecision:
    """Capital allocation decision across assets."""

    allocations: dict[str, float]  # symbol -> weight [0, 1], sums to <= 1.0
    scores: list[AssetTrendScore]
    flat_reason: Optional[str] = None  # reason if all flat
    risk_off: bool = False


@dataclass
class CapitalRotator:
    """Rank assets by trend score and allocate capital to the strongest.

    Usage::

        rotator = CapitalRotator(assets=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        decision = rotator.rotate(
            features_by_symbol={"BTCUSDT": fv1, "ETHUSDT": fv2, "SOLUSDT": fv3},
            risk_off=False,
        )
        # decision.allocations == {"BTCUSDT": 0.6, "ETHUSDT": 0.4, "SOLUSDT": 0.0}
    """

    assets: list[str] = field(default_factory=list)
    top_n: int = 2
    min_trend_score: float = 0.30
    risk_off_multiplier: float = 0.5

    # Normalization ranges
    adx_low: float = 10.0
    adx_high: float = 60.0
    ema_slope_low: float = 0.0
    ema_slope_high: float = 0.05
    volume_low: float = 0.5
    volume_high: float = 3.0

    def compute_trend_score(
        self,
        features: FeatureVector,
        structure_score: float = 0.0,
    ) -> AssetTrendScore:
        """Compute composite trend score for a single asset.

        trend_score = mean(norm(ADX), norm(EMA_slope), structure, norm(volume))
        """
        adx_norm = _normalize(features.adx_14, self.adx_low, self.adx_high)
        ema_slope_norm = _normalize(
            abs(features.ema_21_vs_55), self.ema_slope_low, self.ema_slope_high,
        )
        volume_norm = _normalize(
            features.volume_ratio, self.volume_low, self.volume_high,
        )
        struct_clamped = max(0.0, min(1.0, structure_score))

        composite = (adx_norm + ema_slope_norm + struct_clamped + volume_norm) / 4.0

        return AssetTrendScore(
            symbol=features.symbol,
            trend_score=composite,
            adx_norm=adx_norm,
            ema_slope_norm=ema_slope_norm,
            structure_score=struct_clamped,
            volume_score=volume_norm,
        )

    def rotate(
        self,
        features_by_symbol: dict[str, FeatureVector],
        structure_scores: Optional[dict[str, float]] = None,
        risk_off: bool = False,
    ) -> RotationDecision:
        """Rank assets by trend score and allocate capital proportionally.

        Rules:
            1. Score all assets.
            2. Rank descending by trend_score.
            3. Allocate to top_n proportionally.
            4. If all trend_score < min_trend_score → stay flat.
            5. If risk_off → halve allocation weights.
        """
        struct_scores = structure_scores or {}
        scores: list[AssetTrendScore] = []

        for symbol in self.assets:
            fv = features_by_symbol.get(symbol)
            if fv is None:
                continue
            s_score = struct_scores.get(symbol, 0.0)
            ts = self.compute_trend_score(fv, structure_score=s_score)
            scores.append(ts)

        # Sort descending by trend_score
        scores.sort(key=lambda s: s.trend_score, reverse=True)

        # Assign ranks
        scores = [
            dataclasses.replace(s, rank=i + 1) for i, s in enumerate(scores)
        ]

        # Filter by minimum threshold
        eligible = [s for s in scores if s.trend_score >= self.min_trend_score]

        if not eligible:
            return RotationDecision(
                allocations={s.symbol: 0.0 for s in scores},
                scores=scores,
                flat_reason="all_below_threshold",
                risk_off=risk_off,
            )

        top = eligible[: self.top_n]
        total_score = sum(s.trend_score for s in top)

        allocations: dict[str, float] = {}
        for s in scores:
            if any(t.symbol == s.symbol for t in top) and total_score > 0:
                weight = s.trend_score / total_score
                if risk_off:
                    weight *= self.risk_off_multiplier
                allocations[s.symbol] = weight
            else:
                allocations[s.symbol] = 0.0

        return RotationDecision(
            allocations=allocations,
            scores=scores,
            flat_reason=None,
            risk_off=risk_off,
        )

    def update_universe(self, symbols: list[str]) -> None:
        """Replace the asset universe dynamically (e.g. from SONAR scan)."""
        self.assets = list(symbols)

    @classmethod
    def from_sonar_scores(
        cls,
        scores: list[SonarScore],
        top_n: int = 2,
        min_trend_score: float = 0.30,
    ) -> CapitalRotator:
        """Create a CapitalRotator pre-populated from SONAR scan results.

        Converts SONAR 0-100 trend_score to internal 0-1 scale.
        """
        symbols = [s.symbol for s in scores]
        return cls(
            assets=symbols,
            top_n=top_n,
            min_trend_score=min_trend_score,
        )
