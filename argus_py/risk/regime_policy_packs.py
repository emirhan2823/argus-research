from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RegimePolicy:
    risk_multiplier: float
    min_adx_bonus: float
    max_exp_multiplier: float
    cooldown_bars: int = 0


@dataclass(frozen=True)
class RegimePolicyPack:
    name: str
    regimes: Dict[str, RegimePolicy]


def normalize_regime(regime: str) -> str:
    text = str(regime or "RANGE").upper().strip()
    if text in {"TREND", "BULL_TREND", "BEAR_TREND"}:
        return "TREND"
    if text in {"CHOP", "HIGH_VOL_CHOP", "VOLATILE"}:
        return "CHOP"
    if text in {"RANGE", "LOW_VOL_CALM", "CALM"}:
        return "RANGE"
    return "RANGE"


def default_regime_policy_packs() -> Dict[str, RegimePolicyPack]:
    legacy = RegimePolicyPack(
        name="legacy",
        regimes={
            "TREND": RegimePolicy(1.0, 0.0, 1.0, 0),
            "RANGE": RegimePolicy(1.0, 0.0, 1.0, 0),
            "CHOP": RegimePolicy(1.0, 0.0, 1.0, 0),
        },
    )
    balanced = RegimePolicyPack(
        name="balanced",
        regimes={
            "TREND": RegimePolicy(1.0, 0.0, 1.00, 0),
            "RANGE": RegimePolicy(0.80, 2.0, 0.90, 0),
            "CHOP": RegimePolicy(0.55, 5.0, 0.75, 1),
        },
    )
    strict = RegimePolicyPack(
        name="strict",
        regimes={
            "TREND": RegimePolicy(0.90, 2.0, 0.95, 0),
            "RANGE": RegimePolicy(0.65, 6.0, 0.75, 1),
            "CHOP": RegimePolicy(0.35, 10.0, 0.60, 2),
        },
    )
    return {
        "legacy": legacy,
        "balanced": balanced,
        "strict": strict,
    }


class RegimePolicyResolver:
    def __init__(self, pack_name: str = "legacy") -> None:
        packs = default_regime_policy_packs()
        key = str(pack_name or "legacy").lower().strip()
        self.pack = packs.get(key, packs["legacy"])

    @property
    def name(self) -> str:
        return self.pack.name

    def resolve(self, regime: str) -> RegimePolicy:
        norm = normalize_regime(regime)
        return self.pack.regimes.get(norm, self.pack.regimes["RANGE"])


__all__ = [
    "RegimePolicy",
    "RegimePolicyPack",
    "RegimePolicyResolver",
    "default_regime_policy_packs",
    "normalize_regime",
]
