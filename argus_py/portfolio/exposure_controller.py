from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List


def _pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return (float(numerator) / float(denominator)) * 100.0


@dataclass(frozen=True)
class PositionExposure:
    symbol: str
    asset_class: str
    notional: float


@dataclass(frozen=True)
class ExposureLimits:
    total_cap_pct: float = 90.0
    per_symbol_cap_pct: float = 35.0
    per_asset_caps_pct: Dict[str, float] = field(
        default_factory=lambda: {
            "crypto": 75.0,
            "stock": 70.0,
            "defi": 40.0,
        }
    )


@dataclass(frozen=True)
class ExposureSnapshot:
    total_exposure_pct: float
    symbol_exposure_pct: float
    asset_exposure_pct: float


@dataclass(frozen=True)
class ExposureDecision:
    accepted: bool
    scale: float
    reason: str
    snapshot: ExposureSnapshot


class ExposureController:
    """
    Portfolio exposure controller for pre-trade checks.

    It does not place orders; it only decides whether and how much of a candidate
    trade can be sized under total / symbol / asset-class caps.
    """

    def __init__(self, limits: ExposureLimits | None = None) -> None:
        self.limits = limits or ExposureLimits()

    def decide(
        self,
        *,
        equity: float,
        existing_positions: Iterable[PositionExposure],
        candidate_symbol: str,
        candidate_asset_class: str,
        candidate_notional: float,
    ) -> ExposureDecision:
        eq = max(1e-9, float(equity))
        cand = max(0.0, float(candidate_notional))
        symbol = str(candidate_symbol)
        asset_class = str(candidate_asset_class).lower()

        positions = list(existing_positions)
        total_current = sum(max(0.0, float(p.notional)) for p in positions)
        symbol_current = sum(max(0.0, float(p.notional)) for p in positions if str(p.symbol) == symbol)
        asset_current = sum(
            max(0.0, float(p.notional)) for p in positions if str(p.asset_class).lower() == asset_class
        )

        snapshot = ExposureSnapshot(
            total_exposure_pct=_pct(total_current, eq),
            symbol_exposure_pct=_pct(symbol_current, eq),
            asset_exposure_pct=_pct(asset_current, eq),
        )
        if cand <= 0.0:
            return ExposureDecision(accepted=False, scale=0.0, reason="ZERO_CANDIDATE_NOTIONAL", snapshot=snapshot)

        total_cap = max(0.0, float(self.limits.total_cap_pct)) / 100.0 * eq
        symbol_cap = max(0.0, float(self.limits.per_symbol_cap_pct)) / 100.0 * eq
        asset_cap_pct = float(self.limits.per_asset_caps_pct.get(asset_class, self.limits.total_cap_pct))
        asset_cap = max(0.0, asset_cap_pct) / 100.0 * eq

        allowed_total = max(0.0, total_cap - total_current)
        allowed_symbol = max(0.0, symbol_cap - symbol_current)
        allowed_asset = max(0.0, asset_cap - asset_current)
        allowed = min(cand, allowed_total, allowed_symbol, allowed_asset)

        if allowed <= 0.0:
            reason = "EXPOSURE_CAP_REACHED"
            if allowed_total <= 0.0:
                reason = "TOTAL_EXPOSURE_CAP_REACHED"
            elif allowed_symbol <= 0.0:
                reason = "SYMBOL_EXPOSURE_CAP_REACHED"
            elif allowed_asset <= 0.0:
                reason = "ASSET_EXPOSURE_CAP_REACHED"
            return ExposureDecision(accepted=False, scale=0.0, reason=reason, snapshot=snapshot)

        scale = min(1.0, allowed / cand)
        if scale >= 1.0:
            return ExposureDecision(accepted=True, scale=1.0, reason="OK", snapshot=snapshot)
        if scale < 0.05:
            return ExposureDecision(accepted=False, scale=0.0, reason="EXPOSURE_SCALE_TOO_SMALL", snapshot=snapshot)
        return ExposureDecision(accepted=True, scale=scale, reason="CLAMPED_BY_EXPOSURE_CAP", snapshot=snapshot)


def positions_from_notional_map(
    positions: Dict[str, float],
    *,
    asset_class: str,
) -> List[PositionExposure]:
    out: List[PositionExposure] = []
    for symbol, notional in positions.items():
        out.append(
            PositionExposure(
                symbol=str(symbol),
                asset_class=str(asset_class),
                notional=max(0.0, float(abs(notional))),
            )
        )
    return out


__all__ = [
    "ExposureController",
    "ExposureDecision",
    "ExposureLimits",
    "ExposureSnapshot",
    "PositionExposure",
    "positions_from_notional_map",
]
