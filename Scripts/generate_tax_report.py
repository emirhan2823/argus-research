#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.reporting.compliance import ComplianceReporter


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate 8949 and P&L report from trades.csv")
    parser.add_argument("trades_csv", type=Path, help="Path to trades CSV")
    parser.add_argument("--year", type=int, default=date.today().year, help="Tax year to export")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path for 8949 rows (default: tax_report_<year>.csv)",
    )
    parser.add_argument(
        "--statement-json",
        type=Path,
        default=None,
        help="Optional output path for P&L statement JSON",
    )
    args = parser.parse_args()

    output = args.output or Path(f"tax_report_{args.year}.csv")

    reporter = ComplianceReporter(args.trades_csv)
    lots = reporter.generate_8949(args.year)
    reporter.export_csv(lots, output)

    statement = reporter.generate_pnl_statement(
        start=date(args.year, 1, 1),
        end=date(args.year, 12, 31),
    )

    if args.statement_json is not None:
        args.statement_json.parent.mkdir(parents=True, exist_ok=True)
        args.statement_json.write_text(json.dumps(statement, indent=2), encoding="utf-8")

    print(f"Generated 8949 CSV: {output}")
    print(f"Lots: {len(lots)}")
    print(f"Realized PnL: {statement['realized_pnl']:.2f}")
    print(f"Win Rate: {statement['win_rate']:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
