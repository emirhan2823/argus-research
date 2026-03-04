"""Correlation analysis between features/filters and PnL.

Pearson + Spearman with Bonferroni correction.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Minimum sample size for reliable correlation (kritik ayar #4)
MIN_N_FOR_CORRELATION = 30


def _safe_pearsonr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Pearson correlation without scipy dependency."""
    n = len(x)
    if n < 3:
        return np.nan, 1.0
    mx, my = x.mean(), y.mean()
    dx, dy = x - mx, y - my
    denom = np.sqrt((dx ** 2).sum() * (dy ** 2).sum())
    if denom < 1e-15:
        return 0.0, 1.0
    r = float((dx * dy).sum() / denom)
    # t-test for significance
    if abs(r) >= 1.0:
        return float(np.clip(r, -1, 1)), 0.0
    t_stat = r * np.sqrt((n - 2) / (1 - r ** 2))
    # Approximate p-value using normal for large n
    p = float(2 * _t_survival(abs(t_stat), n - 2))
    return r, p


def _safe_spearmanr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Spearman rank correlation without scipy dependency."""
    n = len(x)
    if n < 3:
        return np.nan, 1.0
    from scipy.stats import spearmanr  # scipy 1.17.0 available
    result = spearmanr(x, y)
    return float(result.statistic), float(result.pvalue)


def _t_survival(t: float, df: int) -> float:
    """Approximate survival function for t-distribution.

    Uses normal approximation for df >= 30, otherwise scipy.
    """
    if df >= 30:
        # Normal approximation
        from math import erfc, sqrt
        return 0.5 * erfc(t / sqrt(2))
    try:
        from scipy.stats import t as t_dist
        return float(t_dist.sf(t, df))
    except ImportError:
        from math import erfc, sqrt
        return 0.5 * erfc(t / sqrt(2))


def compute_correlation_matrix(
    df: pd.DataFrame,
    target: str = "net_pnl_pct",
    min_n: int = MIN_N_FOR_CORRELATION,
) -> pd.DataFrame:
    """Compute Pearson and Spearman correlations of numeric features vs target.

    Parameters
    ----------
    df : enriched trades DataFrame
    target : target column name
    min_n : minimum number of non-NaN pairs for reliable correlation (kritik ayar #4)

    Returns
    -------
    DataFrame with columns: feature, pearson_r, pearson_p, spearman_rho,
    spearman_p, n, bonf_significant, reliable
    """
    if target not in df.columns:
        return pd.DataFrame()

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    skip = {target, "trade_id", "match_dt_seconds", "snap_version"}
    feature_cols = [c for c in numeric_cols if c not in skip]

    results: list[dict[str, Any]] = []
    n_features = len(feature_cols)

    for col in feature_cols:
        mask = df[[col, target]].dropna()
        n = len(mask)
        if n < 3:
            continue

        x = mask[col].values.astype(float)
        y = mask[target].values.astype(float)

        pr, pp = _safe_pearsonr(x, y)
        sr, sp = _safe_spearmanr(x, y)

        # Bonferroni correction (G5)
        bonf_p = min(pp * n_features, 1.0) if not np.isnan(pp) else 1.0
        bonf_significant = bonf_p < 0.05

        # Reliability flag (kritik ayar #4)
        reliable = n >= min_n

        results.append({
            "feature": col,
            "pearson_r": pr,
            "pearson_p": pp,
            "spearman_rho": sr,
            "spearman_p": sp,
            "n": n,
            "bonf_p_adj": bonf_p,
            "bonf_significant": bonf_significant,
            "reliable": reliable,
        })

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df = result_df.sort_values("bonf_p_adj", ascending=True)
    return result_df


def compute_segmented_correlations(
    df: pd.DataFrame,
    segment_col: str = "side",
    target: str = "net_pnl_pct",
    min_n: int = MIN_N_FOR_CORRELATION,
) -> pd.DataFrame:
    """Compute correlations segmented by a categorical column (e.g. side).

    Returns DataFrame with additional 'segment' column.
    """
    if segment_col not in df.columns:
        return compute_correlation_matrix(df, target=target, min_n=min_n)

    parts: list[pd.DataFrame] = []
    for segment_val, sub_df in df.groupby(segment_col):
        corr = compute_correlation_matrix(sub_df, target=target, min_n=min_n)
        if not corr.empty:
            corr.insert(0, "segment", segment_val)
            parts.append(corr)

    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)
