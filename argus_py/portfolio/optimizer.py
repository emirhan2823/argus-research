from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping


def _safe_pct(value: float) -> float:
    return max(0.0, float(value))


@dataclass(frozen=True)
class AllocationCandidate:
    symbol: str
    asset_class: str
    signal_score: float
    expected_return_bps: float
    volatility_bps: float


@dataclass(frozen=True)
class OptimizerConstraints:
    gross_cap_pct: float = 100.0
    per_symbol_cap_pct: float = 20.0
    per_asset_cap_pct: Dict[str, float] = field(
        default_factory=lambda: {
            "crypto": 70.0,
            "stock": 70.0,
            "defi": 35.0,
        }
    )
    cvar_limit_pct: float = 2.5
    corr_penalty: float = 0.5
    min_corr_scale: float = 0.5


@dataclass(frozen=True)
class OptimizerResult:
    target_weights_pct: Dict[str, float]
    total_weight_pct: float
    cvar_proxy_pct: float
    scale_applied: float
    reason: str


class PortfolioOptimizerV2:
    """
    Lightweight portfolio optimizer:
    - Score-based target weighting
    - Per-symbol/per-asset caps
    - Correlation penalty
    - CVaR proxy cap scaling
    """

    def __init__(self, constraints: OptimizerConstraints | None = None) -> None:
        self.constraints = constraints or OptimizerConstraints()

    def optimize(
        self,
        candidates: Iterable[AllocationCandidate],
        *,
        correlation: Mapping[str, Mapping[str, float]] | None = None,
    ) -> OptimizerResult:
        rows = [c for c in candidates if float(c.signal_score) > 0.0]
        if not rows:
            return OptimizerResult(target_weights_pct={}, total_weight_pct=0.0, cvar_proxy_pct=0.0, scale_applied=0.0, reason="NO_CANDIDATES")

        raw: Dict[str, float] = {}
        asset_map: Dict[str, str] = {}
        volatility_map: Dict[str, float] = {}
        for c in rows:
            score = max(0.05, float(c.signal_score) / 100.0)
            edge = max(0.0, float(c.expected_return_bps))
            vol = max(1.0, float(c.volatility_bps))
            raw_score = score * (edge / vol)
            raw[c.symbol] = raw_score
            asset_map[c.symbol] = str(c.asset_class).lower()
            volatility_map[c.symbol] = vol

        total_raw = sum(raw.values())
        if total_raw <= 0.0:
            return OptimizerResult(target_weights_pct={}, total_weight_pct=0.0, cvar_proxy_pct=0.0, scale_applied=0.0, reason="NON_POSITIVE_EDGES")

        gross_cap = _safe_pct(self.constraints.gross_cap_pct)
        weights: Dict[str, float] = {k: (v / total_raw) * gross_cap for k, v in raw.items()}

        # Symbol cap
        sym_cap = _safe_pct(self.constraints.per_symbol_cap_pct)
        for sym in list(weights.keys()):
            weights[sym] = min(weights[sym], sym_cap)

        # Asset cap
        for asset, cap in self.constraints.per_asset_cap_pct.items():
            cap_pct = _safe_pct(cap)
            symbols = [s for s, a in asset_map.items() if a == str(asset).lower()]
            current = sum(weights.get(s, 0.0) for s in symbols)
            if current > cap_pct and current > 0.0:
                scale = cap_pct / current
                for s in symbols:
                    weights[s] *= scale

        # Correlation penalty
        if correlation:
            for sym in list(weights.keys()):
                row = correlation.get(sym, {})
                max_corr = 0.0
                for other, corr_v in row.items():
                    if other == sym:
                        continue
                    max_corr = max(max_corr, abs(float(corr_v)))
                scale = max(self.constraints.min_corr_scale, 1.0 - (self.constraints.corr_penalty * max_corr))
                weights[sym] *= scale

        # CVaR proxy scaling
        cvar_proxy = 0.0
        for sym, w in weights.items():
            vol_bps = volatility_map.get(sym, 1.0)
            cvar_proxy += (w / 100.0) * ((vol_bps / 10000.0) * 2.33 * 100.0)

        scale_applied = 1.0
        cvar_limit = _safe_pct(self.constraints.cvar_limit_pct)
        if cvar_proxy > cvar_limit and cvar_proxy > 0.0:
            scale_applied = cvar_limit / cvar_proxy
            for sym in list(weights.keys()):
                weights[sym] *= scale_applied
            cvar_proxy = cvar_limit

        total_w = sum(max(0.0, v) for v in weights.values())
        if total_w > gross_cap and total_w > 0.0:
            norm = gross_cap / total_w
            for sym in list(weights.keys()):
                weights[sym] *= norm
            total_w = gross_cap

        reason = "OK"
        if scale_applied < 1.0:
            reason = "CVAR_SCALED"
        return OptimizerResult(
            target_weights_pct={k: max(0.0, float(v)) for k, v in weights.items()},
            total_weight_pct=float(total_w),
            cvar_proxy_pct=float(cvar_proxy),
            scale_applied=float(scale_applied),
            reason=reason,
        )


__all__ = [
    "AllocationCandidate",
    "OptimizerConstraints",
    "OptimizerResult",
    "PortfolioOptimizerV2",
]
