#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ops.reliability_watchdog import evaluate_reliability, write_watchdog_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate daemon reliability from heartbeat + metrics files")
    parser.add_argument("--run-dir", "--run_dir", dest="run_dir", type=Path, required=True)
    parser.add_argument("--stale-after-sec", "--stale_after_sec", dest="stale_after_sec", type=float, default=120.0)
    parser.add_argument(
        "--max-error-ratio-pct",
        "--max_error_ratio_pct",
        dest="max_error_ratio_pct",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--out-md",
        "--out_md",
        dest="out_md",
        type=Path,
        default=Path("reports/year2/reliability_watchdog.md"),
    )
    parser.add_argument(
        "--out-json",
        "--out_json",
        dest="out_json",
        type=Path,
        default=Path("reports/year2/reliability_watchdog.json"),
    )
    args = parser.parse_args()

    status = evaluate_reliability(
        args.run_dir,
        stale_after_sec=float(args.stale_after_sec),
        max_error_ratio_pct=float(args.max_error_ratio_pct),
    )
    out_md, out_json = write_watchdog_report(status, out_md=args.out_md, out_json=args.out_json)
    print(f"[watchdog] wrote {out_md}")
    print(f"[watchdog] wrote {out_json}")
    print(f"[watchdog] healthy={status.healthy} reasons={','.join(status.reasons) if status.reasons else 'none'}")
    return 0 if status.healthy else 2


if __name__ == "__main__":
    raise SystemExit(main())
