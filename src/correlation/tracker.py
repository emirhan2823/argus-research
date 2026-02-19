"""Correlation tracking for asset pairs (A-01 to A-04)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_correlation(
    prices_a: pd.Series, prices_b: pd.Series, window: int = 100
) -> float:
    """Pearson rolling correlation (last value).

    Computes rolling correlation over ``window`` bars and returns the most
    recent value.  If the series are too short, falls back to the full-
    length Pearson correlation.
    """
    if len(prices_a) < 2 or len(prices_b) < 2:
        return 0.0

    if len(prices_a) >= window and len(prices_b) >= window:
        rolling_corr = prices_a.rolling(window).corr(prices_b)
        last = rolling_corr.iloc[-1]
    else:
        last = prices_a.corr(prices_b)

    if pd.isna(last):
        return 0.0
    return float(last)


def calculate_spread(
    prices_a: pd.Series, prices_b: pd.Series, method: str = "log_ratio"
) -> pd.Series:
    """Compute the spread between two price series.

    Parameters
    ----------
    method : str
        ``"log_ratio"`` — log(A/B)
        ``"zscore"``    — z-scored difference (A − B)
    """
    if method == "log_ratio":
        ratio = prices_a / prices_b
        spread = np.log(ratio)
    elif method == "zscore":
        diff = prices_a - prices_b
        mean = diff.rolling(len(diff), min_periods=1).mean()
        std = diff.rolling(len(diff), min_periods=1).std()
        # Avoid division by zero
        std = std.replace(0, np.nan)
        spread = (diff - mean) / std
    else:
        raise ValueError(f"Unknown spread method: {method!r}")
    return spread


class CorrelationTracker:
    """Maintains correlation state for a set of configured pairs.

    Parameters
    ----------
    pairs_config : list[dict]
        Each dict must contain ``symbol_a`` and ``symbol_b`` keys.
        An optional ``pair_id`` key overrides the auto-generated id.
    window : int
        Rolling correlation window size.
    """

    def __init__(self, pairs_config: list[dict], window: int = 100) -> None:
        self.window = window
        self._pairs: dict[str, dict] = {}
        for cfg in pairs_config:
            pair_id = cfg.get("pair_id", f"{cfg['symbol_a']}_{cfg['symbol_b']}")
            self._pairs[pair_id] = {
                "pair_id": pair_id,
                "symbol_a": cfg["symbol_a"],
                "symbol_b": cfg["symbol_b"],
                "correlation": 0.0,
                "spread_zscore": 0.0,
            }

    def update(self, prices: dict[str, pd.Series]) -> list:
        """Recompute all pair correlations from latest price data.

        Parameters
        ----------
        prices : dict[str, pd.Series]
            Mapping of symbol -> price series.

        Returns
        -------
        list[dict]
            Updated pair state dicts.
        """
        results: list[dict] = []
        for pair_id, pair in self._pairs.items():
            sym_a = pair["symbol_a"]
            sym_b = pair["symbol_b"]
            if sym_a not in prices or sym_b not in prices:
                results.append(dict(pair))
                continue

            pa = prices[sym_a]
            pb = prices[sym_b]
            corr = calculate_correlation(pa, pb, self.window)
            spread = calculate_spread(pa, pb, method="log_ratio")

            # Compute z-score of the spread
            if len(spread.dropna()) >= 2:
                mean_s = float(spread.mean())
                std_s = float(spread.std())
                if std_s > 0:
                    zscore = (float(spread.iloc[-1]) - mean_s) / std_s
                else:
                    zscore = 0.0
            else:
                zscore = 0.0

            pair["correlation"] = corr
            pair["spread_zscore"] = zscore
            results.append(dict(pair))

        return results

    def get_pair(self, pair_id: str) -> dict | None:
        """Return current state for a pair, or None if not found."""
        pair = self._pairs.get(pair_id)
        if pair is None:
            return None
        return dict(pair)
