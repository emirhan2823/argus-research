#!/usr/bin/env python3
"""Backtest correlation analysis CLI.

Usage:
    python Scripts/analyze_backtest.py --db runs/war_backtest_lab/luna_crash_2022/20260301_184945/
    python Scripts/analyze_backtest.py --db path/to/run1/,path/to/run2/ --output-dir reports/analysis
    python Scripts/analyze_backtest.py --db runs/ --min-trades 10 --top-n 20 --timeframe 15m
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.analysis.buckets import bucketize_and_analyze
from src.backtest.analysis.correlations import (
    compute_correlation_matrix,
    compute_segmented_correlations,
)
from src.backtest.analysis.extractor import extract_enriched_trades, timeframe_to_seconds
from src.backtest.analysis.patterns import (
    find_golden_patterns,
    find_toxic_patterns,
    patterns_to_dataframe,
)
from src.backtest.analysis.report_writer import write_reports


def _find_db_files(path_str: str) -> list[Path]:
    """Resolve DB file paths from CLI input.

    Accepts:
    - Single .db file path
    - Directory (recursive **/*.db search)
    - Comma-separated list of paths
    """
    db_files: list[Path] = []
    for part in path_str.split(","):
        p = Path(part.strip())
        if p.is_file() and p.suffix == ".db":
            db_files.append(p)
        elif p.is_dir():
            found = sorted(p.rglob("*.db"))
            db_files.extend(found)
        else:
            # Try glob
            from glob import glob
            matches = glob(str(p))
            for m in matches:
                mp = Path(m)
                if mp.is_file() and mp.suffix == ".db":
                    db_files.append(mp)
    return db_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ARGUS Backtest Correlation Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db", required=True,
        help="DB file, directory (recursive), or comma-separated paths",
    )
    parser.add_argument(
        "--output-dir", default="reports/analysis",
        help="Output directory for reports (default: reports/analysis)",
    )
    parser.add_argument(
        "--min-trades", type=int, default=8,
        help="Minimum trades per bucket/pattern (default: 8)",
    )
    parser.add_argument(
        "--top-n", type=int, default=15,
        help="Number of golden/toxic patterns to show (default: 15)",
    )
    parser.add_argument(
        "--max-depth", type=int, default=3,
        help="Max pattern combination depth (default: 3)",
    )
    parser.add_argument(
        "--timeframe", default="1h",
        help="Timeframe for match quality thresholds (default: 1h)",
    )
    parser.add_argument(
        "--split-by", default="side",
        help="Bucket split columns, comma-separated (default: side)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Find DB files
    db_files = _find_db_files(args.db)
    if not db_files:
        print(f"ERROR: No .db files found at: {args.db}")
        return 1

    print(f"Found {len(db_files)} DB file(s):")
    for f in db_files:
        print(f"  - {f}")
    print()

    bar_seconds = timeframe_to_seconds(args.timeframe)
    split_by = [s.strip() for s in args.split_by.split(",")]
    output_dir = Path(args.output_dir)

    # Phase 1: Extract
    print("Extracting enriched trades...")
    enriched_df = extract_enriched_trades(db_files, bar_seconds=bar_seconds)
    if enriched_df.empty:
        print("ERROR: No closed trades found in any DB.")
        return 1
    print(f"  -> {len(enriched_df)} enriched trades")

    # Sanity check summary
    if "reason_exit" in enriched_df.columns:
        exit_counts = enriched_df["reason_exit"].value_counts()
        print(f"  Exit reasons: {dict(exit_counts)}")
        known = {"stop_loss_hit", "breakeven_stop_hit", "trailing_stop_hit",
                 "time_stop_hit", "time_exit_backtest_sim", "sl", "tp",
                 "trailing", "be_stop", "time_stop"}
        unknown = set(exit_counts.index) - known
        if unknown:
            print(f"  [WARN] Unknown exit reasons: {unknown}")

    if "regime_at_entry" in enriched_df.columns:
        regime_counts = enriched_df["regime_at_entry"].value_counts()
        print(f"  Regimes: {dict(regime_counts)}")
        if "REPLAY" in regime_counts.index:
            print(f"  [WARN] {regime_counts['REPLAY']} trades with regime='REPLAY' (should be actual regime)")

    if "net_pnl_pct" in enriched_df.columns:
        import numpy as _np
        non_finite = (~_np.isfinite(enriched_df["net_pnl_pct"])).sum()
        if non_finite > 0:
            print(f"  [WARN] {non_finite} trades with non-finite PnL (filtered)")

    print()

    # Phase 2: Correlations
    print("Computing correlations...")
    corr_df = compute_correlation_matrix(enriched_df)
    seg_corr_df = compute_segmented_correlations(enriched_df)
    print(f"  -> {len(corr_df)} feature correlations ({len(corr_df[corr_df.get('bonf_significant', False) == True])} Bonferroni-significant)")  # noqa: E712
    print()

    # Phase 3: Bucket analysis
    print("Running bucket analysis...")
    bucket_df = bucketize_and_analyze(
        enriched_df, split_by=split_by, min_trades=args.min_trades,
    )
    print(f"  -> {len(bucket_df)} bucket rows")
    print()

    # Phase 4: Pattern mining
    print("Mining golden patterns...")
    golden = find_golden_patterns(
        enriched_df, min_trades=args.min_trades,
        top_n=args.top_n, max_depth=args.max_depth,
    )
    golden_df = patterns_to_dataframe(golden)
    oos_confirmed = sum(1 for p in golden if p.oos_confirmed is True)
    print(f"  -> {len(golden)} golden patterns ({oos_confirmed} OOS-confirmed)")

    print("Mining toxic patterns...")
    toxic = find_toxic_patterns(
        enriched_df, min_trades=args.min_trades,
        top_n=args.top_n, max_depth=args.max_depth,
    )
    toxic_df = patterns_to_dataframe(toxic)
    oos_confirmed_t = sum(1 for p in toxic if p.oos_confirmed is True)
    print(f"  -> {len(toxic)} toxic patterns ({oos_confirmed_t} OOS-confirmed)")
    print()

    # Phase 5: Write reports
    print(f"Writing reports to {output_dir}/...")
    created = write_reports(
        output_dir, enriched_df, corr_df, bucket_df, golden_df, toxic_df,
    )
    print(f"  -> {len(created)} files created:")
    for f in created:
        print(f"    - {f.name}")

    print()
    print("Done! Open ANALYSIS_SUMMARY.md for the full report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
