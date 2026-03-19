"""ARGUS v2.0 — ML output features (8).

ALL asset classes. Values come from Chronos and LightGBM models.
This module provides a pass-through interface for consistency.
"""

from __future__ import annotations

from typing import Optional


def compute_ml_features(
    chronos_forecast_1h: Optional[float] = None,
    chronos_confidence_width: Optional[float] = None,
    lgbm_direction: Optional[int] = None,
    lgbm_confidence: Optional[float] = None,
    meta_label_score: Optional[float] = None,
    regime_prob_trending: Optional[float] = None,
    regime_prob_ranging: Optional[float] = None,
    regime_prob_volatile: Optional[float] = None,
) -> dict[str, Optional[float | int]]:
    """Return ML output features.

    These values are populated by the ML pipeline (Chronos + LightGBM).
    When ML models are not active/trained, all return None.

    Returns:
        Dict with 8 ML feature keys.
    """
    return {
        "chronos_forecast_1h": chronos_forecast_1h,
        "chronos_confidence_width": chronos_confidence_width,
        "lgbm_direction": lgbm_direction,
        "lgbm_confidence": lgbm_confidence,
        "meta_label_score": meta_label_score,
        "regime_prob_trending": regime_prob_trending,
        "regime_prob_ranging": regime_prob_ranging,
        "regime_prob_volatile": regime_prob_volatile,
    }
