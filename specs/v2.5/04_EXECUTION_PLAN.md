# ARGUS v2.5 Execution & Implementation Plan

## 1. Reference Repo Integration Strategy

To accelerate development while maintaining the custom "21 Module" architecture, we will leverage existing high-quality libraries rather than forking full bots.

### 1.1 Core Libraries (The "Engine Block")
*   **Execution/Data:** `nautilus_trader` (Rust-core, Event-driven).
    *   *Why:* Handles "Time Machine" data replay and live execution seamlessly.
    *   *Role:* Replaces custom `Backtester` and parts of `Executioner`.
*   **Exchange Connectivity:** `ccxt` (Async).
    *   *Role:* Direct API wrapper for BingX (Nautilus uses this under the hood or via adapters).
*   **Vectorized Backtesting (Darwin/Reflector):** `vectorbt` (Pro optional).
    *   *Why:* Extremely fast for Genetic Algorithm (Darwin) simulations on CPU/GPU.
    *   *Role:* Evolution engine.

### 1.2 ML & NLP (The "Brain")
*   **News Sentiment:** `transformers` (Hugging Face) + `pytorch`.
    *   *Model:* `ProsusAI/finbert` (Small, fast, accurate for finance).
*   **Feature Engineering:** `polars` (Faster than Pandas) + `ta-lib`.

---

## 2. Acceptance Criteria (GIVEN / WHEN / THEN)

These scenarios define the "Done" state for critical modules.

### 2.1 Signal Quality System (SQS) - The Gatekeeper
**Scenario: Low Quality Signal Rejection**
*   **GIVEN** the market is in a "CHOP" regime (ADX < 20),
*   **AND** a Strategy generates a "BREAKOUT_LONG" signal,
*   **AND** SQS calculates `structure_score` = 0.4 (No support nearby),
*   **AND** SQS calculates `news_sentiment` = -0.2 (Negative),
*   **WHEN** the signal is passed to the SQS Gate,
*   **THEN** SQS must return `passed=False` with `reason="REGIME_MISMATCH + SENTIMENT"`.
*   **AND** `TradeDecision` must be `REJECT`.

### 2.2 HyperSizer - Survival First
**Scenario: Drawdown Protection**
*   **GIVEN** Account Equity is $10,000,
*   **AND** Current Drawdown is 5% (Max is 12%),
*   **AND** A high-confidence signal (SQS=0.9) arrives,
*   **WHEN** HyperSizer calculates position size,
*   **THEN** the `Risk_Multiplier` must be reduced by 50% (due to 5% DD).
*   **AND** The final leverage must NOT exceed 2x (Conservative mode).

### 2.3 Reflector - Counterfactual Learning
**Scenario: Bad Timing Detection**
*   **GIVEN** a trade hit Stop Loss at $2000,
*   **AND** Reflector simulates "Scenario C" (Tighter Stop at $2010),
*   **AND** Simulation shows Tighter Stop would *also* have been hit,
*   **BUT** "Scenario A" (Hold 1h) shows price rebounded to $2050,
*   **THEN** Reflector classifies trade as "BAD_TIMING" (Direction correct, entry too early).
*   **AND** Increments `bad_timing_counter` for that Strategy Genome.

---

## 3. Phased Implementation Plan

### Package 0: Foundation (Weeks 1-2)
*   **Deliverables:**
    *   Docker/Podman Compose setup (`Bunker`).
    *   `TimeMachine` (Parquet storage) + `ccxt` fetcher.
    *   `Regenerator` (Watchdog script).
    *   Logging & Metrics (Prometheus/Grafana).
*   **Goal:** Reliable data ingestion and storage.

### Package 1: The Oracle & Sages (Weeks 3-4)
*   **Deliverables:**
    *   `Oracle`: TA-Lib / Polars feature pipeline.
    *   `Hermes`: FinBERT integration (GPU enabled).
    *   `Sage`: Vector DB (ChromaDB or FAISS) for regime search.
*   **Goal:** Rich `FeatureVector` generation.

### Package 2: The Singularity (Weeks 5-8)
*   **Deliverables:**
    *   `Darwin`: Genetic Algorithm core using `vectorbt`.
    *   `Reflector`: Post-trade simulation logic.
    *   `HyperSizer`: Kelly criterion logic.
*   **Goal:** A strategy engine that evolves and learns.

### Package 3: Execution & Control (Weeks 9-12)
*   **Deliverables:**
    *   `Executioner`: NautilusTrader / CCXT Order management.
    *   `Sentinel`: Pre-trade risk checks.
    *   `SQS`: The final gatekeeper logic.
    *   **Live Paper Trading.**
*   **Goal:** End-to-end automated trading (Safety First).
