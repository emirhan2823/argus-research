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

## 4) Fallback Rules

- If one profile exceeds restart budget (`MAX_RESTARTS_PER_HOUR`), keep other profiles alive and mark degraded mode in `logs/phase19_agent/supervisor.log`.
- If heartbeat is stale (`>180s`) for one profile, restart only that profile; do not stop healthy profiles.
- If `TOPHUNTER` becomes unstable, continue with `STRICT+SOFT` and generate blocker notes in `reports/year2/micro_live_ready.md`.
- If kill-switch enters `HARD` or `HALT`, no new entries; close/open actions follow kill-switch policy.

## 5) Promotion Policy

- Default operation is paper-only.
- Promotion to micro-live is allowed only when `reports/year2/micro_live_ready.md` gate is `PASS`.
- If gate is `FAIL`, fix listed blockers and rerun nightly cycle.
