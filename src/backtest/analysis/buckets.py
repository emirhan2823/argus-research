"""Bucket analysis — discretize continuous indicators and compute WR/PF per bucket.

Includes Wilson confidence interval and PF reliability flag.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Bucket definitions — [low, high) convention (kritik ayar #6)
# low inclusive, high exclusive. Last bucket uses inf.
# ---------------------------------------------------------------------------
BUCKET_DEFS: dict[str, list[tuple[str, float, float]]] = {
    "feat_adx_14": [
        ("<15", 0, 15), ("15-25", 15, 25), ("25-40", 25, 40), ("40+", 40, float("inf")),
    ],
    "feat_atr_14_pct": [
        ("<0.5%", 0, 0.005), ("0.5-1.5%", 0.005, 0.015),
        ("1.5-3%", 0.015, 0.03), ("3%+", 0.03, float("inf")),
    ],
    "feat_volume_ratio": [
        ("<0.5", 0, 0.5), ("0.5-0.8", 0.5, 0.8), ("0.8-1.2", 0.8, 1.2),
        ("1.2-2", 1.2, 2), ("2+", 2, float("inf")),
    ],
    "confidence": [
        ("<0.55", 0, 0.55), ("0.55-0.65", 0.55, 0.65),
        ("0.65-0.80", 0.65, 0.80), ("0.80+", 0.80, float("inf")),
    ],
    "filt_sq_score": [
        ("<0.55", 0, 0.55), ("0.55-0.65", 0.55, 0.65),
        ("0.65-0.80", 0.65, 0.80), ("0.80+", 0.80, float("inf")),
    ],
    "filt_confluence_score": [
        ("<0.35", 0, 0.35), ("0.35-0.50", 0.35, 0.50),
        ("0.50-0.70", 0.50, 0.70), ("0.70+", 0.70, float("inf")),
    ],
    "filt_tq_composite": [
        ("<0.50", 0, 0.50), ("0.50-0.65", 0.50, 0.65),
        ("0.65-0.80", 0.65, 0.80), ("0.80+", 0.80, float("inf")),
    ],
    "leverage": [
        ("1-2", 1, 2), ("2-5", 2, 5), ("5-10", 5, 10), ("10+", 10, float("inf")),
    ],
    "hold_minutes": [
        ("<30", 0, 30), ("30-60", 30, 60), ("60-120", 60, 120),
        ("120+", 120, float("inf")),
    ],
}


def wilson_ci_lower(wins: int, n: int, z: float = 1.96) -> float:
    """Wilson score confidence interval lower bound.

    No scipy needed — pure formula.
    """
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n) / denom
    return max(0.0, center - spread)


def wilson_ci_upper(wins: int, n: int, z: float = 1.96) -> float:
    """Wilson score confidence interval upper bound."""
    if n == 0:
        return 1.0
    p = wins / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n) / denom
    return min(1.0, center + spread)


def _assign_bucket(value: float, buckets: list[tuple[str, float, float]]) -> str | None:
    """Assign a value to a bucket using [low, high) convention (kritik ayar #6)."""
    for label, low, high in buckets:
        if low <= value < high:
            return label
    return None


def _compute_pf(returns: pd.Series) -> float | None:
    """Compute profit factor, handling edge cases (G6)."""
    gross_profit = float(returns[returns > 0].sum())
    gross_loss = float(abs(returns[returns < 0].sum()))
    if gross_loss < 1e-12:
        return None  # Avoid inf PF
    return gross_profit / gross_loss


def bucketize_and_analyze(
    df: pd.DataFrame,
    bucket_defs: dict[str, list[tuple[str, float, float]]] | None = None,
    split_by: list[str] | None = None,
    min_trades: int = 8,
) -> pd.DataFrame:
    """Bucketize indicators and compute stats per bucket.

    Parameters
    ----------
    df : enriched trades DataFrame
    bucket_defs : bucket definitions (defaults to BUCKET_DEFS)
    split_by : columns to split by (default: ["side"])
    min_trades : minimum trades per bucket to include

    Returns
    -------
    DataFrame: indicator, bucket, (split cols), trades, wins, win_rate,
    wilson_ci_low, avg_return, total_return, pf, pf_reliable
    """
    if bucket_defs is None:
        bucket_defs = BUCKET_DEFS
    if split_by is None:
        split_by = ["side"]

    results: list[dict[str, Any]] = []

    for indicator, buckets in bucket_defs.items():
        if indicator not in df.columns:
            continue

        # Assign bucket labels
        col_data = df[indicator].dropna()
        if col_data.empty:
            continue

        bucket_labels = col_data.apply(lambda v: _assign_bucket(v, buckets))

        # Merge back
        work = df.loc[col_data.index].copy()
        work["_bucket"] = bucket_labels
        work = work.dropna(subset=["_bucket", "net_pnl_pct"])

        # Group by bucket + split columns
        group_cols = ["_bucket"] + [c for c in split_by if c in work.columns]
        for group_key, group_df in work.groupby(group_cols, observed=True):
            n = len(group_df)
            if n < min_trades:
                continue

            wins = int((group_df["net_pnl_pct"] > 0).sum())
            wr = wins / n
            returns = group_df["net_pnl_pct"]

            row: dict[str, Any] = {"indicator": indicator}

            # Unpack group key
            if isinstance(group_key, tuple):
                row["bucket"] = group_key[0]
                for i, col in enumerate(split_by):
                    if col in work.columns and i + 1 < len(group_key):
                        row[col] = group_key[i + 1]
            else:
                row["bucket"] = group_key

            row["trades"] = n
            row["wins"] = wins
            row["win_rate"] = round(wr, 4)
            row["wilson_ci_low"] = round(wilson_ci_lower(wins, n), 4)
            row["avg_return"] = round(float(returns.mean()), 6)
            row["total_return"] = round(float(returns.sum()), 6)
            row["pf"] = _compute_pf(returns)
            # PF reliable only if n >= 30 AND gross_loss > 0 (G6)
            row["pf_reliable"] = n >= 30 and row["pf"] is not None

            if row["pf"] is not None:
                row["pf"] = round(row["pf"], 3)

            results.append(row)

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df = result_df.sort_values(
            ["indicator", "bucket"], ascending=True,
        ).reset_index(drop=True)
    return result_df
