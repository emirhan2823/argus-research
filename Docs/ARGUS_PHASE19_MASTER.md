# ARGUS Phase 19: Twin Engine & Counterfactual Learning
**Version:** 19.7 (Stable)
**Date:** February 2026

---

## 1. Project Purpose & Vision
Argus Phase 19 represents the transition from theoretical backtesting to **High-Fidelity Forward Testing**. The system employs a "Twin Engine" architecture to solve the "Overfitting vs. Missed Opportunity" dilemma.

**Core Vision:**
> "By running two identical strategy engines—one **STRICT** (Production Gates) and one **SOFT** (Widened Gates)—we generate a clean request-response dataset of 'What if?' scenarios (Counterfactuals). This allows us to tune risk gates (Min ADX, Max Exp Move) based on empirical forward data rather than historical curve fitting."

**Objectives:**
- **Zero-Risk Verification:** Validate execution logic and stability without risking capital.
- **Data-Driven Tuning:** Use the divergence between STRICT and SOFT engines to mathematically optimize gate thresholds.
- **Operational Robustness:** Ensure the daemon architecture is self-healing, observable, and crash-resistant.

---

## 2. System Architecture

```ascii
                                  +------------------+
                                  |   Market Data    |
                                  | (Binance Kline)  |
                                  +--------+---------+
                                           |
                                           v
+----------------------------------------------------------------------------------+
|                              PHASE 19 SUPERVISOR                                 |
|                        (Scripts/phase19_supervisor.py)                           |
|                                           |                                      |
|          +-----------------------+        |      +-----------------------+       |
|          |    DAEMON [STRICT]    |        |      |     DAEMON [SOFT]     |       |
|          | (Production Settings) |        |      | (Validation Settings) |       |
|          +-----------+-----------+        |      +-----------+-----------+       |
|                      |                    |                  |                   |
|           [Decision: BLOCK/GO]            |           [Decision: GO]             |
|                      |                    |                  |                   |
|              +-------v-------+            |          +-------v-------+           |
|              |  PaperBroker  |            |          |  PaperBroker  |           |
|              +-------+-------+            |          +-------+-------+           |
|                      |                    |                  |                   |
+----------------------+--------------------+------------------+-------------------+
                       |                    |                  |
                       v                    v                  v
                [decisions.csv]      [status.log]        [trades.csv]
                [rejects.csv]                            [rejects.csv]
                       |                    |                  |
                       +--------------------+------------------+
                                            |
                                            v
                                 +---------------------+
                                 | COUNTERFACTUAL LAB  |
                                 | (Scripts/phase19_*.py)|
                                 +----------+----------+
                                            |
                                            v
                                   [Tuning Proposals]
                                   [Audit Summaries]
```

---

## 3. Core Components

### A. Paper Daemon (`Scripts/paper_daemon.py`)
The worker unit. Each daemon is an independent process running the full strategy stack.
- **Inputs:** Live Binance Klines (1m).
- **Logic:**
    - `RegimeDetector`: Identifies Market State (CHOP, RANGE, TREND).
    - `Aegean/Orion`: Generates signals and volatility metrics.
    - `Council`: Voting mechanism for trade entry.
    - `ModeRouter`: Switches risk profiles (ATTACK, DEFENSE).
- **Execution:** Uses `PaperBroker` to simulate fills, slippage, and commission.
- **Observability:** Logs `EXEC_ATTEMPT`, `TRADE_REJECTED`, and writes to CSVs/JSONL.

### B. Supervisor (`Scripts/phase19_supervisor.py`)
The process manager.
- **Function:** Launches `STRICT` and `SOFT` daemons as subprocesses.
- **Resilience:** Monitors PIDs and Heartbeats. Auto-restarts daemons if they crash or hang.
- **Concurrency:** Ensures no port/file conflicts between twins (separate run directories).

### C. Paper Broker (`argus_py/broker/paper.py`)
A high-fidelity simulation of an exchange.
- **Features:**
    - Deterministic Position IDs (SHA1 hash of trade details).
    - Configurable Spread, Slippage, and Fees (bps).
    - Realistic Order Types: Market Entry, Fixed Brackets, Trailing Stops.
    - **Guardrails:** Max Risk %, Max Notional, Liquidation Safety Checks.

### D. Counterfactual Lab (`Scripts/phase19_counterfactual.py`)
The analytics engine.
- **Logic:** Compares `STRICT` (Block) vs `SOFT` (Go) timestamps.
- **Output:** `counterfactual_labels.csv` (Did the rejected trade win or lose?).
- **Metric:** Shadow PnL (The PnL we *would* have had).

---

## 4. Data & Folder Structure

All runtime data is strictly scoped to `runs/phase19_twin/`.

```text
runs/phase19_twin/
├── STRICT/                     # Production Daemon Workspace
│   ├── daemon_state.json       # Persistence (Balance, Positions)
│   ├── decisions.csv           # Signal Log (All votes)
│   ├── decisions.jsonl         # Detailed JSON Telemetry
│   ├── trades.csv              # Execution Log (Fills, PnL)
│   ├── rejects.csv             # Gate Rejection Log (Min ADX, etc.)
│   ├── status.log              # Heartbeat & Startup Logs
│   └── errors.log              # Stack Traces
├── SOFT/                       # Validation Daemon Workspace
│   ├── ... (Same structure)
└── lab/                        # Evaluation Output
    ├── counterfactual_labels.csv
    ├── reject_audit_summary.md
    └── tuning_proposals.md
```

---

## 5. Current System Status

### Status: **OPERATIONAL (Stable)**

- **Trade Execution:** **Verified**. Trades execute and log correctly in `trades.csv`.
- **Reject Handling:** **Verified**. Execution failures (Risk Cap, Min Notional) log to `rejects.csv` and `trades.csv` (Event: `REJECTED`).
- **Counterfactuals:** **Verified**. Lab runs without crashing on missing data.
- **Reliability:** **High**. Supervisor handles restarts; `paper_daemon` handles rate limits.
- **Risk System:** **Fixed**. Fractional units (0.01 = 1%) enforced globally.

### Known Limitations
- **Exit Signals:** Currently relies on Broker Brackets (TP/SL). Strategy-based `EXIT` signals are not yet fully wired to execution.
- **Live Data:** Relies on `requests` polling (HTTP). No WebSocket implementation yet (latency ~1-2s).

---

## 6. Recent Fixes & Patches

1.  **Risk Unit Standardization (Hotfix):**
    -   Problem: CLI args (1.0) were treated as 100% risk internally.
    -   Fix: Enforced canonical fractional units. `1.0` CLI -> `0.01` Internal. Added validation logs.
2.  **Execution Observability:**
    -   Added `EXEC_ATTEMPT` logging to see calculated risk/price before execution.
    -   Broker rejections now explicitly logged to CSVs.
3.  **Counterfactual Robustness:**
    -   Fixed `TypeError` loop when rejection reasons were `None` or `NaN`.
    -   Added sanity counters to lab output.
4.  **Safe Paper Mode:**
    -   Added `--safe_paper` flag to enforce `min_risk_pct` (0.1%) and `soft_defense_override` to ensure low-balance accounts still trade.

---

## 7. Development Priorities

1.  **Tuning Proposal Automation:**
    -   Fully implement `Scripts/phase19_tuning_proposals.py` to auto-adjust `min_adx` based on Shadow PnL.
2.  **Dashboard Visualization:**
    -   Finalize `Scripts/phase19_dashboard.py` (Streamlit) for real-time monitoring of Twin Divergence.
3.  **Exit Strategy Evolution:**
    -   Move from Fixed IO brackets to Volatility-based Dynamic Exits (Chandelier Exits).

---

## 8. Daily Workflow

### A. Start the System
```bash
./Scripts/phase19ctl.sh twin-start
./Scripts/phase19ctl.sh twin-status
```

### B. Monitor
check logs for activity:
```bash
# Watch Soft Daemon (Active Trading)
tail -f runs/phase19_twin/SOFT/status.log
# Watch Decision Stream
tail -f runs/phase19_twin/SOFT/decisions.csv
```

### C. Evaluate (Counterfactuals)
Run the lab to generate audit reports:
```bash
./Scripts/phase19ctl.sh lab-run
# Review Output
cat runs/phase19_twin/lab/reject_audit_summary.md
```

### D. Stop
```bash
./Scripts/phase19ctl.sh twin-stop
```

---

## 9. Debugging Checklist

| Symptom | Check | Action |
| :--- | :--- | :--- |
| **No Trades (STRICT)** | `decisions.csv` has `GO`? | If `BLOCK`, check `rejects.csv`. Commonly `MIN_ADX` or `ROUTER_DEFENSE`. |
| **No Trades (SOFT)** | `rejects.csv` codes? | If `EXEC_REJECT`, check Risk Caps. Try `--safe_paper`. |
| **Crash Loop** | `errors.log` | Usually Binace API rate limit or JSON corruption. Supervisor will auto-restart. |
| **Lab Crash** | `lab-run` output | Typically data mismatch. Ensure both daemons ran for overlapping times. |
| **Risk Mismatch** | `status.log` startup | Verify `MaxRisk` prints `0.0100` (1%) not `1.0000`. |

---

## 10. Long-Term Roadmap

- **Phase 20:** **Live Execution**. Connecting `PaperBroker` logic to `BinanceExecution`.
- **Phase 21:** **Portfolio Mode**. Running multiple Symbols (ETH, SOL) concurrently with shared capital.
- **Phase 22:** **Reinforcement Learning**. Using Counterfactual data to train a policy network (PPO) for dynamic gating.

---

## 11. Engineering Philosophy

1.  **Fail Noisily, Fail Safe:** If execution logic is ambiguous, reject the trade and log exactly why.
2.  **Data is Truth:** Don't guess if a strategy change is better. Run it in `SOFT` mode, collect Shadow PnL, and prove it.
3.  **Twin Architecture:** Always maintain a control group (`STRICT`) to benchmark experimental changes (`SOFT`).
4.  **Canonical Units:** All internal math uses fractions (0.01). All User Interface uses Percent (1.0%). Interfaces must convert immediately.
