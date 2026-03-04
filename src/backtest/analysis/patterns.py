"""Pattern mining — find golden (winning) and toxic (losing) condition combos.

Includes Wilson CI filtering, coverage, and time-split OOS validation.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from math import sqrt
from typing import Any

import numpy as np
import pandas as pd

from .buckets import BUCKET_DEFS, _assign_bucket, wilson_ci_lower, wilson_ci_upper

logger = logging.getLogger(__name__)

# Minimum OOS trades for a valid OOS confirmation (kritik ayar #5)
MIN_OOS_TRADES = 5


@dataclass
class PatternResult:
    conditions: dict[str, str]
    n_trades: int
    win_rate: float
    wilson_ci_low: float
    avg_return: float
    total_return: float
    pf: float | None
    score: float
    coverage: float           # n_trades / total_trades
    oos_win_rate: float       # out-of-sample WR
    oos_n_trades: int         # OOS trade count
    oos_confirmed: bool | None  # |train_wr - oos_wr| < 0.15; None if insufficient OOS


def _bucketize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add bucket columns for all defined indicators."""
    work = df.copy()
    for indicator, buckets in BUCKET_DEFS.items():
        if indicator not in work.columns:
            continue
        col_name = f"{indicator}_bucket"
        work[col_name] = work[indicator].apply(
            lambda v, b=buckets: _assign_bucket(v, b) if pd.notna(v) else None,
        )
    return work


def _compute_pf(returns: pd.Series) -> float | None:
    gross_profit = float(returns[returns > 0].sum())
    gross_loss = float(abs(returns[returns < 0].sum()))
    if gross_loss < 1e-12:
        return None
    return gross_profit / gross_loss


def _time_split(df: pd.DataFrame, train_frac: float = 0.6) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split DataFrame chronologically by entry_time (60/40 train/test)."""
    sorted_df = df.sort_values("entry_time").reset_index(drop=True)
    split_idx = int(len(sorted_df) * train_frac)
    return sorted_df.iloc[:split_idx], sorted_df.iloc[split_idx:]


def _evaluate_pattern(
    mask: pd.Series,
    df: pd.DataFrame,
    conditions: dict[str, str],
    total_trades: int,
    train_df: pd.DataFrame | None = None,
    test_df: pd.DataFrame | None = None,
) -> PatternResult | None:
    """Evaluate a pattern on the full dataset + OOS split."""
    group = df[mask]
    n = len(group)
    if n == 0:
        return None

    wins = int((group["net_pnl_pct"] > 0).sum())
    wr = wins / n
    returns = group["net_pnl_pct"]
    avg_ret = float(returns.mean())
    total_ret = float(returns.sum())
    pf = _compute_pf(returns)
    ci_low = wilson_ci_lower(wins, n)
    coverage = n / total_trades if total_trades > 0 else 0.0
    score = avg_ret * sqrt(n) * ci_low

    # OOS validation (kritik ayar #5)
    oos_wr = 0.0
    oos_n = 0
    oos_confirmed: bool | None = None

    if train_df is not None and test_df is not None:
        # Apply same conditions to test set
        test_mask = pd.Series(True, index=test_df.index)
        for col, val in conditions.items():
            if col in test_df.columns:
                test_mask &= test_df[col] == val

        oos_group = test_df[test_mask]
        oos_n = len(oos_group)
        if oos_n >= MIN_OOS_TRADES:
            oos_wins = int((oos_group["net_pnl_pct"] > 0).sum())
            oos_wr = oos_wins / oos_n
            oos_confirmed = abs(wr - oos_wr) < 0.15
        else:
            oos_confirmed = None  # insufficient OOS data

    return PatternResult(
        conditions=conditions,
        n_trades=n,
        win_rate=round(wr, 4),
        wilson_ci_low=round(ci_low, 4),
        avg_return=round(avg_ret, 6),
        total_return=round(total_ret, 6),
        pf=round(pf, 3) if pf is not None else None,
        score=round(score, 6),
        coverage=round(coverage, 4),
        oos_win_rate=round(oos_wr, 4),
        oos_n_trades=oos_n,
        oos_confirmed=oos_confirmed,
    )


def _find_patterns(
    df: pd.DataFrame,
    min_trades: int = 8,
    top_n: int = 15,
    max_depth: int = 3,
    golden: bool = True,
) -> list[PatternResult]:
    """Core pattern mining: enumerate condition combos, evaluate, rank.

    Parameters
    ----------
    golden : True = find winning patterns (high WR), False = find toxic patterns (low WR)
    """
    work = _bucketize_columns(df)
    total_trades = len(work)

    # Time split for OOS
    train_df, test_df = _time_split(work)
    train_df = _bucketize_columns(train_df)
    test_df = _bucketize_columns(test_df)

    # Identify bucket columns that have data
    bucket_cols = [c for c in work.columns if c.endswith("_bucket") and work[c].notna().sum() > 0]

    # Always include 'side' as a dimension
    dim_cols = ["side"] + bucket_cols
    dim_cols = [c for c in dim_cols if c in work.columns]

    results: list[PatternResult] = []

    # Enumerate combinations: depth 1 to max_depth
    for depth in range(1, max_depth + 1):
        for combo in itertools.combinations(dim_cols, depth):
            # Group by this combination
            valid = work.dropna(subset=list(combo) + ["net_pnl_pct"])
            if valid.empty:
                continue

            for group_key, group_df in valid.groupby(list(combo), observed=True):
                if len(group_df) < min_trades:
                    continue

                # Build conditions dict
                if isinstance(group_key, tuple):
                    conditions = dict(zip(combo, group_key))
                else:
                    conditions = {combo[0]: group_key}

                # Build mask on full work df
                mask = pd.Series(True, index=work.index)
                for col, val in conditions.items():
                    mask &= work[col] == val

                result = _evaluate_pattern(
                    mask, work, conditions, total_trades,
                    train_df, test_df,
                )
                if result is None:
                    continue

                # Filter by Wilson CI
                if golden:
                    if result.wilson_ci_low < 0.50:
                        continue
                else:
                    ci_upper = wilson_ci_upper(
                        int(result.win_rate * result.n_trades),
                        result.n_trades,
                    )
                    if ci_upper > 0.40:
                        continue

                results.append(result)

    # Rank
    if golden:
        results.sort(key=lambda r: r.score, reverse=True)
    else:
        results.sort(key=lambda r: r.avg_return, reverse=False)

    return results[:top_n]


def find_golden_patterns(
    df: pd.DataFrame,
    min_trades: int = 8,
    top_n: int = 15,
    max_depth: int = 3,
) -> list[PatternResult]:
    """Find winning condition combinations (wilson_ci_low >= 0.50)."""
    return _find_patterns(df, min_trades, top_n, max_depth, golden=True)


def find_toxic_patterns(
    df: pd.DataFrame,
    min_trades: int = 8,
    top_n: int = 15,
    max_depth: int = 3,
) -> list[PatternResult]:
    """Find losing condition combinations (wilson_ci_upper <= 0.40)."""
    return _find_patterns(df, min_trades, top_n, max_depth, golden=False)


def patterns_to_dataframe(patterns: list[PatternResult]) -> pd.DataFrame:
    """Convert pattern results to DataFrame for CSV export."""
    rows: list[dict[str, Any]] = []
    for i, p in enumerate(patterns, 1):
        row: dict[str, Any] = {
            "rank": i,
            "conditions": " & ".join(f"{k}={v}" for k, v in p.conditions.items()),
            "n_trades": p.n_trades,
            "win_rate": p.win_rate,
            "wilson_ci_low": p.wilson_ci_low,
            "avg_return": p.avg_return,
            "total_return": p.total_return,
            "pf": p.pf,
            "score": p.score,
            "coverage": p.coverage,
            "oos_win_rate": p.oos_win_rate,
            "oos_n_trades": p.oos_n_trades,
            "oos_confirmed": p.oos_confirmed,
        }
        rows.append(row)
    return pd.DataFrame(rows)
