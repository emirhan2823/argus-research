# Year-2 Autopilot Runbook

## 1) Purpose

This runbook defines how to operate Argus Autopilot in paper-first mode with explicit fallback behavior.

## 2) Start / Stop

### Start all profiles (`STRICT`, `SOFT`, `TOPHUNTER`)

```bash
Scripts/phase19ctl.sh twin-start
```

### Start selected profiles only

```bash
Scripts/phase19ctl.sh twin-start STRICT,SOFT
```

### Status

```bash
Scripts/phase19ctl.sh twin-status
```

### Stop

```bash
Scripts/phase19ctl.sh twin-stop
```

## 2.1 Paper Soak Core Infra

Core scripts (DO NOT DELETE):

- `Scripts/soak_start.sh`
- `Scripts/soak_status.sh`
- `Scripts/soak_stop.sh`
- `Scripts/soak_smoke.sh`

Start:

```bash
Scripts/soak_start.sh council
```

Status:

```bash
Scripts/soak_status.sh
```

Stop:

```bash
Scripts/soak_stop.sh
```

Smoke:

```bash
Scripts/soak_smoke.sh council
```

## 3) Night Autopilot Batch

```bash
venv/bin/python Scripts/year2_autopilot.py \
  --run-dir runs/overnight_paper_live \
  --data-dir data/BTCUSDT/1h \
  --reports-dir reports/year2
```

Expected outputs:

- `reports/year2/weekly_review.md`
- `reports/year2/tophunter_tuning.md`
- `reports/year2/strategy_governance.md`
- `reports/year2/micro_live_ready.md`
- `reports/year2/night_cycle.md`
- `reports/year2/nightly/YYYYMMDD/metrics.json`

Additional nightly evaluation:

```bash
venv/bin/python Scripts/nightly_eval.py \
  --run-dir runs/year2/paper_main \
  --reports-dir reports/year2
```

Gate re-check:

```bash
venv/bin/python Scripts/gate_recheck.py \
  --run-dir runs/year2/paper_main \
  --reports-dir reports/year2
```

TopHunter paper-only sweep:

```bash
venv/bin/python Scripts/tophunter_sweep.py \
  --data-dir data/BTCUSDT/1h \
  --days 30 \
  --out reports/year2/tophunter_tuning.md
```

Strategy registry + auto-disable decision:

```bash
venv/bin/python Scripts/strategy_registry.py \
  --run-dir runs/year2/paper_main \
  --registry runs/year2/governance/strategy_registry.json \
  --report reports/year2/strategy_governance.md
```

Incident template generation:

```bash
venv/bin/python Scripts/generate_incident_template.py
```

## 4) Fallback Rules

- If one profile exceeds restart budget (`MAX_RESTARTS_PER_HOUR`), keep other profiles alive and mark degraded mode in `logs/phase19_agent/supervisor.log`.
- If heartbeat is stale (`>180s`) for one profile, restart only that profile; do not stop healthy profiles.
- If `TOPHUNTER` becomes unstable, continue with `STRICT+SOFT` and generate blocker notes in `reports/year2/micro_live_ready.md`.
- If kill-switch enters `HARD` or `HALT`, no new entries; close/open actions follow kill-switch policy.

## 5) Promotion Policy

- Default operation is paper-only.
- Promotion to micro-live is allowed only when `reports/year2/micro_live_ready.md` gate is `PASS`.
- If gate is `FAIL`, fix listed blockers and rerun nightly cycle.

## 6) Optional Service Mode (macOS launchd)

Install service:

```bash
Scripts/soak_service.sh install council
```

Service status:

```bash
Scripts/soak_service.sh status
```

Service stop:

```bash
Scripts/soak_service.sh stop
```

Service logs:

```bash
Scripts/soak_service.sh logs
```

## 7) Windows 7/24 Node

Prepare:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_prepare.ps1
```

Start paper soak:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_start.ps1 -Strategy council -RunDir runs/year2/paper_main
```

Status:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_status.ps1 -RunDir runs/year2/paper_main
```

Stop:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_stop.ps1 -RunDir runs/year2/paper_main
```

Dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_dashboard_start.ps1 -RunDir runs/year2/paper_main -Host 127.0.0.1 -Port 18081
powershell -ExecutionPolicy Bypass -File Scripts\win_dashboard_status.ps1 -RunDir runs/year2/paper_main
powershell -ExecutionPolicy Bypass -File Scripts\win_dashboard_stop.ps1 -RunDir runs/year2/paper_main
```

Task Scheduler (boot + logon):

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_task.ps1 -Action install -Strategy council -RunDir runs/year2/paper_main
powershell -ExecutionPolicy Bypass -File Scripts\win_soak_task.ps1 -Action status
```
