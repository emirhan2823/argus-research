# Incident Drill Checklist (Paper-Only)

## Goal

Validate operational readiness under paper trading incidents without changing risk caps.

## Preconditions

- [ ] Running in PAPER mode only
- [ ] `Scripts/soak_start.sh` + `Scripts/soak_status.sh` operational
- [ ] Current run directory known (`runs/year2/paper_main`)
- [ ] Alerts channel reachable

## Drill Steps

1. Detection
- [ ] Simulate anomaly (stale heartbeat / error spike)
- [ ] Confirm alert fired
- [ ] Record detection timestamp

2. Triage
- [ ] Check `Scripts/soak_status.sh`
- [ ] Check `Scripts/status_reader.py --run-dir ...`
- [ ] Identify affected strategy/profile

3. Containment
- [ ] Confirm kill-switch level
- [ ] Stop daemon if required (`Scripts/soak_stop.sh`)
- [ ] Preserve logs and telemetry files

4. Recovery
- [ ] Restart with same risk caps (`Scripts/soak_start.sh`)
- [ ] Confirm heartbeat + metrics recovery
- [ ] Re-run nightly eval (`Scripts/nightly_eval.py`)

5. Postmortem
- [ ] Generate incident template (`Scripts/generate_incident_template.py`)
- [ ] Fill root cause and actions
- [ ] Add follow-up tasks

## Exit Criteria

- [ ] System stable for >= 30 min
- [ ] No unresolved critical alerts
- [ ] Incident report created under `reports/year2/incidents/`
