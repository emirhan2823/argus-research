# Argus Research Laboratory

## Experiment Log

| ID | Date | Goal | Config | Outcome |
|----|------|------|--------|---------|
| E0 | 2026-01-29 | Sanity Check | Buy&Hold vs Bot | Bot avoids drawdowns but lags in strong bull runs (expected). |
| E1 | 2026-01-29 | Conservative vs Sniper | Convict > 0.75 vs 0.55 | Sniper trades 2-3x more frequency. |
| E2 | 2026-01-29 | Small Cap Reality | $30 Start | Requires rounding/min-notional hacks. Fees eat profit fast if overtrading. |
| E3 | 2026-01-29 | Smart Leverage | Dynamic Lev | 2x Lev in Trend improves ROI significantly if entry efficient. |

## Planned Experiments
1.  **Ensemble Diversification**: Adding Mean Reversion agent to reduce correlation.
2.  **Dynamic Take Profit**: Scaling out at 1R, 2R.

## Running Experiments
Use the runner script:
```bash
python3 argus_py/lab/runner_experiments.py --data_dir argus_py/data
```
Outputs saved to `argus_py/lab/experiments_TIMESTAMP.csv`.
