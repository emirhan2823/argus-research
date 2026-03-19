# Sprint A Integration Validation

Generated: 2026-02-10T04:14:48.992761+00:00
Run Dir: `runs/year2/sprint_a_validation`

## Validation Checks

| Check | Result |
|---|---|
| `mode_is_v2` | PASS |
| `heartbeat_exists` | PASS |
| `metrics_exists` | PASS |
| `events_v2_exists` | PASS |
| `events_v2_nonempty` | PASS |
| `warehouse_db_exists` | PASS |
| `warehouse_has_rows` | PASS |

## Runtime Snapshot

- Mode: `v2`
- Bars Seen: 1
- Decisions Total: 1
- Trades Total: 1
- Rejects Total: 1
- V2 Regime: LOW_VOL_CALM
- V2 Legacy Regime: RANGE
- V2 Event Types: 6

## How To Run

```bash
venv/bin/python Scripts/paper_daemon.py --mode v2 --strategy council --run_dir runs/year2/paper_main --interval 1m
venv/bin/python Scripts/nightly_eval.py --mode v2 --run-dir runs/year2/paper_main --reports-dir reports/year2
venv/bin/python Scripts/integration_validate.py --run-dir runs/year2/paper_main --report reports/year2/integration_validation.md
```

## Nightly Pipeline

- Nightly mode: v2
- 24h trades: 0
- 7d trades: 0
