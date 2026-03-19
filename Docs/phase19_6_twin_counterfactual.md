# Phase 19.6: Twin Engine & Counterfactuals

## 1. Twin Architecture
We run two instances of `paper_daemon.py`:
- **STRICT**: Current production config (min_adx=35, max_exp=80).
- **SOFT**: Relaxed config (min_adx=28).

Both write to `runs/phase19_twin/{STRICT,SOFT}/`.

## 2. Telemetry (Standardized)
Logs are now in JSONL format for machine readability:
- `decisions.jsonl`
- `rejects.jsonl`
- `trades.jsonl`

## 3. Counterfactual Generator
`Scripts/phase19_counterfactual.py` compares logs to find divergences:
- **Case A**: STRICT blocks, SOFT enters.
- **Case B**: SOFT blocks, STRICT enters.

It computes "Shadow PnL" using fixed horizons (30m, 60m, 120m) to label the reject as:
- **REJECT_BAD**: Missed profit (>0.2%)
- **REJECT_GOOD**: Saved loss (<-0.2%)
- **UNCLEAR**: Flat outcome

## 4. Operational Commands

**Start Twin Daemon**
```bash
./Scripts/phase19ctl.sh twin-start
```

**Monitor Status**
```bash
./Scripts/phase19ctl.sh twin-status
```

**Launch Twin Dashboard**
```bash
./Scripts/phase19ctl.sh twin-ui
```

**Generate Counterfactual Dataset**
```bash
python3 Scripts/phase19_counterfactual.py
```
Output: `runs/phase19_twin/datasets/counterfactual.jsonl`

## 5. Artifacts
- `argus_py/telemetry/schema.py`: Event schema.
- `Scripts/phase19_supervisor.py`: Twin-aware supervisor.
- `Scripts/phase19_dashboard.py`: Twin dashboard.
