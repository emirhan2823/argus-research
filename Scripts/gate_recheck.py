#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.year2_generate_metrics import compute_metrics


def evaluate_gate(metrics: Dict[str, Any]) -> Tuple[bool, List[Tuple[str, bool, str]]]:
    checks: List[Tuple[str, bool, str]] = []

    trades = int(metrics.get("trades_closed", 0))
    expectancy = float(metrics.get("expectancy", 0.0))
    max_dd = float(metrics.get("max_dd_pct", 0.0))
    error_rate = float(metrics.get("error_rate_pct", 0.0))
    telemetry_stable = bool(metrics.get("telemetry_stable", False))
    violations = int(metrics.get("risk_violations", 0))

    checks.append(("trades>=100", trades >= 100, f"trades={trades}"))
    checks.append(("expectancy>0", expectancy > 0.0, f"expectancy={expectancy:.4f}"))
    checks.append(("maxDD<=6%", max_dd <= 6.0, f"maxDD={max_dd:.2f}%"))
    checks.append(("error_rate<=0.20%", error_rate <= 0.20, f"error_rate={error_rate:.3f}%"))
    checks.append(("telemetry_stable", telemetry_stable, f"telemetry_stable={telemetry_stable}"))
    checks.append(("no_risk_violations", violations == 0, f"violations={violations}"))

    passed = all(item[1] for item in checks)
    return passed, checks


def write_markdown(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate re-evaluation from run_dir telemetry")
    parser.add_argument("--run-dir", type=Path, default=Path("runs/year2/paper_main"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/year2"))
    args = parser.parse_args()

    metrics = compute_metrics(args.run_dir)
    passed, checks = evaluate_gate(metrics)

    lines = [
        "# Gate Re-check",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Run Dir: `{args.run_dir}`",
        f"Result: **{'PASS' if passed else 'FAIL'}**",
        "",
        "| Check | Result | Details |",
        "|---|---|---|",
    ]

    for name, ok, detail in checks:
        lines.append(f"| `{name}` | {'PASS' if ok else 'FAIL'} | {detail} |")

    if passed:
        lines.extend(["", "## Decision", "", "- Gate passed. Continue with micro-live preparation (still paper-only until explicit promotion)."])
    else:
        lines.extend(["", "## Blockers", ""])
        for name, ok, detail in checks:
            if not ok:
                lines.append(f"- `{name}` failed ({detail})")

    report_path = args.reports_dir / "gate_recheck.md"
    write_markdown(report_path, lines)

    print(f"[gate_recheck] wrote {report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
