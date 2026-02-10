#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def sqlite_count(path: Path, table: str) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MODE=v2 integration artifacts")
    parser.add_argument("--run-dir", type=Path, default=Path("runs/year2/paper_main"))
    parser.add_argument("--report", type=Path, default=Path("reports/year2/integration_validation.md"))
    parser.add_argument("--nightly-metrics", type=Path, default=None)
    args = parser.parse_args()

    run_dir = args.run_dir
    metrics = load_json(run_dir / "metrics.json")
    heartbeat = load_json(run_dir / "heartbeat.json")
    nightly_path = args.nightly_metrics or (args.report.parent / "metrics.json")
    nightly = load_json(Path(nightly_path))

    mode = str(metrics.get("mode", "unknown"))
    v2_payload = metrics.get("v2", {}) if isinstance(metrics.get("v2"), dict) else {}

    events_path = run_dir / "events_v2.jsonl"
    warehouse_db = run_dir / "warehouse" / "cold" / "metrics.sqlite3"

    checks = {
        "mode_is_v2": mode == "v2",
        "heartbeat_exists": bool(heartbeat),
        "metrics_exists": bool(metrics),
        "events_v2_exists": events_path.exists(),
        "events_v2_nonempty": count_jsonl(events_path) > 0,
        "warehouse_db_exists": warehouse_db.exists(),
        "warehouse_has_rows": sqlite_count(warehouse_db, "metrics") > 0,
    }

    lines = [
        "# Sprint A Integration Validation",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Run Dir: `{run_dir}`",
        "",
        "## Validation Checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ]

    for key, passed in checks.items():
        lines.append(f"| `{key}` | {'PASS' if passed else 'FAIL'} |")

    lines.extend(
        [
            "",
            "## Runtime Snapshot",
            "",
            f"- Mode: `{mode}`",
            f"- Bars Seen: {metrics.get('bars_seen')}",
            f"- Decisions Total: {metrics.get('decisions_total')}",
            f"- Trades Total: {metrics.get('trades_total')}",
            f"- Rejects Total: {metrics.get('rejects_total')}",
            f"- V2 Regime: {v2_payload.get('regime_v2')}",
            f"- V2 Legacy Regime: {v2_payload.get('regime_legacy')}",
            f"- V2 Event Types: {len(v2_payload.get('event_counts', {})) if isinstance(v2_payload.get('event_counts', {}), dict) else 0}",
            "",
            "## How To Run",
            "",
            "```bash",
            "venv/bin/python Scripts/paper_daemon.py --mode v2 --strategy council --run_dir runs/year2/paper_main --interval 1m",
            "venv/bin/python Scripts/nightly_eval.py --mode v2 --run-dir runs/year2/paper_main --reports-dir reports/year2",
            "venv/bin/python Scripts/integration_validate.py --run-dir runs/year2/paper_main --report reports/year2/integration_validation.md",
            "```",
        ]
    )

    if nightly:
        lines.extend(
            [
                "",
                "## Nightly Pipeline",
                "",
                f"- Nightly mode: {nightly.get('mode')}",
                f"- 24h trades: {nightly.get('window_24h', {}).get('trades')}",
                f"- 7d trades: {nightly.get('window_7d', {}).get('trades')}",
            ]
        )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[integration_validate] wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
