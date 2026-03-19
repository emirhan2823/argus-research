#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate incident report template")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/year2/incidents/incident_report_template.md"),
    )
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = f"""# Incident Report Template

Generated: {now}

## 1. Incident Summary

- Incident ID:
- Severity:
- Detected At (UTC):
- Resolved At (UTC):
- Trigger Source (alert/manual):

## 2. Impact

- Affected strategy/profile:
- Trading impact (paper):
- Telemetry impact:

## 3. Timeline

- T0:
- T+5m:
- T+15m:
- T+30m:

## 4. Root Cause Analysis

- Primary cause:
- Contributing factors:
- Why not detected earlier:

## 5. Immediate Actions

- [ ] Kill-switch check
- [ ] Daemon health reset
- [ ] Telemetry continuity validation
- [ ] Report regeneration

## 6. Preventive Actions

- [ ] Test coverage added
- [ ] Alert rule adjusted
- [ ] Runbook updated
- [ ] Monitoring panel updated

## 7. Approval

- Owner:
- Reviewer:
- Date:
"""
    args.out.write_text(content, encoding="utf-8")
    print(f"[incident_template] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
