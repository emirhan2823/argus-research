# ARGUS v2.5 Algorithm Specifications

## 1. Darwin Engine (Genetic Algorithm)

**Objective:** Evolve trading strategies that survive diverse market regimes.
**Constraints:** Population Size = 64 (CPU Optimized).

### 1.1 Genome Structure
A list of floating-point genes normalized to [0, 1].
```python
class Genome:
    id: str
    genes: List[float]  # Length: 12

    # Interpretation Map (Example)
    # [0]: EMA_Short_Period (10-100)
    # [1]: EMA_Long_Period (100-300)
    # [2]: RSI_Period (7-21)
    # [3]: Entry_Threshold (30-70)
    # [4]: Stop_Loss_ATR_Mult (1.5-4.0)
    # [5]: Take_Profit_ATR_Mult (2.0-8.0)
    # [6]: Max_Hold_Hours (4-48)
    # [7-11]: Reserved / Unused
```

### 1.2 Fitness Function
Calculated over a purged walk-forward window (e.g., last 3 months, excluding embargo period).

```python
def calculate_fitness(trades: List[Trade]) -> float:
    if not trades:
        return -1000.0  # Death penalty for inactivity

    returns = [t.pnl_pct for t in trades]
    sharpe = sharpe_ratio(returns)
    recovery_factor = net_profit / abs(max_drawdown)
    win_rate = len([r for r in returns if r > 0]) / len(returns)
    max_dd = abs(max_drawdown_pct(returns))

    # Core Formula
    # Reward Stability (Sharpe), Resilience (Recovery), Accuracy (WinRate)
    # Punish Drawdown heavily.
    score = (0.4 * sharpe) + (0.3 * recovery_factor) - (0.2 * max_dd * 100) + (0.1 * win_rate * 10)

    # Hard Constraints
    if max_dd > 0.12:  # 12% Max DD Limit
        return -1000.0

    if len(trades) < 10: # Minimum sample size
        return -500.0

    return score
```

### 1.3 Evolution Cycle (Tournament Selection)
1.  **Select:** Pick 4 random genomes. The best one becomes a parent. Repeat to get 2 parents.
2.  **Crossover:** Uniform Crossover (50% chance per gene to come from Parent A or Parent B).
3.  **Mutation:** 5% chance per gene to add Gaussian noise (Mean=0, Std=0.1).
4.  **Elitism:** Keep top 2 genomes unchanged in next generation.

---

## 2. Reflector (Counterfactual Simulation)

**Objective:** Analyze *execution quality* and *luck* by simulating alternative actions post-trade.
**Trigger:** Runs immediately after a trade closes (Stop Loss or Take Profit).

### 2.1 Simulation Scenarios
For every closed trade `T`:

1.  **Scenario A (Hold Longer):**
    - "What if we held for 1 more hour?"
    - Simulate price action for `T.exit_time + 1h`.
    - Record `P_1h` (PnL if exited at 1h mark).

2.  **Scenario B (No Stop Loss):**
    - "Would the price have recovered?"
    - Simulate price action for `T.exit_time + 4h` assuming no SL was hit.
    - Record `P_no_sl` (PnL or Liquidation).

3.  **Scenario C (Tighter Stop):**
    - "Could we have lost less?"
    - Re-run trade with SL at 0.5x original distance.
    - Record `P_tight_sl`.

### 2.2 Classification Logic
- **"BAD_LUCK":** SL hit, but price immediately reversed and would have hit TP within 1h (`P_no_sl > 0`).
- **"BAD_TIMING":** Entry was good, but `P_tight_sl` would have been hit instantly. Volatility was underestimated.
- **"GOOD_SKILL":** Trade hit TP, and `P_1h` < TP (perfect exit).
- **"LUCK":** Trade hit TP, but `P_tight_sl` would have been hit first if noise was slightly higher.

### 2.3 Output: Adjustment Vector
Used to tune HyperSizer for future trades.
- If "BAD_LUCK" freq > 30%: Widen SL (Increase ATR Multiplier).
- If "BAD_TIMING" freq > 30%: Improve Entry (Wait for pullback / Limit Order).

---

## 3. HyperSizer (Adaptive Kelly)

**Objective:** Allocate capital efficiently based on confidence, not just fixed rules.
**Constraints:** Max Leverage 5x. "Survival First".

### 3.1 Inputs
- `W`: Win Probability (Estimated by Darwin WinRate or Seer Model).
- `R`: Win/Loss Ratio (Avg Profit / Avg Loss).
- `K`: Kelly Fraction (Full Kelly = W - (1-W)/R).
- `C`: Confidence Score (Signal Strength * SQS Score).
- `V`: Volatility Adjustment (1 / Normalized ATR).

### 3.2 Calculation
```python
def calculate_size(account_equity, W, R, C, V):
    # 1. Base Kelly
    kelly_pct = W - ((1 - W) / R)

    # 2. Safety Half-Kelly (Standard practice)
    safe_kelly = kelly_pct * 0.5

    # 3. Confidence Scaling
    # If SQS is low, reduce size drastically.
    scaled_size = safe_kelly * C * V

    # 4. Hard Limits ("Survival First")
    MAX_RISK_PER_TRADE = 0.02 # 2% Equity
    MAX_LEVERAGE = 5.0

    # Cap by Risk
    risk_amount = account_equity * scaled_size
    if risk_amount > (account_equity * MAX_RISK_PER_TRADE):
        scaled_size = MAX_RISK_PER_TRADE

    # Cap by Leverage
    if scaled_size * leverage > MAX_LEVERAGE:
        scaled_size = MAX_LEVERAGE / leverage

    return max(0.0, scaled_size)
```

---

## 4. Signal Quality Score (SQS)

**Objective:** Filter out low-quality signals *before* they reach the Risk Manager.
**Range:** [0.0, 1.0]. Pass Threshold: 0.7 (Configurable).

### 4.1 Components & Weights

| Component | Weight | Description |
| :--- | :--- | :--- |
| **Regime Match** | 0.30 | Is signal aligned with broad market regime? (e.g., LONG in Uptrend). |
| **Structure** | 0.20 | Is entry near Support (Long) or Resistance (Short)? Score based on distance. |
| **Microstructure** | 0.15 | Order Book Imbalance. Is there buying pressure? |
| **News Sentiment** | 0.15 | FinBERT Score. Positive news supports Longs. |
| **Correlation** | 0.10 | Is this asset correlated with a crashing market? (Contagion check). |
| **Fee Expectancy** | 0.10 | (Est. Profit - Fees) > 0? If low volatility, fees kill the trade. |

### 4.2 Calculation Logic
```python
def calculate_sqs(signal, market_context):
    score = 0.0

    # 1. Regime (Binary or Gradient)
    if signal.direction == market_context.regime:
        score += 0.30
    elif market_context.regime == "CHOP":
        score += 0.15 # Partial credit in chop if mean-reversion

    # 2. Structure (Distance to Support/Resistance)
    dist_norm = normalize(signal.entry - market_context.nearest_level)
    score += 0.20 * (1.0 - dist_norm) # Closer is better

    # 3. Microstructure (OBI)
    obi = market_context.order_book_imbalance # [-1, 1]
    if signal.direction == "LONG":
        score += 0.15 * max(0, obi)
    else:
        score += 0.15 * max(0, -obi)

    # ... (Add other components)

    return score
```
