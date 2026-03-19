# Argus Research Playbook

## 1. Objective
Use the Research Pack to optimize Argus parameters, validate robustness, and compare strategies without risking capital.

## 2. Tools

### A. Grid Search (`argus_py/lab/grid_search.py`)
Runs a backtest across a permutation of parameters on the entire dataset.
**Use for:** Initial hypothesis testing, finding parameter sensitivity.

**Parameters searched:**
*   `Profile`: DEFENSIVE, BALANCED, DEGEN
*   `Council Threshold`: 0.3, 0.4, 0.6
*   `Exit Policy`: FIXED_BRACKET, TRAILING_STOP

**Command:**
```bash
python3 argus_py/lab/grid_search.py \
  --data_dir argus_py/data/ \
  --symbol BTCUSDT \
  --start_balance 1000
```
**Output:** `runs/grid_compare_TIMESTAMP.csv` (Sorted by Return).

### B. Walk-Forward Optimization (`argus_py/lab/walkforward_v2.py`)
Simulates running the bot live by optimizing parameters on a "Train" window and testing on a subsequent "Test" window.
**Use for:** Validating if past performance predicts future results (Robustness).

**Command:**
```bash
python3 argus_py/lab/walkforward_v2.py \
  --data_dir argus_py/data/ \
  --symbol BTCUSDT \
  --start_date 2023-01-01 \
  --end_date 2023-03-01 \
  --train_days 30 \
  --test_days 7
```
**Output:** `argus_py/lab/walkforward_results_TIMESTAMP.csv`.

## 3. Core Experiments

### Experiment A: Conservative vs Aggressive
Run Grid Search. Compare `DEFENSIVE` (threshold 0.4) vs `BALANCED` (threshold 0.3).
*   **Hypothesis**: Lower threshold increases trade frequency but reduces Win Rate.
*   **Metric**: Look at `ProfitFactor` in the CSV.

### Experiment B: Exit Policies
Review `ExitPolicy` column in Grid Search results.
*   `FIXED_BRACKET`: Hard SL/TP.
*   `TRAILING_STOP`: Moves SL as price advances.
*   **Hypothesis**: Trailing stop captures more trend upside but may stop out early in chop.

### Experiment C: Small Account Realism
Run Grid Search with `--start_balance 30` (modify script default or args).
*   Check `runs/.../decision_log.csv` for skipped trades due to Min Notional.

## 4. Interpretation
*   **Sharpe Ratio**: Not explicitly calculated yet, use `Return / MaxDD` as proxy.
*   **Overfitting**: If Grid Search shows one config dominating significantly but failing in Walk-Forward, it is overfit.
