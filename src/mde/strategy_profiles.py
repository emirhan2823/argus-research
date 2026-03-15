"""Strategy profile resolver for setup/side/volatility specific overrides.

This module lets the pipeline apply different execution/gating behavior for:
- market setup: trend | mr | pump | neutral
- direction: long | short
- volatility bucket: low_vol | normal_vol | high_vol
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_GEMINI,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
)

_TREND_ENGINES = {ENGINE_TITAN, ENGINE_AEGEAN}
_MR_ENGINES = {ENGINE_NAUTILUS, ENGINE_HYDRA, ENGINE_POSEIDON, ENGINE_GEMINI}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class StrategyProfileResolution:
    profile_name: str
    setup: str
    side: str
    vol_bucket: str
    confidence_shift: float
    sl_mult: float
    tp_mult: float
    min_confidence: float | None = None
    min_rr: float | None = None
    crypto_min_rr: float | None = None
    confluence_min_factors: int | None = None
    confluence_min_score: float | None = None


def classify_setup(
    *,
    engine: str,
    regime: str,
    sub_strategy: str | None,
    volume_ratio: float,
    roc_10: float,
) -> str:
    """Classify the signal setup into trend/mr/pump/neutral."""
    regime_up = str(regime or "").upper()
    engine_up = str(engine or "").upper()
    sub = str(sub_strategy or "").upper()

    # Pump mode: abnormal flow + abrupt move.
    if volume_ratio >= 2.2 and abs(roc_10) >= 0.05:
        return "pump"
    if "PUMP" in sub:
        return "pump"

    if engine_up in _TREND_ENGINES or regime_up == "TRENDING":
        return "trend"
    if engine_up in _MR_ENGINES or regime_up == "RANGING":
        return "mr"
    return "neutral"


def classify_vol_bucket(*, atr_pctl: float | None, realized_vol_20d: float) -> str:
    """Classify volatility into low/normal/high buckets."""
    pctl = 0.50 if atr_pctl is None else _clamp(float(atr_pctl), 0.0, 1.0)
    rv = max(0.0, float(realized_vol_20d))
    if pctl <= 0.35 or rv <= 0.03:
        return "low_vol"
    if pctl >= 0.70 or rv >= 0.08:
        return "high_vol"
    return "normal_vol"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_opt_float(node: dict[str, Any], key: str) -> float | None:
    raw = node.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _to_opt_int(node: dict[str, Any], key: str) -> int | None:
    raw = node.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def resolve_strategy_profile(
    *,
    config: dict[str, Any] | None,
    engine: str,
    regime: str,
    side: str,
    sub_strategy: str | None,
    atr_pctl: float | None,
    realized_vol_20d: float,
    volume_ratio: float,
    roc_10: float,
) -> StrategyProfileResolution | None:
    """Resolve a strategy profile row for the current signal context.

    Expected config shape:
      enabled: bool
      defaults: {...}
      profiles:
        trend|mr|pump|neutral:
          long|short:
            low_vol|normal_vol|high_vol: {...}
    """
    cfg = _safe_dict(config)
    if not bool(cfg.get("enabled", False)):
        return None

    side_norm = "short" if str(side).lower() == "short" else "long"
    setup = classify_setup(
        engine=engine,
        regime=regime,
        sub_strategy=sub_strategy,
        volume_ratio=volume_ratio,
        roc_10=roc_10,
    )
    vol_bucket = classify_vol_bucket(atr_pctl=atr_pctl, realized_vol_20d=realized_vol_20d)

    defaults = _safe_dict(cfg.get("defaults"))
    profiles = _safe_dict(cfg.get("profiles"))
    setup_node = _safe_dict(profiles.get(setup))
    side_node = _safe_dict(setup_node.get(side_norm))
    bucket_node = _safe_dict(side_node.get(vol_bucket))

    if not bucket_node and not defaults:
        return None

    merged: dict[str, Any] = dict(defaults)
    merged.update(bucket_node)

    profile_name = f"{setup}.{side_norm}.{vol_bucket}"
    return StrategyProfileResolution(
        profile_name=profile_name,
        setup=setup,
        side=side_norm,
        vol_bucket=vol_bucket,
        confidence_shift=float(merged.get("confidence_shift", 0.0)),
        sl_mult=max(0.50, min(2.50, float(merged.get("sl_mult", 1.0)))),
        tp_mult=max(0.50, min(3.00, float(merged.get("tp_mult", 1.0)))),
        min_confidence=_to_opt_float(merged, "min_confidence"),
        min_rr=_to_opt_float(merged, "min_rr"),
        crypto_min_rr=_to_opt_float(merged, "crypto_min_rr"),
        confluence_min_factors=_to_opt_int(merged, "confluence_min_factors"),
        confluence_min_score=_to_opt_float(merged, "confluence_min_score"),
    )

