# Phase 16: Variant Wiring Audit

## Problem Statement
In Phase 14/15, we observed that:
- `A_Baseline_Norm`
- `V1_Adx45`
- `V5_Adx45_MaxExp`

Produced **identical** trade sets (Fingerprint: `9c2aa13b`). This defeats the purpose of "variants" vs "baseline".

## Wiring Analysis
We traced the argument flow from `backtest_pack.sh` -> `cli.py` -> `Router/Gate`.

### 1. `backtest_pack.sh`
- **Baseline**: `run_test "A_Baseline_Norm" $NORM_COST`
  - Passes only fee/slip/spread args.
- **V1**: `run_test "V1_Adx45" $NORM_COST --min_adx 45.0`
- **V5**: `run_test "V5_Adx45_MaxExp" $NORM_COST --min_adx 45.0 --max_exp_move_bps 80.0`

### 2. `cli.py` Defaults
Inside `cli.py`, the `argparse` definitions set the defaults:
```python
parser.add_argument("--max_exp_move_bps", type=float, default=80.0, ...)
parser.add_argument("--min_adx", type=float, default=45.0, ...)
```

### 3. Resolution
| Scenario | MinADX (Arg) | ExpMove (Arg) | MinADX (Effective) | ExpMove (Effective) |
|---|---|---|---|---|
| A_Baseline_Norm | *None* | *None* | **45.0** (Default) | **80.0** (Default) |
| V1_Adx45 | 45.0 | *None* | 45.0 | **80.0** (Default) |
| V5_Adx45_MaxExp | 45.0 | 80.0 | 45.0 | 80.0 |

**Conclusion**: All three scenarios execute with effectively identical parameters logic. The "Baseline" is not a zero-filter baseline; it is a "Production V5" baseline.

## Proposed Fix (Implemented)
To verify parameter sensitivity and restore the semantic meaning of "Baseline", we reset the CLI defaults to **Neutral**:

- `min_adx`: `None` (Treated as 0.0/Disabled)
- `max_exp_move_bps`: `None` (Treated as 0.0/Disabled)

### Verification
- **A_Baseline_Norm** (Defaults):
  - `min_adx=None` -> 0.0.
  - `max_exp=None` -> 0.0.
  - Result: **30 Trades** (includes Weak Trend trades).
- **V1_Adx45**:
  - `min_adx=45.0`.
  - Result: **19 Trades**.
- **Conclusion**: Scenarios now diverge as expected.
