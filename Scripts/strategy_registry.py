#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.year2_generate_metrics import compute_metrics

HARD_RISK_CODES = {"KILL_SWITCH_DD", "REJECT_KILL_SWITCH", "HARD_STOP", "DAILY_STOP"}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_reject_codes(path: Path) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if not path.exists():
        return out
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = str(row.get("code") or row.get("reason") or "").strip()
            if not code:
                continue
            out[code] = out.get(code, 0) + 1
    return out


def evaluate_disable_criteria(metrics: Dict[str, Any], reject_codes: Dict[str, int]) -> List[str]:
    reasons: List[str] = []

    error_rate = float(metrics.get("error_rate_pct", 0.0))
    telemetry_stale = metrics.get("telemetry_stale_seconds")
    violations = int(metrics.get("risk_violations", 0))

    if error_rate >= 5.0:
        reasons.append(f"errors_spike(error_rate={error_rate:.3f}%)")

    if telemetry_stale is None or float(telemetry_stale) > 600.0:
        reasons.append(f"severe_telemetry_failure(stale_sec={telemetry_stale})")

    hard_hits = sum(reject_codes.get(code, 0) for code in HARD_RISK_CODES)
    if violations > 0 or hard_hits > 0:
        reasons.append(f"hard_risk_rule_violated(violations={violations}, hard_hits={hard_hits})")

    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Update strategy registry and apply strict auto-disable rules")
    parser.add_argument("--run-dir", type=Path, default=Path("runs/year2/paper_main"))
    parser.add_argument("--registry", type=Path, default=Path("runs/year2/governance/strategy_registry.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/year2/strategy_governance.md"))
    args = parser.parse_args()

    metrics = compute_metrics(args.run_dir)
    strategy_id = str(metrics.get("strategy_id", "COUNCIL_BASELINE"))
    reject_codes = read_reject_codes(args.run_dir / "rejects.csv")
    disable_reasons = evaluate_disable_criteria(metrics, reject_codes)

    registry = load_json(args.registry)
    if "strategies" not in registry or not isinstance(registry["strategies"], dict):
        registry["strategies"] = {}

    entry = registry["strategies"].get(strategy_id, {
        "enabled": True,
        "disable_reason": None,
        "last_performance": {},
        "updated_at_utc": None,
    })

    entry["last_performance"] = {
        "expectancy": metrics.get("expectancy"),
        "win_rate": metrics.get("win_rate"),
        "max_dd_pct": metrics.get("max_dd_pct"),
        "error_rate_pct": metrics.get("error_rate_pct"),
        "telemetry_stale_seconds": metrics.get("telemetry_stale_seconds"),
        "trades_closed": metrics.get("trades_closed"),
    }

    auto_disabled = False
    if disable_reasons:
        if entry.get("enabled", True):
            auto_disabled = True
        entry["enabled"] = False
        entry["disable_reason"] = "; ".join(disable_reasons)
    else:
        entry.setdefault("enabled", True)
        if entry.get("enabled", True):
            entry["disable_reason"] = None

    entry["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    registry["strategies"][strategy_id] = entry
    registry["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    args.registry.parent.mkdir(parents=True, exist_ok=True)
    args.registry.write_text(json.dumps(registry, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# Strategy Governance",
        "",
        f"Generated: {registry['generated_at_utc']}",
        f"Run Dir: `{args.run_dir}`",
        "",
        "| Strategy | Enabled | Disable Reason | Expectancy | WinRate | MaxDD% | ErrorRate% |",
        "|---|---|---|---:|---:|---:|---:|",
        (
            f"| `{strategy_id}` | {entry.get('enabled')} | "
            f"{entry.get('disable_reason') or '-'} | "
            f"{float(metrics.get('expectancy', 0.0)):.4f} | "
            f"{float(metrics.get('win_rate', 0.0))*100.0:.2f}% | "
            f"{float(metrics.get('max_dd_pct', 0.0)):.2f} | "
            f"{float(metrics.get('error_rate_pct', 0.0)):.3f} |"
        ),
        "",
        "## Auto-Disable Criteria",
        "",
        "- errors_spike",
        "- severe_telemetry_failure",
        "- hard_risk_rule_violated",
        "",
        "## Decision",
        "",
    ]

    if auto_disabled:
        lines.append(f"- AUTO-DISABLED `{strategy_id}` due to: {entry.get('disable_reason')}")
    elif disable_reasons:
        lines.append(f"- Strategy remains disabled: {entry.get('disable_reason')}")
    else:
        lines.append("- No auto-disable triggered.")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[strategy_registry] wrote {args.registry}")
    print(f"[strategy_registry] wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
