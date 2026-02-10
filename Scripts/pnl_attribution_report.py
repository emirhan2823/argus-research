#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.reporting.pnl_attribution import compute_pnl_attribution, write_pnl_attribution_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PnL attribution report from run_dir/trades.csv")
    parser.add_argument("--run-dir", "--run_dir", dest="run_dir", type=Path, required=True)
    parser.add_argument(
        "--out-md",
        "--out_md",
        dest="out_md",
        type=Path,
        default=Path("reports/year2/pnl_attribution.md"),
    )
    parser.add_argument(
        "--out-json",
        "--out_json",
        dest="out_json",
        type=Path,
        default=Path("reports/year2/pnl_attribution.json"),
    )
    args = parser.parse_args()

    report = compute_pnl_attribution(args.run_dir)
    out_md, out_json = write_pnl_attribution_report(report, out_md=args.out_md, out_json=args.out_json)
    print(f"[pnl_attribution] wrote {out_md}")
    print(f"[pnl_attribution] wrote {out_json}")
    print(f"[pnl_attribution] closed_trades={report.total_closed_trades} total_pnl={report.total_realized_pnl:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
