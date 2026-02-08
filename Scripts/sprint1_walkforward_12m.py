#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.walk_forward import WalkForwardEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 12-month walk-forward baseline.")
    parser.add_argument("--data_path", default="argus_py/data", help="Path containing symbol CSV files")
    parser.add_argument("--output_dir", default="runs/wf_test", help="Output directory")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start_date", default="2025-01-01")
    parser.add_argument("--end_date", default="2026-01-01")
    parser.add_argument("--train_months", type=int, default=6)
    parser.add_argument("--test_months", type=int, default=1)
    parser.add_argument("--step_months", type=int, default=1)
    parser.add_argument("--skip_invalid", action="store_true", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    engine = WalkForwardEngine(
        data_path=Path(args.data_path),
        output_dir=Path(args.output_dir),
    )

    windows = engine.create_windows(
        start_date=start_date,
        end_date=end_date,
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
    )

    report = engine.run_full(
        start_date=start_date,
        end_date=end_date,
        symbols=[args.symbol],
        skip_invalid=args.skip_invalid,
    )

    out = engine.save_report(report, filename="walkforward_12m")

    print(f"Created {len(windows)} windows")
    for w in windows[:3]:
        print(f"  Train: {w.train_start} to {w.train_end}")
        print(f"  Test:  {w.test_start} to {w.test_end}")

    print(f"Results windows: {len(report.windows)}")
    print(f"No-data windows: {len(report.no_data_windows)}")
    print(f"Aggregate Sharpe: {report.aggregate_sharpe:.4f}")
    print(f"Aggregate PnL: {report.aggregate_pnl:.4f}")
    print(f"Aggregate DD: {report.aggregate_dd:.4f}")
    print(f"Saved report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
