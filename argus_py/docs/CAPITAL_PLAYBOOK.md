# Argus Capital Scaling Playbook

## 1. Objective
Argus is designed to evolve. It starts in "Survival Mode" ($30) and scales to "Pro Mode" ($10k+). The `CapitalEngine` automatically detects your account size and adjusts risk parameters.

## 2. Profiles

| Profile | Equity Range | Max Risk | Lev Cap | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SMALL** | < $100 | 2.0% | 1x | Growth via compounding. No bust risk. |
| **GROWTH** | $100 - $1k | 1.5% | 2x | Balanced acceleration. |
| **SCALE** | $1k - $10k | 1.0% | 3x | Portfolio building. Defensive bias. |
| **PRO** | > $10k | 0.5% | 3x | Capital preservation. Kelly-sizing. |

## 3. Safety Guard (Adaptive)
The system watches your rolling 20-trade Win Rate and Equity Curve slope.

*   **Losing Streak**: If WR20 < 40%, Risk is halved.
*   **Drawdown > 8%**: Forces `DEFENSIVE` mode (0.5x Risk).
*   **Drawdown > 15%**: **LOCKDOWN**. No new trades for 20 bars.

## 4. How to Run
Auto-scaling is **ON** by default.

```bash
# Start with $30 (Will use SMALL profile)
python3 argus_py/runner/cli.py --symbol BTCUSDT --start_balance 30

# Start with $5000 (Will use SCALE profile)
python3 argus_py/runner/cli.py --symbol BTCUSDT --start_balance 5000
```

## 5. Reporting
To see how your capital evolved:
```bash
python3 argus_py/reporting/capital_report.py --run_dir runs/YOUR_RUN_ID
```
Check `capital_evolution.csv` for frame-by-frame analysis of:
*   Assigned Profile
*   Effective Risk %
*   Lockdown Status
