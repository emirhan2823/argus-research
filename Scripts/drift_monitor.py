#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.year2_generate_metrics import compute_metrics


def _drift_grade(drift_bps: float | None) -> tuple[str, str]:
    if drift_bps is None:
        return "UNKNOWN", "No overlapping expected vs realized samples."
    abs_v = abs(float(drift_bps))
    if abs_v <= 10.0:
        return "GREEN", f"Drift is healthy ({drift_bps:.2f} bps)."
    if abs_v <= 25.0:
        return "YELLOW", f"Drift is elevated ({drift_bps:.2f} bps); monitor execution quality."
    return "RED", f"Drift is high ({drift_bps:.2f} bps); investigate signal/execution mismatch."


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute decision-vs-execution drift report")
    parser.add_argument("--run-dir", "--run_dir", dest="run_dir", type=Path, required=True)
    parser.add_argument(
        "--out-md",
        "--out_md",
        dest="out_md",
        type=Path,
        default=Path("reports/year2/drift_monitor.md"),
    )
    parser.add_argument(
        "--out-json",
        "--out_json",
        dest="out_json",
        type=Path,
        default=Path("reports/year2/drift_monitor.json"),
    )
    args = parser.parse_args()

    metrics = compute_metrics(args.run_dir)
    drift_bps = metrics.get("drift_bps_median")
    grade, interpretation = _drift_grade(drift_bps if drift_bps is None else float(drift_bps))

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(args.run_dir),
        "drift_bps_median": drift_bps,
        "slippage_bps_median": metrics.get("slippage_bps_median"),
        "slippage_bps_p95": metrics.get("slippage_bps_p95"),
        "expectancy": metrics.get("expectancy"),
        "max_dd_pct": metrics.get("max_dd_pct"),
        "grade": grade,
        "interpretation": interpretation,
    }

    lines = [
        "# Drift Monitor",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Run Dir: `{args.run_dir}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Drift Median (bps) | {drift_bps if drift_bps is not None else 'N/A'} |",
        f"| Slippage Median (bps) | {metrics.get('slippage_bps_median', 'N/A')} |",
        f"| Slippage P95 (bps) | {metrics.get('slippage_bps_p95', 'N/A')} |",
        f"| Expectancy | {float(metrics.get('expectancy', 0.0)):.6f} |",
        f"| MaxDD% | {float(metrics.get('max_dd_pct', 0.0)):.4f} |",
        "",
        f"## Grade: **{grade}**",
        "",
        f"- {interpretation}",
    ]

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"[drift_monitor] wrote {args.out_md}")
    print(f"[drift_monitor] wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
