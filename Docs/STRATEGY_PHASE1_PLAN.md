# Strategy Phase-1: Edge Upgrade Plan

## Overview
**Objective**: Improve the raw predictive power (Edge) of the `ExpMove` signal.
**Current State**: Pipeline is robust, friction is realistic, but the core "Slope + ADX" signal has low correlation (approx -0.3) in the current regime (BTC 1m), suggesting mean-reversion dynamics or noise.

## 1. Candidate Approaches

### Candidate A: ATR + Trend Continuation (Refined)
- **Hypothesis**: Low quality comes from "fighting the trend" or "late entry" in chopped markets.
- **Logic**: 
    - **Filter**: `ADX > 25` (Trend Mode).
    - **Confirmation**: `Slope` direction MUST match `Trend` direction (e.g., EMA-200 slope or Higher TF).
    - **Trigger**: Pullback entries (Slope decreases but Trend remains).
- **Validation**: 
    - Expect `HitRate` improvement in `TREND` regime.
    - `ExpMove` should correlate positively with `Realized` in high ADX bins.

### Candidate B: Mean Reversion (Regime Switching)
- **Hypothesis**: Negative correlation (-0.3) indicates the market is mean-reverting at this timeframe/sensitivity.
- **Logic**:
    - **Switch**: If `ADX < 20` (Chop) OR `AutoCorrelation < 0`.
    - **Action**: Fade the Slope.
        - If `Slope > Thresh` -> **SELL**.
        - If `Slope < -Thresh` -> **BUY**.
    - **Target**: Fixed Reward/Risk (e.g., 1ATR / 1ATR).
- **Validation**:
    - PnL should flip from negative to positive in `CHOP` regime.

### Candidate C: Multi-Timeframe Confirmation (MTF)
- **Hypothesis**: 1m Slope is essentially noise. 5m or 15m Trend provides the "True" direction.
- **Logic**:
    - **Input**: Resampled indicators (5m, 15m), not just 1m.
    - **Rule**: `GO` only if `Slope(1m)` == `Slope(5m)` == `Slope(15m)`.
    - **Alternative**: `GO` if `1m` crosses `5m` (Momentum ignition).
- **Validation**:
    - Drastic reduction in Trade Count (lower frequency).
    - Higher `Avg Realized` per trade.

## 2. Validation Metrics (Beyond PnL)
We validte "Edge" not "Profit":
1.  **Hit Rate (> Cost)**: `%` of trades where `Realized > Fees+Slip`.
2.  **Reliability**: `ExpMove` bins should be monotonic (Higher ExpMove -> Higher Realized).
3.  **Correlation**: Spearman Rank Correlation > 0.1 (Positive predictive power).

## 3. GitHub Integration (Adapter Pattern)
We will likely import indicators/strategies from external repos (e.g. `freqtrade` community strategies).
**Do NOT copy-paste blindly.** Use the Adapter Pattern.

### Folder Structure
```
argus_py/
  features/
    adapters/
      __init__.py
      freqtrade_wrapper.py  # Generic adapter
      rsi_custom.py         # Adapted logic
```

### Import Checklist
- [ ] **License Check**: Is it MIT/Apache? (GPL requires caution).
- [ ] **Dependencies**: Does it need heavy libs (ta-lib involved?) Prefer `pandas_ta` or pure numpy if possible.
- [ ] **Speed**: Vectorized (pandas)? Avoid loops.
- [ ] **Standardization**:
    - Input: `df[['open','high','low','close','volume']]`.
    - Output: `pd.Series` (Signal or Indicator).
    - No side effects (plotting, printing).

### Example Adapter
```python
def adapt_freqtrade_indicator(df, func, **kwargs):
    """
    Wraps a freqtrade-style populate_indicators function.
    """
    # 1. Standardize Columns (lower case)
    df.columns = [c.lower() for c in df.columns]
    # 2. Call Logic
    df_res = func(df, **kwargs)
    # 3. Return specific column
    return df_res['target_col']
```
