#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.reporting.audit_pipeline import AuditPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly audit report from run telemetry CSVs.")
    parser.add_argument("run_dir", type=Path, help="Run directory containing decisions.csv/trades.csv/rejects.csv")
    parser.add_argument("--week", required=True, help="ISO week, e.g. 2026-W06")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    args = parser.parse_args()

    pipeline = AuditPipeline(args.run_dir)
    report = pipeline.generate_weekly_report(args.week)

    if args.json:
        print(pipeline.to_json(report))
    else:
        print(pipeline.to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
