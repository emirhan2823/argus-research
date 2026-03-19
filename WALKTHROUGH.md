# Argus Phase P4 Walkthrough

## 1. Single Run with Visualization & Reporting
To run a backtest with limited bars and generate a full report:

```bash
python -m argus_py.runner.cli --symbol BTCUSDT --start_balance 1000 --mode backtest --data_dir argus_py/data --max_bars 500 --report
```

**Output:**
- Runs the backtest on the **last 500 bars**.
- Generates `report.md` in the run folder.
- Generates `equity.png` and `drawdown.png`.

## 2. Batch Lab Grid
To run the full research grid (balances x max_bars x conviction x floors):

```bash
python -m argus_py.runner.cli --data_dir argus_py/data --lab_grid
```
OR
```bash
python -m argus_py.lab.batch_run --data_dir argus_py/data
```

**Output:**
- Iterates through all combinations.
- Skips combinations if data is insufficient (checked against `max_bars`).
- Aggregates results in `argus_py/lab/results.csv`.
- Creates individual run folders with logs.

## 3. Interpreting Results
- **BlockReason**: Check `report.md` or `decision_log.csv` to see why trades were blocked (e.g., `Veto`, `Mode Block`).
- **Warmup**: If `Loaded X bars` is small and few trades occur, check `warmup_rate` in `results.csv`.
- **Lockdown**: Occurs if `PerformanceGuard` triggers safety stop.
