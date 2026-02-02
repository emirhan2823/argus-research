# Phase 3 Design: The "Council" & Adaptive Risk

## 1. Objective
Enhance the Argus Trading System (both Swift CLI and Python Port) to move beyond single-indicator entries ("Aegean") to a robust, multi-confirmation system ("The Council") with regime-adaptive risk management ("Chiron").

## 2. Core Philosophy
**"Trade Less, Trade Better."**
- **Multi-confirmation**: No single indicator is trusted. Entries require consensus or a "Strong Claim" supported by regime.
- **Adaptive Risk**: Position size and strategy behavior change based on Market Regime (Trend vs. Chop).
- **Survival First**: In "Risk-Off" or "Chop" regimes, capital preservation is prioritized over seeking signals.

## 3. Architecture: The Council (Voting System)

*Reference: `ArgusDecisionEngine.swift`*

The system shall aggregate "Opinions" from distinct modules. For Phase 3 (Technical Only), the Council consists of:

### **Modules**
1.  **Orion (Trend Hunter)**
    - **Logic**: Moving Averages, ADX, structure breaks.
    - **Role**: Identifies the primary trend direction.
    - **Output**: Score 0-100 (>60 Buy, <40 Sell).
2.  **Phoenix (Mean Reversion)**
    - **Logic**: Bollinger Bands, RSI Divergence, Regression Channels.
    - **Role**: Identifies overextended moves for counter-trend or dip-buying entries.
    - **Output**: Score 0-100.
3.  **Aegean (Momentum)**
    - **Logic**: Existing Slope/Zone logic.
    - **Role**: Signal timing (Trigger).
    - **Refactor**: Aegean becomes a sub-component of Orion or a standalone "Trigger" module.

### **Voting Logic ("The Debate")**
1.  **Gather Scores**: Collect 0-100 scores from Orion, Phoenix, Aegean.
2.  **Consensus Weights**: Apply "Authority" derived from Regime.
    - *Trend Regime*: Orion has 2x weight.
    - *Chop Regime*: Phoenix has 2x weight.
3.  **Decision**:
    - **Buy**: Weighted Avg > 65 AND No Veto.
    - **Sell**: Weighted Avg < 35 AND No Veto.
    - **Veto**: Any module opposing strictly (>80 strength in opposite direction) blocks the trade.

## 4. Architecture: Chiron (Regime Engine)

*Reference: `ChironRegimeEngine.swift`*

The Risk Engine must be improved to be **Regime-Aware**.

### **Regime Detection (Technical Only)**
Since the CLI lacks Macro data (`Aether`), we determine regime via Price Action:
1.  **Chop Index**: detects sideways movement.
2.  **Volatility**: ATR or Standard Deviation.
3.  **Trend Strength**: ADX.

| Regime | Condition | Strategy | Risk Multiplier |
| :--- | :--- | :--- | :--- |
| **TREND** | ADX > 25, Low Chop | Follow Orion | 1.0x |
| **CHOP** | High Chop Index | Follow Phoenix | 0.5x |
| **RISK-OFF** | Extreme Volatility | Cash / Hedges | 0.0x (No Entry) |

### **R-Model (Risk Budget)**
Instead of fixed 10% equity:
`AllowedRisk = BaseRisk * RegimeMultiplier * QualityScore`

- **BaseRisk**: e.g. 1% of Equity per trade (Account Risk).
- **RegimeMultiplier**: See table above.
- **QualityScore**: Derived from Council Consensus (Stronger signal = Full size, Weak signal = Half size).

## 5. Advanced Exits (Execution Plan)

Trades are no longer "Fire and Forget". The Strategy emits an `ExecutionPlan`.

### **Dynamic Brackets**
1.  **Stop Loss (SL)**:
    - **Trend**: Wide ATR (e.g. 3.0x ATR) to allow pullbacks.
    - **Mean Rev**: Tight structure-based (below recent Low).
2.  **Take Profit (TP)**:
    - **Trend**: Open-ended (Trailing Stop only) or high R:R (3:1).
    - **Mean Rev**: Fixed Target (Mean/Band) or 1.5:1 R:R.

### **Active Management**
1.  **Trailing Stop**: Activates when trade reaches +1R profit. Trails by ATR distance.
2.  **Time Stop**: If trade is +/- 0.5% after 12 bars (3 hours), exit Market. (Capital recycling).
3.  **Standard Deviation Exit**: If price moves > 3 Sigma against position, emergency exit.

## 6. Implementation Plan (Backtest/CLI)

### **Step 1: Module Extraction (Swift)**
- Ensure `Orion` and `Phoenix` logic in `Algo-Trading/Services` can be instantiated by `ArgusRunner/main.swift` without full iOS dependencies.
- **Goal**: `let orion = OrionEngine()` works in CLI.

### **Step 2: CLI Integration**
- Modify `ArgusRunner/main.swift` loop:
    ```swift
    // Phase 3 Loop
    let regime = chiron.detect(history)
    let orionScore = orion.analyze(history)
    let phoenixScore = phoenix.analyze(history)
    
    let decision = council.debate(orion: orionScore, phoenix: phoenixScore, regime: regime)
    
    if decision.isGo {
        let plan = execution.createPlan(decision, availableEquity)
        broker.execute(plan)
    }
    ```

### **Step 3: Python Port Parity**
- Ensure Python `src/argus/strategy/` structure mirrors this "Council" design.
- Implement `Orion` and `Phoenix` as separate classes in Python.
- Implement `Chiron` class for regime detection.

## 7. Migration Path
- **Current**: Aegean Minimal (Single Indicator).
- **Next**: Aegean + Chiron (Regime-aware Aegean).
- **Target**: Full Council (Orion + Phoenix + Aegean + Chiron).

This design preserves the Swift architecture by reusing the patterns found in `ArgusDecisionEngine.swift` while adapting them for the headless CLI environment.
