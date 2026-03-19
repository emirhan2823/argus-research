# ARGUS Year-2 Technical Plan

**Plan Window:** 12 months (M01..M12)  
**Suggested Calendar:** 2026-03 to 2027-02  
**Primary Objective:** **Profitability via stability first** (drawdown control and operational reliability before aggressive scaling).

## 1. Year-2 Mission and Operating Principles

1. Stability first: protect capital and keep system online before return optimization.
2. Gate-driven progression: no stage upgrade without hard pass metrics.
3. Realism-first backtests: cost/latency assumptions must be continuously calibrated against paper/micro-live observations.
4. Reproducible operations: every nightly cycle must emit auditable artifacts under deterministic folder conventions.

## 2. Baseline Inputs and Current Execution Surface

This plan is grounded in:

- `Docs/ARGUS_YEAR1_TECHNICAL_MASTERPLAN.md`
- `Docs/FUTURE_VISION.md`
- Existing runners and modules:
  - `Scripts/paper_daemon.py`
  - `Scripts/dashboard.py`
  - `Scripts/phase19ctl.sh`
  - `Scripts/sprint1_walkforward_12m.py`
  - `Scripts/verify_determinism.py`
  - `Scripts/weekly_audit.py`
  - `Scripts/phase20_signal_audit.py`
  - `Scripts/train_ml_model.py`
  - `Scripts/generate_tax_report.py`
  - `argus_py/risk/kill_switch.py`
  - `argus_py/alerts/*`
  - `argus_py/dashboard/app.py`

## 2.1 Run Dir Migration Note (Year-1 -> Year-2)

Primary runtime path is migrated from:

- Old: `runs/overnight_paper_live`
- New: `runs/year2/paper_main`

Short migration runbook:

```bash
mkdir -p runs/year2/paper_main
rsync -av \
  --exclude '*.pid' \
  --exclude '*.out' \
  --exclude 'daemon_state.json.tmp' \
  --exclude 'heartbeat.json.tmp' \
  runs/overnight_paper_live/ runs/year2/paper_main/
```

Policy:

- Keep `runs/overnight_paper_live` as immutable archive.
- All Year-2 gates and nightly jobs must read/write `runs/year2/*`.
- Note: current `argus_py.runner.live_cli` writes to `runs/live` by default; mirror snapshots to `runs/year2/micro_live_main` for gate reporting.

## 3. Quarter Objectives

| Quarter | Months | Theme | Exit Condition |
|---|---|---|---|
| Q1 | M01-M03 | Paper reliability and gate instrumentation | Paper->Micro-live gate is green |
| Q2 | M04-M06 | Micro-live validation and drift reduction | Micro-live->Live gate is green |
| Q3 | M07-M09 | Live low-risk operation and hardening | 90-day live stability targets met |
| Q4 | M10-M12 | Cross-asset expansion and institutional reporting | Year-2 DoD checklist fully complete |

## 4. 12-Month Milestones (Monthly)

| Month | Focus | Implementation Milestone | Commands (Operational) | Deliverables (Files/Folders) |
|---|---|---|---|---|
| M01 | Baseline freeze | Freeze baseline config set for SOFT paper daemon and telemetry contracts; define nightly metrics generator entrypoint. | `venv/bin/python Scripts/paper_daemon.py --daemon_id SOFT --run_dir runs/year2/paper_main --min_adx 20 --max_exp_move_bps 120 --max_risk_trade_pct 1.0 --daily_loss_limit_pct 3.0 --kill_switch_dd_pct 8.0 --safe_paper` | `runs/year2/paper_main/heartbeat.json`, `runs/year2/paper_main/daemon_state.json`, `runs/year2/paper_main/decisions.csv`, `Scripts/year2_generate_metrics.py` |
| M02 | Paper soak | Run uninterrupted paper soak and enforce stale-heartbeat and reject-code hygiene. | `venv/bin/python Scripts/dashboard.py runs/year2/paper_main --host 127.0.0.1 --port 18081` | `reports/year2/m02_paper_soak.md`, `runs/year2/paper_main/rejects.csv` |
| M03 | Paper gate | Run full paper gate audit pack and gate decision review. | `venv/bin/python Scripts/weekly_audit.py runs/year2/paper_main --week 2026-W18` | `reports/year2/gates/paper_to_micro_live_gate.json`, `reports/year2/gates/paper_to_micro_live_gate.md` |
| M04 | Micro-live phase-1 | Start micro-live with strict notional caps and mandatory cooldown using the real runner entrypoint in dry-run mode; mirror run artifacts to Year-2 namespace. | `venv/bin/python -m argus_py.runner.live_cli --exchange bingx --symbol BTCUSDT --tf 15m --mode dry_run --profile AUTO --poll_seconds 30 --max_daily_loss_pct 0.02 --max_dd_pct 0.05 --max_consecutive_losses 3` then `rsync -av runs/live/ runs/year2/micro_live_main/` | `runs/live/*` (runner output), `runs/year2/micro_live_main/*` (gate snapshot), `reports/year2/m04_micro_live_start.md` |
| M05 | Drift control | Measure paper-vs-micro-live drift and tighten execution assumptions. | `venv/bin/python Scripts/phase20_signal_audit.py runs/year2/micro_live_main --output reports/year2/m05_signal_audit.md` | `reports/year2/m05_signal_audit.md`, `reports/year2/m05_drift_metrics.json` |
| M06 | Micro-live gate | Gate check for moving into live low-risk mode. | `venv/bin/python Scripts/weekly_audit.py runs/year2/micro_live_main --week 2026-W31 --json` | `reports/year2/gates/micro_live_to_live_gate.json`, `reports/year2/gates/micro_live_to_live_gate.md` |
| M07 | Live phase-1 | Enable live at reduced risk profile and single-symbol exposure cap. | `venv/bin/python Scripts/run_telegram_bot.py --help` | `runs/year2/live_main/*`, `reports/year2/m07_live_launch.md` |
| M08 | Live phase-2 | Add second symbol only after first live month stability check. | `venv/bin/python Scripts/verify_determinism.py --runs 2 --seed 42` | `reports/year2/m08_live_multisymbol.md`, `reports/year2/m08_determinism.txt` |
| M09 | Cost model hardening | Re-calibrate fee/slippage/latency using live fills and backtest deltas. | `venv/bin/python Scripts/phase20_signal_audit.py runs/year2/live_main --json` | `reports/year2/m09_cost_model.json`, `reports/year2/m09_cost_model.md` |
| M10 | Cross-asset prep | Introduce equity/commodity adapters in paper-only with isolated run dirs. | `venv/bin/python Scripts/sprint2_make_external_signal_template.py --output runs/year2/templates/external_signals.csv` | `runs/year2/paper_equities/*`, `runs/year2/paper_commodities/*`, `runs/year2/templates/external_signals.csv` |
| M11 | Portfolio and risk unification | Unify portfolio limits across crypto/equity/commodity paper streams. | `venv/bin/python Scripts/weekly_audit.py runs/year2/paper_equities --week 2027-W03` | `reports/year2/m11_portfolio_unification.md`, `reports/year2/m11_risk_matrix.csv` |
| M12 | Year-end validation | Produce annual technical pack and readiness recommendation for Year-3. | `venv/bin/python Scripts/generate_tax_report.py runs/year2/live_main/trades.csv --year 2026 --output reports/year2/tax_report_2026.csv --statement-json reports/year2/tax_report_2026_summary.json` | `reports/year2/year_end_summary.md`, `reports/year2/tax_report_2026.csv`, `reports/year2/year2_retrospective.json` |

### 4.1 Operational Milestone: Kill-switch / Incident Drill

| Month | Drill | Command Set | Required Deliverables |
|---|---|---|---|
| M05 | Kill-switch and incident response drill (tabletop + simulated trigger) | `venv/bin/python Scripts/telegram_local_command_test.py --run-dir runs/year2/paper_main --user-id 1` then `venv/bin/python Scripts/weekly_audit.py runs/year2/paper_main --week 2026-W22 --json > reports/year2/incidents/2026-05-killswitch-drill.json` | `reports/year2/incidents/2026-05-killswitch-drill.md`, `reports/year2/incidents/2026-05-killswitch-drill.json`, `reports/year2/incidents/2026-05-killswitch-drill_actions.md` |

## 5. Stage Gates (Paper -> Micro-live -> Live)

### 5.1 Gate A: Paper -> Micro-live

| Metric | Pass Threshold | Fail Condition | Measurement Source |
|---|---|---|---|
| Max Drawdown (DD) | `<= 6.0%` over rolling 30 days | `> 6.0%` | `heartbeat.json`, `weekly_audit.py` output |
| Uptime | `>= 99.0%` daemon uptime | `< 99.0%` | `status.log`, heartbeat freshness |
| Slippage | median `<= 6 bps`, p95 `<= 12 bps` | above either threshold | `trades.csv` + audit artifacts |
| Error Rate | `<= 0.20%` per processed bar | `> 0.20%` | `rejects.csv`, `errors.log`, health counters |
| Number of Trades | `>= 200` valid paper trades | `< 200` | `trades.csv` |
| Drift (expected vs realized) | `<= 10 bps` median drift | `> 10 bps` | `phase20_signal_audit.py` + custom drift report |
| Twin Divergence (STRICT vs SOFT) | decision divergence `<= 20%` and equity curve spread `<= 2.0%` over same window | above either threshold | twin runs (`runs/phase19_twin/STRICT`, `runs/phase19_twin/SOFT`) + `Scripts/phase19_dashboard.py` / counterfactual report |

**Promotion Rule:** all metrics must pass for 2 consecutive weekly reviews.

### 5.2 Gate B: Micro-live -> Live

| Metric | Pass Threshold | Fail Condition | Measurement Source |
|---|---|---|---|
| Max Drawdown (DD) | `<= 4.0%` over rolling 45 days | `> 4.0%` | broker equity series + `weekly_audit.py` |
| Uptime | `>= 99.5%` | `< 99.5%` | daemon process monitor + heartbeat age |
| Slippage Delta vs model | median `<= +4 bps`, p95 `<= +10 bps` | above either threshold | modeled vs live fills report |
| Error Rate | `<= 0.10%` critical errors per bar | `> 0.10%` | rejects/errors with severity split |
| Number of Trades | `>= 100` micro-live fills | `< 100` | micro-live `trades.csv` |
| Drift (paper vs micro-live) | decision/fill drift `<= 15%` relative | `> 15%` | paired-run drift report |

**Promotion Rule:** all metrics pass, and kill-switch never stays in `HARD/HALT` for > 1 cycle.

### 5.3 Gate C: Live Scale-up (Live Stage-1 -> Stage-2)

| Metric | Pass Threshold | Fail Condition | Measurement Source |
|---|---|---|---|
| 90-day Max DD | `<= 5.0%` | `> 5.0%` | live equity curve |
| Runtime Stability | `>= 99.7%` | `< 99.7%` | heartbeat + supervisor logs |
| Slippage Stability | p95 `<= 12 bps` | `> 12 bps` | fills vs model |
| Incident Rate | `0` unresolved critical incidents | `>= 1` unresolved | incident log |
| Trade Throughput | `>= 250` fills / 90 days | `< 250` | `trades.csv` |
| Drift Stability | monthly drift trend non-increasing | increasing trend 2 months | monthly drift pack |

## 6. Night Autopilot (Mandatory Nightly Batch)

Night batch should run daily after market close window (example: 01:00 local time) and write artifacts into date-partitioned directories.

### 6.1 Nightly Run Command Set

```bash
# 1) Determinism check
venv/bin/python Scripts/verify_determinism.py --runs 2 --seed 42

# 1.1) Nightly metrics pack (new Year-2 pipeline)
venv/bin/python Scripts/year2_generate_metrics.py \
  --run-dir runs/year2/paper_main \
  --out reports/year2/nightly/$(date +%Y%m%d)/metrics.json

# 2) Walk-forward baseline refresh
venv/bin/python Scripts/sprint1_walkforward_12m.py \
  --data_path data \
  --output_dir runs/year2/nightly/$(date +%Y%m%d)/walkforward \
  --symbol BTCUSDT \
  --start_date 2025-01-01 \
  --end_date 2026-01-01 \
  --train_months 3 --test_months 1 --step_months 1 --skip_invalid

# 3) Weekly audit snapshot (if week boundary reached)
venv/bin/python Scripts/weekly_audit.py runs/year2/paper_main --week $(date +%G-W%V) --json \
  > reports/year2/nightly/$(date +%Y%m%d)/weekly_audit.json

# 4) Signal audit
venv/bin/python Scripts/phase20_signal_audit.py runs/year2/paper_main \
  --output reports/year2/nightly/$(date +%Y%m%d)/signal_audit.md

# 5) ML refresh
venv/bin/python Scripts/train_ml_model.py \
  --input runs/training_data.csv \
  --output models/signal_model.lgb
```

### 6.2 Required Nightly Artifacts

| Artifact Type | Required Path Pattern | Minimum Content |
|---|---|---|
| Metrics JSON | `reports/year2/nightly/YYYYMMDD/metrics.json` | DD, win rate, expectancy, slippage median/p95, drift |
| Audit Report | `reports/year2/nightly/YYYYMMDD/signal_audit.md` | reject summary, gate blockers, drift notes |
| Walk-forward Output | `runs/year2/nightly/YYYYMMDD/walkforward/*` | window-level pnl, dd, sharpe |
| Plot Pack | `reports/year2/nightly/YYYYMMDD/plots/*.png` | equity curve, DD curve, slippage distribution |
| Model Metadata | `reports/year2/nightly/YYYYMMDD/model_card.json` | train span, features, validation metrics |

`metrics.json` generation contract:

- Producer script: `Scripts/year2_generate_metrics.py` (Year-2 implementation item).
- Inputs: `heartbeat.json`, `daemon_state.json`, `decisions.csv`, `trades.csv`, `rejects.csv`.
- Required keys: `max_dd_pct`, `win_rate`, `expectancy`, `slippage_bps_median`, `slippage_bps_p95`, `drift_bps_median`, `error_rate`.

## 7. Metrics & Telemetry Requirements

### 7.1 Required Dashboards

| Dashboard | Source | Must Show | Update Frequency |
|---|---|---|---|
| Operations Dashboard | `Scripts/dashboard.py` + `argus_py/dashboard/app.py` | equity, DD, risk level, counters, latest trades/rejects | 5-15 sec |
| Twin Comparison Dashboard | `Scripts/phase19_dashboard.py` | STRICT vs SOFT divergence and reject mix | 30-60 sec |
| Nightly QA Dashboard | generated artifacts in `reports/year2/nightly` | determinism, drift trend, slippage trend | daily |
| Gate Dashboard | `reports/year2/gates/*.json` | gate pass/fail by metric and trend | weekly |

### 7.2 Required Alerts

| Alert | Trigger | Channel |
|---|---|---|
| `alert_kill_switch` | risk level enters `SOFT/HARD/HALT` | Telegram + Discord |
| `alert_heartbeat_stale` | no heartbeat for `>= 3 min` | Telegram |
| Trade execution anomaly | slippage > p99 threshold | Telegram + Discord |
| Drift spike | drift > gate threshold for 2 consecutive batches | Telegram |
| Night batch failure | missing required artifacts by 06:00 local | Telegram + Email |

Implementation surface for alerts: `argus_py/alerts/templates.py`, `argus_py/alerts/dispatcher.py`.

## 8. Risk Policy (Year-2)

### 8.1 Core Policy Values

| Policy | Paper | Micro-live | Live |
|---|---|---|---|
| `dailyLossCap` | `3.0%` | `2.0%` | `1.5%` |
| `maxRiskPerTrade` | `1.0%` | `0.50%` | `0.35%` |
| `maxConcurrentPositions` | `3` | `2` | `2` (until Gate C pass) |
| `minCashReserve` | `10%` | `20%` | `25%` |

### 8.2 Cooldown Rules

| Rule | Value |
|---|---|
| Loss streak cooldown | 3 consecutive losses -> pause new entries for 30 minutes |
| High-volatility cooldown | if intrabar slippage p95 breaches threshold -> pause 15 minutes |
| Post-kill-switch cooldown | after recovery from `HARD`, force 12-hour paper-only mode |
| SOFT selective mode | only high-conviction entries, position size at 25-40% of normal |

### 8.3 Kill-Switch Triggers

Baseline trigger engine: `argus_py/risk/kill_switch.py`

- `SOFT`: daily loss breach, soft consecutive-loss threshold, or soft API error threshold.
- `HARD`: hard daily loss breach, hard consecutive-loss threshold, or hard API error threshold.
- `HALT`: total drawdown breach or manual emergency override.

## 9. Backtest Realism Assumptions (Must Be Enforced)

| Dimension | Year-2 Baseline | Calibration Rule |
|---|---|---|
| Fees | taker `4 bps`, maker `2 bps` (exchange-specific override allowed) | recalibrate monthly from live fills |
| Slippage | base `2 bps` + volatility multiplier + liquidity tier factor | keep modeled-vs-real median delta within gate thresholds |
| Spread | minimum `1 bps` synthetic spread floor | update per symbol weekly |
| Latency | paper: `150ms`, micro-live: observed `p50/p95`, live: observed + stress buffer | update from execution timestamps weekly |
| Rejections | include realistic order rejections and retries | error budget tracked per bar |

### 9.1 Realism Validation Commands

```bash
# Signal/decision audit
venv/bin/python Scripts/phase20_signal_audit.py runs/year2/paper_main --json \
  > reports/year2/realism/signal_audit_latest.json

# Weekly quality pack
venv/bin/python Scripts/weekly_audit.py runs/year2/paper_main --week 2026-W18 \
  > reports/year2/realism/weekly_audit_2026-W18.md
```

## 10. Folder Layout for Year-2 Deliverables

```text
runs/year2/
  paper_main/
  micro_live_main/
  live_main/
  nightly/YYYYMMDD/

reports/year2/
  gates/
  incidents/
  nightly/YYYYMMDD/
  realism/
  year_end_summary.md
```

## 11. Definition of Done for Year-2

- [ ] Q1-Q4 monthly milestones (M01..M12) completed with artifact evidence.
- [ ] Paper->Micro-live gate passed with all required metrics green for 2 consecutive weeks.
- [ ] Micro-live->Live gate passed with all required metrics green.
- [ ] Live scale-up Gate C passed (90-day stability window).
- [ ] Night Autopilot runs daily and writes full artifact set (metrics, reports, plots, model metadata).
- [ ] Operations dashboards and alert channels are active and tested by drill.
- [ ] Risk policy values are encoded in runtime configs and validated via audit.
- [ ] Backtest realism assumptions are calibrated monthly against real/micro-live fill data.
- [ ] Annual technical pack generated in `reports/year2/` including gate history and incident summary.
