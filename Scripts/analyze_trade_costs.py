#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.reporting.trade_cost_analyzer import write_trade_cost_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze trade costs from run_dir/trades.csv")
    parser.add_argument("--run-dir", "--run_dir", dest="run_dir", type=Path, required=True)
    parser.add_argument(
        "--out-md",
        "--out_md",
        dest="out_md",
        type=Path,
        default=Path("reports/year2/trade_costs.md"),
    )
    parser.add_argument(
        "--out-json",
        "--out_json",
        dest="out_json",
        type=Path,
        default=Path("reports/year2/trade_costs.json"),
    )
    args = parser.parse_args()

    summary = write_trade_cost_report(run_dir=args.run_dir, out_md=args.out_md, out_json=args.out_json)
    print(f"[trade_costs] wrote {args.out_md}")
    print(f"[trade_costs] wrote {args.out_json}")
    print(
        f"[trade_costs] closed_trades={summary.closed_trades} total_cost={summary.total_cost:.6f} total_pnl={summary.total_pnl:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
