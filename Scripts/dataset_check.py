"""ARGUS -- Dataset smoke check CLI.

Prints first/last timestamp and candle count for a requested symbol+timeframe.

Usage:
    python Scripts/dataset_check.py --symbol BTCUSDT --interval 15m
    python Scripts/dataset_check.py  # defaults to BTCUSDT 15m
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.replay_loader import ReplayLoader


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset smoke check")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--store-root", default="data/binance")
    args = parser.parse_args()

    loader = ReplayLoader(root=args.store_root)

    try:
        df = loader.load_ohlcv(args.symbol, args.interval, verify=False)
    except FileNotFoundError:
        print(f"[ERROR] No data found for {args.symbol}/{args.interval} in {args.store_root}")
        sys.exit(1)

    if df.empty:
        print(f"[WARN] Empty dataset for {args.symbol}/{args.interval}")
        sys.exit(1)

    print(f"Dataset: {args.symbol} / {args.interval}")
    print(f"  Root:    {args.store_root}")
    print(f"  Candles: {len(df):,}")
    print(f"  First:   {df['timestamp'].iloc[0]}")
    print(f"  Last:    {df['timestamp'].iloc[-1]}")

    # Check for gaps
    if len(df) >= 2:
        diffs = df["timestamp"].diff().dropna()
        expected = diffs.mode().iloc[0]
        gaps = (diffs > expected * 1.5).sum()
        print(f"  Gaps:    {gaps} (expected interval: {expected})")

    # Monthly breakdown
    df["month"] = df["timestamp"].dt.to_period("M")
    monthly = df.groupby("month").size()
    print(f"\n  Monthly breakdown:")
    for month, count in monthly.items():
        print(f"    {month}: {count:,} bars")


if __name__ == "__main__":
    main()
