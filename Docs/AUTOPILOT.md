# ARGUS AUTOPILOT MODE

## Daily Loop
1. Refresh run telemetry (`decisions.csv`, `trades.csv`, `rejects.csv`, `heartbeat.json`).
2. Generate metrics pack via `Scripts/year2_generate_metrics.py`.
3. Generate weekly + gate + governance reports via `Scripts/year2_autopilot.py`.
4. Apply governance decisions (disable negative expectancy strategies).
5. Keep paper mode unless gate says `PASS`.

## Research Loop
1. Select active strategy profile (`STRICT`, `SOFT`, `TOPHUNTER`).
2. Run parameter sweep on last 30-day paper bars.
3. Stress test under fee/slippage and latency shocks.
4. Produce next-day action plan.

## Night Mode
- Run `Scripts/year2_autopilot.py`.
- Refresh `reports/year2/nightly/YYYYMMDD/metrics.json`.
- Update:
  - `reports/year2/weekly_review.md`
  - `reports/year2/tophunter_tuning.md`
  - `reports/year2/strategy_governance.md`
  - `reports/year2/micro_live_ready.md`
  - `reports/year2/night_cycle.md`

## Safety Rules
- NEVER trade live by default.
- Paper only until gate pass.
- Keep risk caps unchanged unless a written report justifies change.
- Stop and investigate on anomalies.

## Reporting
- Core outputs in `reports/year2/`.
- Runbook: `Docs/YEAR2_AUTOPILOT_RUNBOOK.md`.
