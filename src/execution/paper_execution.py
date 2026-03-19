"""Paper-only execution realism: slippage and fee models.

These functions are used ONLY in paper/backtest mode to simulate
realistic execution costs. They do NOT affect live trading logic.
"""

from __future__ import annotations


def compute_paper_slippage(
    *,
    atr_14_pct: float,
    volume_ratio: float,
) -> float:
    """Compute dynamic slippage for paper trading.

    Parameters
    ----------
    atr_14_pct : float
        ATR(14) as a percentage of price (e.g. 0.02 = 2%).
    volume_ratio : float
        Current volume / 20-period avg volume.

    Returns
    -------
    float
        Slippage as a fraction (e.g. 0.0005 = 0.05%).
        Clamped to [0.0001, 0.003].
    """
    base_slippage = 0.0002
    vol_component = min(atr_14_pct * 0.5, 0.002)
    liquidity_penalty = max(0.0, 0.001 - volume_ratio * 0.0005)
    raw = base_slippage + vol_component + liquidity_penalty
    return max(0.0001, min(raw, 0.003))


def compute_paper_fees(
    *,
    size_usd: float,
    fee_pct: float,
) -> float:
    """Compute trading fee for paper execution.

    Parameters
    ----------
    size_usd : float
        Notional position size in USD.
    fee_pct : float
        Fee rate as a fraction (e.g. 0.0004 = 0.04%).

    Returns
    -------
    float
        Fee amount in USD (always non-negative).
    """
    return max(0.0, abs(size_usd) * abs(fee_pct))
