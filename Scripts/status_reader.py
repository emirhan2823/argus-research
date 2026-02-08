#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


def heartbeat_age_seconds(ts_iso: str | None) -> float | None:
    if not ts_iso:
        return None
    try:
        ts = datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
        return (now - ts).total_seconds()
    except Exception:
        return None


def build_status(run_dir: Path) -> Dict[str, Any]:
    hb = load_json(run_dir / "heartbeat.json")
    state = load_json(run_dir / "daemon_state.json")
    metrics = load_json(run_dir / "metrics.json")

    status = {
        "run_dir": str(run_dir),
        "heartbeat": {
            "ts_iso": hb.get("ts_iso"),
            "age_sec": heartbeat_age_seconds(hb.get("ts_iso")),
            "risk_level": hb.get("risk_level"),
            "counters": hb.get("counters", {}),
            "health": hb.get("health", {}),
        },
        "metrics": metrics,
        "state": {
            "timestamp_iso": state.get("timestamp_iso"),
            "balance": state.get("balance"),
            "equity": state.get("equity"),
            "reason": state.get("reason"),
            "strategy": state.get("config_snapshot", {}).get("strategy"),
        },
        "files": {
            "decisions_rows": count_rows(run_dir / "decisions.csv"),
            "trades_rows": count_rows(run_dir / "trades.csv"),
            "rejects_rows": count_rows(run_dir / "rejects.csv"),
        },
    }
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Read run_dir status and print JSON summary")
    parser.add_argument("--run-dir", type=Path, default=Path("runs/year2/paper_main"))
    parser.add_argument("--compact", action="store_true", help="Compact JSON")
    args = parser.parse_args()

    payload = build_status(args.run_dir)
    if args.compact:
        print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
