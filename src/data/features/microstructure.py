"""ARGUS v2.0 — Microstructure features (5).

- spread_pct: ALL asset classes
- orderbook_imbalance, trade_flow_imbalance, depth_ratio, large_trade_ratio: crypto fully, stocks partially
"""

from __future__ import annotations

from typing import Optional


def compute_microstructure_features(
    spread_pct: float,
    orderbook_imbalance: Optional[float] = None,
    trade_flow_imbalance: Optional[float] = None,
    depth_ratio: Optional[float] = None,
    large_trade_ratio: Optional[float] = None,
) -> dict[str, Optional[float]]:
    """Compute microstructure features.

    For non-crypto assets, pass None for crypto-specific fields.

    Args:
        spread_pct: Current bid-ask spread as percentage of mid price.
        orderbook_imbalance: (bid_volume - ask_volume) / total near mid. Crypto only.
        trade_flow_imbalance: Net buyer-initiated trades / total. Crypto only.
        depth_ratio: Bid depth / ask depth within 2% of mid. Crypto only.
        large_trade_ratio: Proportion of volume from large trades. Crypto only.

    Returns:
        Dict with 5 microstructure feature keys.
    """
    return {
        "spread_pct": spread_pct,
        "orderbook_imbalance": orderbook_imbalance,
        "trade_flow_imbalance": trade_flow_imbalance,
        "depth_ratio": depth_ratio,
        "large_trade_ratio": large_trade_ratio,
    }
