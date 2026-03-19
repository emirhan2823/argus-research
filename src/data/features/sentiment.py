"""ARGUS v2.0 — Sentiment features (3) from HERMES engine.

ALL asset classes. Values come from HERMES engine output, not computed here.
This module provides a pass-through interface for consistency.
"""

from __future__ import annotations

from typing import Optional


def compute_sentiment_features(
    hermes_sentiment_score: Optional[float] = None,
    hermes_sentiment_confidence: Optional[float] = None,
    hermes_urgency: Optional[str] = None,
) -> dict[str, Optional[float | str]]:
    """Return HERMES sentiment features.

    These values are populated by the HERMES engine's news analysis.
    During backtesting or when HERMES is not active, all return None.

    Args:
        hermes_sentiment_score: Sentiment score from -100 to +100.
        hermes_sentiment_confidence: Confidence of sentiment analysis (0-1).
        hermes_urgency: Urgency level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL".

    Returns:
        Dict with 3 sentiment feature keys.
    """
    return {
        "hermes_sentiment_score": hermes_sentiment_score,
        "hermes_sentiment_confidence": hermes_sentiment_confidence,
        "hermes_urgency": hermes_urgency,
    }
