#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.stress_scenario_lab import run_stress_scenario_lab, write_stress_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stress scenario lab on realized paper trades")
    parser.add_argument("--run-dir", "--run_dir", dest="run_dir", type=Path, required=True)
    parser.add_argument(
        "--out-md",
        "--out_md",
        dest="out_md",
        type=Path,
        default=Path("reports/year2/stress_scenario_lab.md"),
    )
    parser.add_argument(
        "--out-json",
        "--out_json",
        dest="out_json",
        type=Path,
        default=Path("reports/year2/stress_scenario_lab.json"),
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=["baseline", "fee_slippage_x2", "latency_shock", "gap_down", "loss_cluster"],
    )
    args = parser.parse_args()

    report = run_stress_scenario_lab(args.run_dir, scenarios=args.scenarios)
    out_md, out_json = write_stress_report(report, out_md=args.out_md, out_json=args.out_json)
    print(f"[stress_lab] wrote {out_md}")
    print(f"[stress_lab] wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
