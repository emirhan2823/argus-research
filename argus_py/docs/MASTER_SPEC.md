# Argus Master Specification

## 1. System Architecture
Argus is a hybrid autonomous trading system designed for small-to-mid cap resilience and scalability. It uses a "Council of Experts" architecture for decision making and a strict state-machine for risk management.

### Components
1.  **Council** (`argus_py/council`): Aggregates votes from multiple specialist agents.
    *   *Aegean*: Trend/Momentum expert.
    *   *Orion*: Mean Reversion/Volatility expert.
    *   *Upcoming*: Phoenix (Reversion), Hermes (Arb).
2.  **Risk Engine** (`argus_py/risk/mode_engine.py`):
    *   Determines **Risk Profile** based on equity ($30 -> DEGEN, $1000 -> DEFENSIVE).
    *   Determines **Operating Mode** (NORMAL, SAFE, AGGRESSIVE) based on market regime and PnL streaks.
    *   Enforces **Smart Leverage** (up to 2-3x) only when conditions are optimal (Trend + High Conviction).
3.  **Broker** (`argus_py/broker/paper.py`):
    *   Simulates realistic execution (Fees, Slippage, Min Notional).
    *   Enforces lifecycle invariants (No same-bar close).

## 2. Safety Profiles
| Profile | Capital | Leverage | Risk Mult | Description |
|---------|---------|----------|-----------|-------------|
| **DEGEN** | < $100 | Up to 3x | 1.5x | Survival & Aggressive Growth. 5% daily stop. |
| **BALANCED** | $100-$1K | Up to 2x | 1.0x | Standard operation. |
| **DEFENSIVE** | > $1K | 1x Max | 0.5x | Capital Preservation. |

## 3. Decision Logic
1.  **Data Ingest**: 15m Bars.
2.  **Regime Detection**: Trend vs Chop.
3.  **Council Vote**: Agents output Direction + Confidence.
4.  **Deliberation**: Weighted average of votes -> Verdict (GO/NO_GO).
5.  **Risk Check**: ModeEngine validates if trade allowed.
6.  **Filter Check**: Cooldowns (3-5 bars), Hard Stops.
7.  **Execution**: Sizing based on risk %, leverage, and fees.

## 4. Lifecycle
*   **Entry**: Market Order (simulated slippage).
*   **Maintenance**: Trailing Stop, Time Stop (48 bars).
*   **Exit**: SL/TP or End-of-Run.
*   **Invariant**: Position cannot close on the same bar it opened.

## 5. Experimentation
Check `argus_py/lab/experiments.md` for research logs.
