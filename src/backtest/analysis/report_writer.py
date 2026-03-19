"""Report writer — generate CSV files and ANALYSIS_SUMMARY.md.

Includes execution diagnostics: exit reason breakdown, hold time distribution,
leverage impact, time-stop winners vs losers, trade quality × exit reason matrix.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .buckets import wilson_ci_lower
from .extractor import get_match_quality_summary

logger = logging.getLogger(__name__)


def _safe_round(v: Any, n: int = 4) -> Any:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return v


# ---------------------------------------------------------------------------
# Execution diagnostics (G8 + G11)
# ---------------------------------------------------------------------------

def compute_execution_diagnostics(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Compute execution-focused diagnostics.

    Returns dict with keys:
    - exit_reason_breakdown
    - hold_time_distribution
    - leverage_impact
    - time_stop_comparison (G11: winners vs losers)
    - tq_exit_matrix (G11: trade quality grade × exit reason)
    """
    result: dict[str, pd.DataFrame] = {}

    if df.empty:
        return result

    # 1) Exit reason breakdown
    if "reason_exit" in df.columns and "net_pnl_pct" in df.columns:
        exit_groups = df.groupby("reason_exit", observed=True)
        exit_rows: list[dict[str, Any]] = []
        for reason, group in exit_groups:
            n = len(group)
            wins = int((group["net_pnl_pct"] > 0).sum())
            exit_rows.append({
                "reason_exit": reason,
                "trades": n,
                "win_rate": round(wins / n, 4) if n > 0 else 0,
                "wilson_ci_low": round(wilson_ci_lower(wins, n), 4),
                "avg_return": round(float(group["net_pnl_pct"].mean()), 6),
                "total_return": round(float(group["net_pnl_pct"].sum()), 6),
            })
        result["exit_reason_breakdown"] = pd.DataFrame(exit_rows)

    # 2) Hold time distribution
    if "hold_minutes" in df.columns and "net_pnl_pct" in df.columns:
        hold_buckets = [
            ("<15m", 0, 15), ("15-30m", 15, 30), ("30-60m", 30, 60),
            ("1-2h", 60, 120), ("2-4h", 120, 240), ("4h+", 240, float("inf")),
        ]
        hold_rows: list[dict[str, Any]] = []
        for label, lo, hi in hold_buckets:
            mask = (df["hold_minutes"] >= lo) & (df["hold_minutes"] < hi)
            group = df[mask]
            n = len(group)
            if n == 0:
                continue
            wins = int((group["net_pnl_pct"] > 0).sum())
            hold_rows.append({
                "hold_bucket": label,
                "trades": n,
                "win_rate": round(wins / n, 4),
                "wilson_ci_low": round(wilson_ci_lower(wins, n), 4),
                "avg_return": round(float(group["net_pnl_pct"].mean()), 6),
            })
        result["hold_time_distribution"] = pd.DataFrame(hold_rows)

    # 3) Leverage impact
    if "leverage" in df.columns and "net_pnl_pct" in df.columns:
        lev_buckets = [
            ("1x", 0.9, 1.5), ("1.5-3x", 1.5, 3), ("3-5x", 3, 5),
            ("5-10x", 5, 10), ("10x+", 10, float("inf")),
        ]
        lev_rows: list[dict[str, Any]] = []
        for label, lo, hi in lev_buckets:
            mask = (df["leverage"] >= lo) & (df["leverage"] < hi)
            group = df[mask]
            n = len(group)
            if n == 0:
                continue
            wins = int((group["net_pnl_pct"] > 0).sum())
            lev_rows.append({
                "leverage_bucket": label,
                "trades": n,
                "win_rate": round(wins / n, 4),
                "wilson_ci_low": round(wilson_ci_lower(wins, n), 4),
                "avg_return": round(float(group["net_pnl_pct"].mean()), 6),
            })
        result["leverage_impact"] = pd.DataFrame(lev_rows)

    # 4) Time-stop winners vs losers (G11)
    if "reason_exit" in df.columns and "net_pnl_pct" in df.columns:
        time_stop_mask = df["reason_exit"].str.contains("time", case=False, na=False)
        other_mask = ~time_stop_mask
        is_winner = df["net_pnl_pct"] > 0

        groups = {
            "time_stop_winners": df[time_stop_mask & is_winner],
            "time_stop_losers": df[time_stop_mask & ~is_winner],
            "other_exit_winners": df[other_mask & is_winner],
            "other_exit_losers": df[other_mask & ~is_winner],
        }

        ts_rows: list[dict[str, Any]] = []
        for label, group in groups.items():
            n = len(group)
            row: dict[str, Any] = {"group": label, "trades": n}
            if n > 0:
                row["hold_minutes_mean"] = round(float(group["hold_minutes"].mean()), 1) if "hold_minutes" in group.columns else None
                row["hold_minutes_median"] = round(float(group["hold_minutes"].median()), 1) if "hold_minutes" in group.columns else None
                row["confidence_avg"] = round(float(group["confidence"].mean()), 4) if "confidence" in group.columns else None
                row["leverage_avg"] = round(float(group["leverage"].mean()), 2) if "leverage" in group.columns else None
                row["avg_return"] = round(float(group["net_pnl_pct"].mean()), 6)
            else:
                row.update({"hold_minutes_mean": None, "hold_minutes_median": None,
                            "confidence_avg": None, "leverage_avg": None, "avg_return": None})
            ts_rows.append(row)
        result["time_stop_comparison"] = pd.DataFrame(ts_rows)

    # 5) Trade quality grade × exit reason matrix (G11)
    if "filt_tq_grade" in df.columns and "reason_exit" in df.columns:
        _build_tq_exit_matrix(df, result)
    elif "filt_tq_composite" in df.columns and "reason_exit" in df.columns:
        # Derive grade from composite score if grade not available
        df_work = df.copy()
        df_work["_tq_grade"] = pd.cut(
            df_work["filt_tq_composite"],
            bins=[0, 0.50, 0.65, 0.80, 1.01],
            labels=["D", "C", "B", "A"],
            right=False,
        )
        _build_tq_exit_matrix(df_work, result, grade_col="_tq_grade")

    return result


def _build_tq_exit_matrix(
    df: pd.DataFrame,
    result: dict[str, pd.DataFrame],
    grade_col: str = "filt_tq_grade",
) -> None:
    """Build trade quality grade × exit reason WR matrix."""
    if grade_col not in df.columns or "reason_exit" not in df.columns:
        return

    valid = df.dropna(subset=[grade_col, "reason_exit", "net_pnl_pct"])
    if valid.empty:
        return

    rows: list[dict[str, Any]] = []
    for (grade, reason), group in valid.groupby([grade_col, "reason_exit"], observed=True):
        n = len(group)
        wins = int((group["net_pnl_pct"] > 0).sum())
        rows.append({
            "tq_grade": grade,
            "exit_reason": reason,
            "trades": n,
            "win_rate": round(wins / n, 4) if n > 0 else 0,
            "avg_return": round(float(group["net_pnl_pct"].mean()), 6),
        })

    result["tq_exit_matrix"] = pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Long vs Short summary
# ---------------------------------------------------------------------------

def compute_long_short_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute long vs short performance summary."""
    if "side" not in df.columns or "net_pnl_pct" not in df.columns:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for side, group in df.groupby("side"):
        n = len(group)
        wins = int((group["net_pnl_pct"] > 0).sum())
        rows.append({
            "side": side,
            "trades": n,
            "wins": wins,
            "win_rate": round(wins / n, 4) if n > 0 else 0,
            "wilson_ci_low": round(wilson_ci_lower(wins, n), 4),
            "avg_return": round(float(group["net_pnl_pct"].mean()), 6),
            "total_return": round(float(group["net_pnl_pct"].sum()), 6),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------

def write_reports(
    output_dir: Path,
    enriched_df: pd.DataFrame,
    correlation_df: pd.DataFrame,
    bucket_df: pd.DataFrame,
    golden_patterns_df: pd.DataFrame,
    toxic_patterns_df: pd.DataFrame,
) -> list[Path]:
    """Write all analysis outputs to output_dir.

    Returns list of created file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    # 1) enriched_trades.csv
    p = output_dir / "enriched_trades.csv"
    enriched_df.to_csv(p, index=False)
    created.append(p)

    # 2) correlation_matrix.csv
    p = output_dir / "correlation_matrix.csv"
    correlation_df.to_csv(p, index=False)
    created.append(p)

    # 3) indicator_buckets.csv
    p = output_dir / "indicator_buckets.csv"
    bucket_df.to_csv(p, index=False)
    created.append(p)

    # 4) golden_patterns.csv
    p = output_dir / "golden_patterns.csv"
    golden_patterns_df.to_csv(p, index=False)
    created.append(p)

    # 5) toxic_patterns.csv
    p = output_dir / "toxic_patterns.csv"
    toxic_patterns_df.to_csv(p, index=False)
    created.append(p)

    # 6) long_short_tuning.csv
    ls_df = compute_long_short_summary(enriched_df)
    p = output_dir / "long_short_tuning.csv"
    ls_df.to_csv(p, index=False)
    created.append(p)

    # 7) execution_diagnostics.csv (multiple tables in one)
    exec_diag = compute_execution_diagnostics(enriched_df)
    p = output_dir / "execution_diagnostics.csv"
    _write_multi_table_csv(p, exec_diag)
    created.append(p)

    # 8) ANALYSIS_SUMMARY.md
    p = output_dir / "ANALYSIS_SUMMARY.md"
    _write_summary_md(
        p, enriched_df, correlation_df, bucket_df,
        golden_patterns_df, toxic_patterns_df,
        ls_df, exec_diag,
    )
    created.append(p)

    logger.info("Wrote %d report files to %s", len(created), output_dir)
    return created


def _write_multi_table_csv(path: Path, tables: dict[str, pd.DataFrame]) -> None:
    """Write multiple named tables to a single CSV with section headers."""
    with open(path, "w", encoding="utf-8") as f:
        for name, df in tables.items():
            f.write(f"### {name}\n")
            if not df.empty:
                df.to_csv(f, index=False)
            else:
                f.write("(no data)\n")
            f.write("\n")


def _write_summary_md(
    path: Path,
    enriched_df: pd.DataFrame,
    correlation_df: pd.DataFrame,
    bucket_df: pd.DataFrame,
    golden_df: pd.DataFrame,
    toxic_df: pd.DataFrame,
    ls_df: pd.DataFrame,
    exec_diag: dict[str, pd.DataFrame],
) -> None:
    """Write ANALYSIS_SUMMARY.md."""
    match_summary = get_match_quality_summary(enriched_df)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("# Backtest Analysis Summary")
    lines.append(f"Date: {now}")
    lines.append(f"DB Sources: {enriched_df['db_source'].nunique() if 'db_source' in enriched_df.columns else '?'} files, {len(enriched_df)} closed trades")
    lines.append(
        f"Match Quality: {match_summary.get('exact', 0)} exact, "
        f"{match_summary.get('close', 0)} close, "
        f"{match_summary.get('stale', 0)} stale, "
        f"{match_summary.get('future', 0)} future, "
        f"{match_summary.get('unmatched', 0)} unmatched"
    )
    lines.append(
        f"PnL Distribution: p99={match_summary.get('pnl_p99', 0):.4f}, "
        f"p999={match_summary.get('pnl_p999', 0):.4f}, "
        f"max={match_summary.get('pnl_max', 0):.4f}"
    )

    # Regime distribution
    regime_dist = match_summary.get("regime_distribution")
    if regime_dist:
        regime_parts = [f"{k}: {v}" for k, v in sorted(regime_dist.items(), key=lambda x: -x[1])]
        lines.append(f"Regime Distribution: {', '.join(regime_parts)}")

    # Exit reason distribution (quick overview)
    exit_dist = match_summary.get("exit_reason_distribution")
    if exit_dist:
        exit_parts = [f"{k}: {v}" for k, v in sorted(exit_dist.items(), key=lambda x: -x[1])]
        lines.append(f"Exit Reasons: {', '.join(exit_parts)}")

    lines.append("")

    # 1) Top Correlations
    lines.append("## 1) Top Correlations with PnL (Bonferroni-adjusted)")
    if not correlation_df.empty:
        sig = correlation_df[correlation_df.get("reliable", True) == True]  # noqa: E712
        top = sig.head(15)
        lines.append("| Feature | Pearson r | Spearman ρ | p-adj | Significant | n |")
        lines.append("|---------|-----------|------------|-------|-------------|---|")
        for _, row in top.iterrows():
            lines.append(
                f"| {row.get('feature', '')} "
                f"| {_safe_round(row.get('pearson_r'), 4)} "
                f"| {_safe_round(row.get('spearman_rho'), 4)} "
                f"| {_safe_round(row.get('bonf_p_adj'), 4)} "
                f"| {'✓' if row.get('bonf_significant') else '✗'} "
                f"| {row.get('n', '')} |"
            )
    else:
        lines.append("(no correlation data)")
    lines.append("")

    # 2) Long vs Short
    lines.append("## 2) Long vs Short Performance")
    if not ls_df.empty:
        lines.append("| Side | Trades | WR | Wilson CI Low | Avg Return | Total Return |")
        lines.append("|------|--------|-----|--------------|------------|--------------|")
        for _, row in ls_df.iterrows():
            lines.append(
                f"| {row.get('side', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} "
                f"| {_safe_round(row.get('total_return'), 6)} |"
            )
    lines.append("")

    # 3) Indicator Buckets (top insights)
    lines.append("## 3) Indicator Buckets (Top Insights)")
    if not bucket_df.empty:
        # Show top 20 by absolute avg_return
        top_buckets = bucket_df.copy()
        top_buckets["abs_return"] = top_buckets["avg_return"].abs()
        top_buckets = top_buckets.sort_values("abs_return", ascending=False).head(20)
        lines.append("| Indicator | Bucket | Side | Trades | WR | Wilson CI Low | Avg Return | PF |")
        lines.append("|-----------|--------|------|--------|-----|--------------|------------|-----|")
        for _, row in top_buckets.iterrows():
            pf_str = f"{row['pf']}" if row.get("pf") is not None else "N/A"
            if row.get("pf_reliable") is False and row.get("pf") is not None:
                pf_str += "*"
            lines.append(
                f"| {row.get('indicator', '')} "
                f"| {row.get('bucket', '')} "
                f"| {row.get('side', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} "
                f"| {pf_str} |"
            )
    lines.append("")

    # 4) Golden Patterns
    lines.append("## 4) Golden Patterns (Winning Conditions)")
    if not golden_df.empty:
        lines.append("| # | Conditions | Trades | WR | CI Low | Avg Return | Coverage | OOS WR | OOS Conf |")
        lines.append("|---|------------|--------|-----|--------|------------|----------|--------|----------|")
        for _, row in golden_df.iterrows():
            oos_label = _oos_label(row)
            lines.append(
                f"| {row.get('rank', '')} "
                f"| {row.get('conditions', '')} "
                f"| {row.get('n_trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} "
                f"| {_safe_round(row.get('coverage'), 4)} "
                f"| {_safe_round(row.get('oos_win_rate'), 4)} "
                f"| {oos_label} |"
            )
    lines.append("")

    # 5) Toxic Patterns
    lines.append("## 5) Toxic Patterns (Losing Conditions)")
    if not toxic_df.empty:
        lines.append("| # | Conditions | Trades | WR | CI Low | Avg Return | Coverage | OOS WR | OOS Conf |")
        lines.append("|---|------------|--------|-----|--------|------------|----------|--------|----------|")
        for _, row in toxic_df.iterrows():
            oos_label = _oos_label(row)
            lines.append(
                f"| {row.get('rank', '')} "
                f"| {row.get('conditions', '')} "
                f"| {row.get('n_trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} "
                f"| {_safe_round(row.get('coverage'), 4)} "
                f"| {_safe_round(row.get('oos_win_rate'), 4)} "
                f"| {oos_label} |"
            )
    lines.append("")

    # 6) Execution Diagnostics
    lines.append("## 6) Execution Diagnostics")

    # Exit reason
    lines.append("### Exit Reason Breakdown")
    exit_df = exec_diag.get("exit_reason_breakdown", pd.DataFrame())
    if not exit_df.empty:
        lines.append("| Exit Reason | Trades | WR | Wilson CI Low | Avg Return | Total Return |")
        lines.append("|-------------|--------|-----|--------------|------------|--------------|")
        for _, row in exit_df.iterrows():
            lines.append(
                f"| {row.get('reason_exit', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} "
                f"| {_safe_round(row.get('total_return'), 6)} |"
            )
    lines.append("")

    # Hold time
    lines.append("### Hold Time Distribution")
    hold_df = exec_diag.get("hold_time_distribution", pd.DataFrame())
    if not hold_df.empty:
        lines.append("| Hold Bucket | Trades | WR | Wilson CI Low | Avg Return |")
        lines.append("|-------------|--------|-----|--------------|------------|")
        for _, row in hold_df.iterrows():
            lines.append(
                f"| {row.get('hold_bucket', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} |"
            )
    lines.append("")

    # Leverage impact
    lines.append("### Leverage Impact")
    lev_df = exec_diag.get("leverage_impact", pd.DataFrame())
    if not lev_df.empty:
        lines.append("| Leverage Bucket | Trades | WR | Wilson CI Low | Avg Return |")
        lines.append("|-----------------|--------|-----|--------------|------------|")
        for _, row in lev_df.iterrows():
            lines.append(
                f"| {row.get('leverage_bucket', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('wilson_ci_low'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} |"
            )
    lines.append("")

    # Time-stop comparison (G11)
    lines.append("### Time-Stop Winners vs Losers")
    ts_df = exec_diag.get("time_stop_comparison", pd.DataFrame())
    if not ts_df.empty:
        lines.append("| Group | Trades | Hold Min (mean) | Hold Min (median) | Conf Avg | Lev Avg | Avg Return |")
        lines.append("|-------|--------|-----------------|-------------------|----------|---------|------------|")
        for _, row in ts_df.iterrows():
            lines.append(
                f"| {row.get('group', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('hold_minutes_mean'), 1)} "
                f"| {_safe_round(row.get('hold_minutes_median'), 1)} "
                f"| {_safe_round(row.get('confidence_avg'), 4)} "
                f"| {_safe_round(row.get('leverage_avg'), 2)} "
                f"| {_safe_round(row.get('avg_return'), 6)} |"
            )
    lines.append("")

    # TQ × Exit matrix (G11)
    lines.append("### Trade Quality Grade × Exit Reason Matrix")
    tq_df = exec_diag.get("tq_exit_matrix", pd.DataFrame())
    if not tq_df.empty:
        # Pivot to matrix format
        lines.append("| TQ Grade | Exit Reason | Trades | WR | Avg Return |")
        lines.append("|----------|-------------|--------|-----|------------|")
        for _, row in tq_df.iterrows():
            lines.append(
                f"| {row.get('tq_grade', '')} "
                f"| {row.get('exit_reason', '')} "
                f"| {row.get('trades', '')} "
                f"| {_safe_round(row.get('win_rate'), 4)} "
                f"| {_safe_round(row.get('avg_return'), 6)} |"
            )
    else:
        lines.append("(no trade quality grade data — features_snapshot v1)")
    lines.append("")

    # 7) Tuning recommendations placeholder
    lines.append("## 7) Tuning Recommendations")
    lines.append("*(Auto-generated recommendations based on patterns above)*")
    lines.append("")

    # Write
    path.write_text("\n".join(lines), encoding="utf-8")


def _oos_label(row: Any) -> str:
    """Generate OOS confirmation label."""
    conf = row.get("oos_confirmed")
    if conf is True:
        return "YES"
    elif conf is False:
        return "NO †"
    else:
        n = row.get("oos_n_trades", 0)
        if n == 0:
            return "N/A"
        return f"insufficient ({n})"
