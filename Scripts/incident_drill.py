#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ops.incident_manager import IncidentManager, IncidentSeverity


def main() -> int:
    parser = argparse.ArgumentParser(description="Run incident drill for ops readiness")
    parser.add_argument(
        "--incident-dir",
        "--incident_dir",
        dest="incident_dir",
        type=Path,
        default=Path("reports/year2/incidents"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/year2/incidents/incident_drill.md"),
    )
    args = parser.parse_args()

    manager = IncidentManager(args.incident_dir)
    incident = manager.open_incident(
        title="Nightly drill: telemetry degradation simulation",
        severity=IncidentSeverity.WARN,
        context={"drill": True, "started_at_utc": datetime.now(timezone.utc).isoformat()},
        recovery_checklist=["heartbeat_ok", "metrics_ok", "alerts_ok"],
    )
    manager.append_event(incident.incident_id, "Simulated telemetry outage", {"simulated": True})
    manager.append_event(incident.incident_id, "Applied fallback profile STRICT", {"profile": "STRICT"})
    # Exercise failed then successful checklist path.
    manager.enforce_recovery(incident.incident_id, {"heartbeat_ok": True, "metrics_ok": False, "alerts_ok": True})
    resolved = manager.resolve(
        incident.incident_id,
        "Drill completed, fallback and recovery path validated.",
        checklist_state={"heartbeat_ok": True, "metrics_ok": True, "alerts_ok": True},
    )

    lines = [
        "# Incident Drill",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Incident ID: `{resolved.incident_id}`",
        f"Incident JSON: `{args.incident_dir / (resolved.incident_id + '.json')}`",
        f"Incident Markdown: `{args.incident_dir / (resolved.incident_id + '.md')}`",
        "",
        "## Checklist",
        "",
        "- heartbeat_ok",
        "- metrics_ok",
        "- alerts_ok",
        "",
        "## Result",
        "",
        "- Drill completed successfully.",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[incident_drill] wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
