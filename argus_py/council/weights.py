from __future__ import annotations

from typing import Dict


class CouncilWeights:
    """Dynamic module weights selected by market regime."""

    TREND_WEIGHTS: Dict[str, float] = {
        "orion": 0.35,
        "aether": 0.20,
        "hermes": 0.15,
        "phoenix": 0.20,
        "aegean": 0.10,
    }

    CHOP_WEIGHTS: Dict[str, float] = {
        "orion": 0.15,
        "aether": 0.30,
        "hermes": 0.20,
        "phoenix": 0.25,
        "aegean": 0.10,
    }

    RISK_OFF_WEIGHTS: Dict[str, float] = {
        "orion": 0.10,
        "aether": 0.40,
        "hermes": 0.30,
        "phoenix": 0.10,
        "aegean": 0.10,
    }

    @classmethod
    def get_for_regime(cls, regime: str) -> Dict[str, float]:
        name = (regime or "TREND").upper()
        if name == "TREND":
            return dict(cls.TREND_WEIGHTS)
        if name == "CHOP":
            return dict(cls.CHOP_WEIGHTS)
        if name == "RISK_OFF":
            return dict(cls.RISK_OFF_WEIGHTS)
        return dict(cls.TREND_WEIGHTS)
