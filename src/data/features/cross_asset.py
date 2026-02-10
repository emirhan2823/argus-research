"""ARGUS v2.0 — Cross-asset features (4).

Primarily crypto-focused. Optional for other asset classes.
"""

from __future__ import annotations

from typing import Optional


def compute_cross_asset_features(
    btc_dominance_delta_24h: Optional[float] = None,
    btc_eth_corr_30d: Optional[float] = None,
    total_mcap_momentum: Optional[float] = None,
    stablecoin_flow: Optional[float] = None,
) -> dict[str, Optional[float]]:
    """Return cross-asset features. All optional.

    Args:
        btc_dominance_delta_24h: Change in BTC dominance over 24h.
        btc_eth_corr_30d: BTC-ETH rolling 30d correlation.
        total_mcap_momentum: Total crypto market cap momentum.
        stablecoin_flow: Net stablecoin flow (positive = inflow).

    Returns:
        Dict with 4 cross-asset feature keys.
    """
    return {
        "btc_dominance_delta_24h": btc_dominance_delta_24h,
        "btc_eth_corr_30d": btc_eth_corr_30d,
        "total_mcap_momentum": total_mcap_momentum,
        "stablecoin_flow": stablecoin_flow,
    }
