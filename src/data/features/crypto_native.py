"""ARGUS v2.0 — Crypto-native features (7).

Crypto ONLY. Returns all None for non-crypto asset classes.
"""

from __future__ import annotations

from typing import Optional

from src.core.constants import AC_CRYPTO


def compute_crypto_native_features(
    asset_class: str,
    funding_rate: Optional[float] = None,
    funding_pctile_30d: Optional[float] = None,
    oi_change_4h_pct: Optional[float] = None,
    oi_change_24h_pct: Optional[float] = None,
    liquidation_est: Optional[float] = None,
    long_short_ratio: Optional[float] = None,
    basis_pct: Optional[float] = None,
) -> dict[str, Optional[float]]:
    """Return crypto-native features. All None if not crypto.

    Args:
        asset_class: Asset class string.
        funding_rate: Current perpetual funding rate.
        funding_pctile_30d: Funding rate percentile over 30 days.
        oi_change_4h_pct: Open interest change in last 4h as percentage.
        oi_change_24h_pct: Open interest change in last 24h as percentage.
        liquidation_est: Estimated liquidation volume (normalized).
        long_short_ratio: Long/short account ratio.
        basis_pct: (Futures - Spot) / Spot as percentage.

    Returns:
        Dict with 7 crypto-native feature keys.
    """
    if asset_class != AC_CRYPTO:
        return {
            "funding_rate": None,
            "funding_pctile_30d": None,
            "oi_change_4h_pct": None,
            "oi_change_24h_pct": None,
            "liquidation_est": None,
            "long_short_ratio": None,
            "basis_pct": None,
        }

    return {
        "funding_rate": funding_rate,
        "funding_pctile_30d": funding_pctile_30d,
        "oi_change_4h_pct": oi_change_4h_pct,
        "oi_change_24h_pct": oi_change_24h_pct,
        "liquidation_est": liquidation_est,
        "long_short_ratio": long_short_ratio,
        "basis_pct": basis_pct,
    }
