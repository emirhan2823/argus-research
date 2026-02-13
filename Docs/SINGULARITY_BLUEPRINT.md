# ARGUS v2.5 — "The Singularity" 15-Module Master Blueprint

**Author:** Staff Quantitative Systems Architect
**Date:** 2026-02-11
**Status:** Architecture Specification (No Implementation Code)
**Hardware Target:** RTX A3000M (6GB VRAM, 4096 CUDA cores, Ampere)

---

## Table of Contents

1. [System Topology](#1-system-topology)
2. [MessageBus v2 Protocol](#2-messagebus-v2-protocol)
3. [Cluster 1 — The Evolutionary Brain](#3-cluster-1--the-evolutionary-brain)
4. [Cluster 2 — The Information Eyes](#4-cluster-2--the-information-eyes)
5. [Cluster 3 — The Predator](#5-cluster-3--the-predator)
6. [Cluster 4 — The Scale & Risk](#6-cluster-4--the-scale--risk)
7. [Cluster 5 — The Fortification](#7-cluster-5--the-fortification)
8. [Cross-Cluster Data Flow](#8-cross-cluster-data-flow)
9. [GPU Memory Budget](#9-gpu-memory-budget)
10. [Deployment Topology](#10-deployment-topology)

---

## 1. System Topology

```
                         +============================+
                         |     ARGUS SINGULARITY      |
                         |       MessageBus v2        |
                         +============================+
                                     |
         +---------------------------+---------------------------+
         |              |            |            |              |
 +-------v-------+ +---v----+ +----v-----+ +----v----+ +-------v-------+
 | CLUSTER 1     | | CLSTR 2| | CLUSTER 3| | CLSTR 4 | | CLUSTER 5     |
 | Evolutionary  | | Info   | | Predator | | Scale & | | Fortification |
 | Brain         | | Eyes   | |          | | Risk    | |               |
 +---------------+ +--------+ +----------+ +---------+ +---------------+
 | 1. Darwin     | | Hermes | | 7. Exec  | | 3. Sizer| | 4. Sentinel   |
 | 2. Reflector  | | 8. Harb| | 6. Chiron| |11. Hive | |10. Chaos Eng  |
 | 5. Oracle     | |13. Seer| |14. Ghost | |         | |12. Bunker     |
 | 9. Regenerator| |        | |          | |         | |               |
 |15. Auditor    | |        | |          | |         | |               |
 +---------------+ +--------+ +----------+ +---------+ +---------------+
```

### Module Maturity Map

| # | Module | File Path | Status | Action |
|---|--------|-----------|--------|--------|
| 1 | Darwin | `src/learning/darwin.py` | BUILT | Integrate with pipeline |
| 2 | Reflector | `src/learning/reflector.py` | BUILT | Integrate with pipeline |
| 3 | Hyper-Sizer | `src/risk/sizing.py` | BUILT | Replace `mde/sizing.py` in pipeline |
| 4 | Sentinel | `src/data/sentinel/validator.py` | BUILT | Extend with cross-exchange |
| 5 | Oracle | `src/ml/chronos/forecaster.py` | BUILT | Add ensemble + GPU path |
| 6 | Chiron | `argus_py/models/chiron/` | BUILT (v1) | Rewrite as RL-based in `src/` |
| 7 | Executioner | `src/execution/executor.py` | BUILT (basic) | Add smart limit + TWAP |
| 8 | Harbinger | — | NEW | Build from scratch |
| 9 | Regenerator | — | NEW | Build from scratch |
| 10 | Chaos Engine | — | NEW | Build from scratch |
| 11 | The Hive | — | NEW | Build from scratch |
| 12 | The Bunker | — | NEW | Build from scratch |
| 13 | The Seer | — | NEW | Build from scratch |
| 14 | The Ghost | — | NEW | Build from scratch |
| 15 | The Auditor | — | NEW | Build from scratch |

---

## 2. MessageBus v2 Protocol

### 2.1 Current State (v2.0)

The existing `EventBus` (`src/core/events.py`) is synchronous pub/sub with
string-keyed callbacks. It has no message ordering, no priority, no
persistence, and no cross-process capability.

### 2.2 Upgraded Architecture

MessageBus v2 is an **in-process priority queue** with:

- **Typed Envelopes**: Every message is wrapped in a `BusEnvelope` carrying
  `source_module`, `target_module` (or broadcast), `priority`, `timestamp`,
  `correlation_id` (for request/response chains), and `payload`.
- **Priority Levels**: CRITICAL (0), HIGH (1), NORMAL (2), LOW (3), BACKGROUND (4).
  Kill switch and Bunker messages always use CRITICAL.
- **Ordered Delivery**: Within same priority, FIFO ordering.
- **Correlation Chains**: Every message carries `correlation_id`. When a
  Reflector emits a `CorrectionVector`, the downstream Darwin micro-evolution
  carries the same `correlation_id`, enabling full traceability.
- **Dead Letter Queue**: Messages that fail delivery 3 times are moved to
  a DLQ table in SQLite for post-mortem debugging.
- **Backward Compatibility**: The existing `EventBus.publish()` and
  `subscribe()` API wraps the new bus transparently. No existing code breaks.

### 2.3 Event Taxonomy (Extended)

```
PIPELINE EVENTS (existing, unchanged)
  CANDLE_CLOSE, SENTINEL_CHECK, FEATURES_READY, REGIME_SNAPSHOT,
  REGIME_CHANGED, SIGNAL_GENERATED, SIGNAL_REJECTED, DECISION_MADE,
  RISK_CHECK, ORDER_SUBMITTED, ORDER_FILLED, ORDER_REJECTED,
  SL_PLACED, SL_FAILED, POSITION_OPENED, POSITION_CLOSED,
  KILL_SWITCH_CHANGE, HEARTBEAT, ALERT, DAILY_REPORT, ERROR

HERMES EVENTS (existing, unchanged)
  HERMES_NEWS_RECEIVED, HERMES_ALERT, HERMES_BLOCK,
  HERMES_CLOSE_POSITION, HERMES_ADJUST_SL, HERMES_ADJUST_TP

ADVISORY EVENTS (existing, unchanged)
  ADVISORY_SIGNAL, ADVISORY_UPDATE

LEARNING EVENTS (v2.5, exists in events.py)
  REFLECTION_COMPLETE, CORRECTION_EMITTED,
  DARWIN_FULL_EVOLUTION, DARWIN_MICRO_EVOLUTION,
  GENOME_PROMOTED, MICRO_EVOLUTION_TRIGGERED

NEW — PERCEPTION EVENTS
  HARBINGER_CORRELATION_SHIFT    # Cross-asset regime early warning
  HARBINGER_DIVERGENCE_ALERT     # Lead/lag divergence detected
  SEER_WHALE_MOVEMENT            # Large wallet transfer detected
  SEER_ACCUMULATION_SIGNAL       # Smart money accumulation pattern
  SEER_DISTRIBUTION_SIGNAL       # Smart money distribution pattern

NEW — EXECUTION EVENTS
  GHOST_ICEBERG_PLACED           # Stealth order placed
  GHOST_SLICE_FILLED             # One iceberg slice filled
  GHOST_EXECUTION_COMPLETE       # All slices filled
  EXECUTIONER_LIMIT_PLACED       # Smart limit placed
  EXECUTIONER_LIMIT_IMPROVED     # Limit price improved (chasing)
  EXECUTIONER_TWAP_TICK          # TWAP slice executed
  CHIRON_LEVERAGE_DECISION       # RL-based leverage chosen

NEW — CONSENSUS EVENTS
  HIVE_CONSENSUS_REACHED         # Multi-agent ensemble agreed
  HIVE_DEADLOCK                  # Agents disagree, default to conservative
  HIVE_AGENT_VOTE                # Individual agent vote cast

NEW — RESILIENCE EVENTS
  CHAOS_STRESS_TEST_START        # Black swan simulation started
  CHAOS_STRESS_TEST_RESULT       # Simulation results ready
  BUNKER_HEARTBEAT               # Cross-platform health check
  BUNKER_FAILOVER_TRIGGERED      # Primary platform down, failover active
  BUNKER_RECOVERY_COMPLETE       # Primary platform restored

NEW — LIFECYCLE EVENTS
  REGENERATOR_RETRAIN_START      # Model retraining initiated
  REGENERATOR_RETRAIN_COMPLETE   # Model retrained, A/B test pending
  REGENERATOR_MODEL_PROMOTED     # New model passed A/B, now active
  REGENERATOR_MODEL_ROLLBACK     # New model failed A/B, rolled back
  AUDITOR_REPORT_GENERATED       # Performance attribution report ready
  AUDITOR_ALPHA_DECAY_ALERT      # Alpha source losing edge
```

### 2.4 Shared Data Contracts (New & Extended)

These contracts flow between modules via the MessageBus. All inherit from
`ArgusModel` (pydantic v2, frozen, strict, NaN-rejecting).

```
CrossAssetSnapshot          # Harbinger -> Hive, Chiron, Hyper-Sizer
  dxy_level: float
  dxy_change_24h: float
  ndx_change_24h: float
  nvda_change_24h: float
  btc_ndx_correlation_30d: float
  btc_dxy_correlation_30d: float
  cross_asset_regime: str   # "RISK_ON" | "RISK_OFF" | "DIVERGENT" | "NEUTRAL"
  lead_lag_signal: float    # -1.0 to +1.0 (positive = risk asset leading)
  confidence: float

WhaleSignal                 # Seer -> Hive, Hermes, Hyper-Sizer
  chain: str                # "ethereum" | "bitcoin" | "solana"
  event_type: str           # "ACCUMULATION" | "DISTRIBUTION" | "EXCHANGE_INFLOW" | "EXCHANGE_OUTFLOW"
  wallet_tier: str          # "TOP_100" | "TOP_500" | "INSTITUTION" | "UNKNOWN"
  symbol: str
  usd_value: float
  direction_bias: float     # -1.0 (bearish) to +1.0 (bullish)
  confidence: float
  timestamp: datetime

HiveConsensus               # Hive -> MDE Gates, Hyper-Sizer
  predator_vote: float      # -1.0 to +1.0
  guardian_vote: float
  turtle_vote: float
  consensus_direction: str  # "LONG" | "SHORT" | "ABSTAIN"
  consensus_strength: float # 0.0 to 1.0
  agreement_ratio: float    # % of agents that agree
  override_signal: bool     # True if consensus overrides engine signal

StressTestResult            # Chaos Engine -> Hyper-Sizer, Bunker, Auditor
  scenario_name: str        # "COVID_CRASH" | "LUNA_COLLAPSE" | "FTX_CONTAGION" | etc.
  max_drawdown: float
  recovery_time_hours: float
  positions_liquidated: int
  capital_at_risk: float
  var_95: float             # Value at Risk 95th percentile
  cvar_95: float            # Conditional VaR (Expected Shortfall)
  survival: bool            # Did the system survive without hitting hard floor?

LeverageDecision            # Chiron -> Executioner, Hyper-Sizer
  symbol: str
  asset_class: str
  regime: str
  base_leverage: float
  rl_adjusted_leverage: float   # After RL policy
  conviction_boost: float       # Additional leverage from conviction
  final_leverage: float         # Clamped to phase maximum
  q_value: float                # RL state-action value (for Auditor)
  exploration_flag: bool        # True if RL is exploring vs exploiting

AuditReport                 # Auditor -> Dashboard, Telegram
  period: str               # "daily" | "weekly" | "monthly"
  total_pnl: float
  alpha_pnl: float          # Return above benchmark
  beta_pnl: float           # Return from market exposure
  strategy_attribution: dict[str, float]  # PnL per engine
  regime_attribution: dict[str, float]    # PnL per regime
  best_trade: str
  worst_trade: str
  sharpe: float
  sortino: float
  max_drawdown: float
  alpha_decay_rate: float   # Trend of alpha over rolling window
  recommendations: list[str]

RegeneratorStatus           # Regenerator -> Auditor, Darwin, Pipeline
  model_name: str           # "chronos" | "lgbm" | "meta_label"
  action: str               # "RETRAIN_START" | "RETRAIN_COMPLETE" | "PROMOTED" | "ROLLBACK"
  old_metrics: dict         # Performance before retrain
  new_metrics: dict         # Performance after retrain
  a_b_test_pvalue: float    # Statistical significance of improvement
  gpu_time_seconds: float
```

---

## 3. Cluster 1 — The Evolutionary Brain

### 3.1 Module 1: Darwin (Genetic Algorithm Engine)

**File:** `src/learning/darwin.py` (EXISTS — 490 lines)

#### Input/Output Contract

```
SUBSCRIBES TO:
  CORRECTION_EMITTED         -> micro_evolve() trigger
  DAILY_REPORT               -> full_evolve() trigger (weekly check)
  REGENERATOR_MODEL_PROMOTED -> refresh fitness evaluation

PUBLISHES:
  DARWIN_FULL_EVOLUTION      -> EvolutionReport
  DARWIN_MICRO_EVOLUTION     -> EvolutionReport
  GENOME_PROMOTED            -> Genome (new active genome for engine/asset pair)

INPUT DATA:
  CorrectionVector           (from Reflector, via CORRECTION_EMITTED)
  trade_returns: np.ndarray  (from Telemetry DB, filtered by engine/asset)

OUTPUT DATA:
  Genome                     (active genome deployed to engine parameter override)
  EvolutionReport            (logged to telemetry, consumed by Auditor)
```

#### Core Logic/Math (Already Implemented)

- **Fitness Function:** `F = w_s * Sharpe + w_w * WinRate - w_d * MaxDD + w_p * ln(PF)`
- **Selection:** Tournament (k=3)
- **Crossover:** BLX-alpha (alpha=0.5) blend for continuous genes
- **Mutation:** Adaptive rate `mu = mu_0 * (2 - fitness/best_fitness)`, Gaussian perturbation
- **Elitism:** Top 3 survive unchanged
- **Micro-Evolution:** 5 challengers from active genome, 80% mutation rate on
  failure-mapped genes only, promote only if fitness improves

#### GPU Utilization

**Current:** CPU-only (numpy). Population of 30 genomes x 18 genes.

**Upgrade Path:** When population scales to 200+ (multi-asset, multi-timeframe
genomes), replace `numpy` with `cupy` for batch fitness evaluation:
- Vectorize the entire population's trade-return dot product on GPU
- Sharpe/DD/WinRate as parallel reduction kernels
- Estimated speedup: 15-20x at population=200, negligible at population=30

**Decision:** Keep CPU for now. GPU path activates when total populations
exceed 150 genomes (approximately 5 engine x 5 asset x 6 genome variants).

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Reflector | <-- receives | CorrectionVector | On every losing trade |
| Engines (Titan/Nautilus/Phoenix) | --> sends | Genome.genes | On GENOME_PROMOTED |
| Regenerator | <-- receives | Model metrics | After retrain, re-evaluate fitness |
| Auditor | --> sends | EvolutionReport | On every evolution cycle |
| Hive | --> sends | Active genome metadata | On population query |

---

### 3.2 Module 2: Reflector (Post-Trade Recursive Learning)

**File:** `src/learning/reflector.py` (EXISTS — 480 lines)

#### Input/Output Contract

```
SUBSCRIBES TO:
  POSITION_CLOSED            -> reflect() trigger

PUBLISHES:
  REFLECTION_COMPLETE        -> ReflectionRecord
  CORRECTION_EMITTED         -> CorrectionVector (if loss or underperformance)
  MICRO_EVOLUTION_TRIGGERED  -> {failure_mode, count} (if threshold hit)

INPUT DATA:
  TradeRecord                (from telemetry, on position close)
  FeatureVector              (from feature store, at time of entry)
  OHLC candles               (from data store, during trade lifetime)

OUTPUT DATA:
  ReflectionRecord           (persisted to SQLite reflections table)
  CorrectionVector           (genome_deltas for Darwin, chiron_nudges for Chiron)
```

#### Core Logic/Math (Already Implemented)

**Shadow Simulation Engine** — 4 counterfactual hypotheses:

1. **SL Width Shadow:** Test 5 alternative stops (0.5x, 0.75x, 1.25x, 1.5x, 2.0x
   original). Replay actual high/low price path. Calculate hypothetical PnL.
   ```
   shadow_pnl_i = replay(entry, exit, sl_i, high_low_path)
   improvement_i = shadow_pnl_i - actual_pnl
   ```

2. **Entry Timing Shadow:** Test entry delayed by 1, 2, 3 candles.
   ```
   shadow_entry_k = close[entry_candle + k]
   shadow_pnl_k = (exit - shadow_entry_k) / shadow_entry_k  [for longs]
   ```

3. **Hermes Veto Shadow:** Check if Hermes was signaling
   BLOCK_ENTRY or sentiment < -30 with HIGH/CRITICAL urgency.
   If so, `shadow_pnl = 0` (trade would not have been taken).

4. **ADX Threshold Shadow:** For TITAN losses with ADX in [25, 30),
   check if threshold at 30 would have filtered the trade.

**Failure Diagnosis:**
- Best shadow (by improvement_pct) reveals dominant cause
- Severity = `min(1.0, |best_improvement| / 0.05)`
- Maps to genome_deltas and chiron_weight_nudges

**Architectural Regret:**
```
regret = max(0, best_shadow_pnl - actual_pnl)
```
This is the metric the system minimizes over time through recursive learning.

**Micro-Evolution Trigger:**
- Rolling window of last 20 failure modes
- If any single FailureMode count >= 5, trigger Darwin.micro_evolve()

#### GPU Utilization

**None.** Reflector is I/O-bound (SQLite writes) and analytically lightweight.
Shadow simulations are O(N * M) where N = candles in trade, M = 5 SL perturbations.
Typical N < 100, so CPU is adequate.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Darwin | --> sends | CorrectionVector | On every loss/underperformance |
| Chiron | --> sends | chiron_weight_nudge | On every correction |
| Auditor | --> sends | ReflectionRecord | On every trade |
| Regenerator | --> sends | failure_distribution | On MICRO_EVOLUTION_TRIGGERED |
| Telemetry | --> sends | ReflectionRecord | Always (persistence) |

---

### 3.3 Module 5: Oracle (Time-Series Price Forecasting)

**File:** `src/ml/chronos/forecaster.py` (EXISTS — 53 lines, needs extension)

#### Input/Output Contract

```
SUBSCRIBES TO:
  FEATURES_READY              -> forecast() trigger
  REGENERATOR_MODEL_PROMOTED  -> reload model weights

PUBLISHES:
  (none — Oracle is a pull-based service, called by pipeline step 3-4)

INPUT DATA:
  price_series: Sequence[float]   (last 256-512 candles of close prices)
  horizon: int                    (forecast steps, default=1)

OUTPUT DATA:
  OracleForecast:
    median: float                 # Point forecast
    confidence_width: float       # 90th - 10th percentile
    direction_probability: float  # P(price_up) derived from forecast distribution
    forecast_distribution: list[float]  # Full quantile array (for Hive)
```

#### Core Logic/Math

**Primary Model:** Amazon Chronos-Bolt (70M parameters, transformer-based)

The Oracle produces a **probabilistic forecast**, not a point estimate.
Chronos outputs a set of sample trajectories. From these:

```
median = percentile(samples, 50)
p10 = percentile(samples, 10)
p90 = percentile(samples, 90)
confidence_width = p90 - p10
direction_probability = count(samples > current_price) / total_samples
```

**Ensemble Extension (v2.5):**

Oracle becomes a 3-model ensemble with inverse-variance weighting:

```
Models:
  M1: Chronos-Bolt (transformer, GPU)
  M2: LightGBM direction classifier (existing in src/ml/)
  M3: Naive statistical (momentum + mean-reversion blend)

For direction probability:
  w_i = 1 / variance_i(rolling_60_trades)
  P_ensemble = sum(w_i * P_i) / sum(w_i)

For point forecast:
  forecast_ensemble = sum(w_i * forecast_i) / sum(w_i)
```

**Confidence calibration:** Track `P_ensemble` vs actual outcomes over a
rolling window of 200 predictions. Apply Platt scaling (logistic regression)
to calibrate probabilities so that "70% confident" means "correct 70% of time."

```
P_calibrated = 1 / (1 + exp(-(a * P_ensemble + b)))
Where a, b are fit on rolling calibration set via MLE.
```

#### GPU Utilization

**Primary consumer of GPU memory.** Chronos-Bolt on RTX A3000M:

| Component | VRAM | Compute |
|---|---|---|
| Chronos-Bolt model weights | ~280 MB | Inference per symbol: ~50ms |
| Inference batch (5 symbols) | ~400 MB temp | Total: ~100ms batched |
| LightGBM | 0 (CPU) | ~2ms per symbol |

**Optimization:** Use `torch.inference_mode()`, `torch.float16` (Ampere
supports native FP16), and batch all 5 asset symbols into a single forward
pass. Context length 512 tokens.

**Memory budget:** 280 MB model + 400 MB inference = 680 MB out of 6 GB.
Leaves 5.3 GB for Regenerator training and Chaos Engine Monte Carlo.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Pipeline (step 3-4) | <-- called by | price_series | Every candle close |
| Hyper-Sizer | --> sends | direction_probability | Via conviction alignment |
| Hive | --> sends | forecast_distribution | For ensemble consensus |
| Regenerator | <-- receives | new model weights | On model promotion |
| Auditor | --> sends | calibration metrics | On daily report |
| Harbinger | --> sends | forecast for cross-asset | On cross-asset forecast |

---

### 3.4 Module 9: Regenerator (Automated Model Lifecycle)

**File:** `src/ml/regenerator.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  DAILY_REPORT               -> check if retraining criteria met
  AUDITOR_ALPHA_DECAY_ALERT  -> force immediate retraining
  CHAOS_STRESS_TEST_RESULT   -> adjust training data distribution

PUBLISHES:
  REGENERATOR_RETRAIN_START     -> {model_name, reason}
  REGENERATOR_RETRAIN_COMPLETE  -> RegeneratorStatus
  REGENERATOR_MODEL_PROMOTED    -> RegeneratorStatus
  REGENERATOR_MODEL_ROLLBACK    -> RegeneratorStatus

INPUT DATA:
  Historical OHLCV + features   (from data store)
  Current model weights         (from model registry)
  Performance metrics           (from Auditor)

OUTPUT DATA:
  RegeneratorStatus             (model lifecycle events)
  Updated model weights         (to model registry on disk)
```

#### Core Logic/Math

**Retraining Trigger Conditions** (any one sufficient):

```
1. Scheduled: Every 168 hours (weekly) for Chronos, every 72 hours for LightGBM
2. Performance degradation: rolling_sharpe(60_trades) < 0.5 * best_sharpe
3. Regime shift: regime distribution in last 50 candles differs from training
   distribution by KL-divergence > 0.3
4. Auditor alert: alpha_decay_rate > 0.02 per week
5. Data drift: PSI (Population Stability Index) > 0.25 on feature distributions
```

**Retraining Protocol:**

```
Phase 1: DATA PREPARATION (CPU)
  - Walk-forward split: 80% train, 10% validation, 10% holdout
  - Apply expanding window (never shrink training set)
  - Augment with Chaos Engine synthetic stress scenarios (5% of training data)
  - Feature selection: drop features with >20% missing or <0.01 importance

Phase 2: TRAINING (GPU — RTX A3000M)
  - Chronos: Fine-tune last 2 transformer layers on recent 2000 candles
    Loss: Quantile loss at tau = {0.1, 0.25, 0.5, 0.75, 0.9}
    Optimizer: AdamW, lr=1e-5, warmup=100 steps, cosine decay
    Epochs: 5-10 (early stopping on validation quantile loss)
  - LightGBM: Full retrain with GPU histogram method
    Objective: binary (direction) + auxiliary regression (magnitude)
    gpu_use_dp: false (use FP32 histogram for stability)
  - Meta-label model: Retrain on last 500 trade outcomes

Phase 3: A/B VALIDATION (CPU)
  - Run new model on holdout set
  - Paired t-test on per-trade PnL: new vs old
  - Promote only if p-value < 0.10 AND sharpe_new > sharpe_old
  - If fail: ROLLBACK, keep old model, log reason

Phase 4: DEPLOYMENT
  - Atomic model swap: write new weights to temp file, rename to active path
  - Publish REGENERATOR_MODEL_PROMOTED with before/after metrics
  - Darwin re-evaluates fitness with new model outputs
```

**Population Stability Index (PSI):**

```
PSI = sum( (actual_pct_i - expected_pct_i) * ln(actual_pct_i / expected_pct_i) )
For each feature, bin into 10 deciles. Compare last-50-candle distribution
vs training-set distribution. PSI > 0.25 indicates significant drift.
```

#### GPU Utilization

**Second largest GPU consumer:**

| Task | VRAM | Duration | Frequency |
|---|---|---|---|
| Chronos fine-tune (2 layers) | ~1.5 GB | ~3-5 min | Weekly |
| LightGBM GPU histogram | ~800 MB | ~30 sec | Every 72h |
| Meta-label retrain | ~200 MB | ~10 sec | Every 72h |

**Scheduling constraint:** Never retrain during live trading hours for the
target asset class. Crypto: retrain 04:00-06:00 UTC (low volume).
Equity: retrain 22:00-02:00 UTC (market closed).

**Memory management:** Unload Chronos inference model before fine-tuning.
Reload after. Total peak: 1.5 GB (training) vs 680 MB (inference).
Never exceeds 6 GB.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Oracle | --> sends | New model weights | On PROMOTED |
| Darwin | --> signals | Re-evaluate fitness | On PROMOTED |
| Auditor | <-- receives | Performance metrics, alpha decay | On DAILY_REPORT |
| Chaos Engine | <-- receives | Synthetic stress data | For training augmentation |
| Bunker | --> sends | Training status | For health monitoring |

---

### 3.5 Module 15: The Auditor (Performance Attribution)

**File:** `src/analytics/auditor.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  POSITION_CLOSED            -> update trade-level attribution
  REFLECTION_COMPLETE        -> consume regret metrics
  DARWIN_FULL_EVOLUTION      -> log genome performance
  REGENERATOR_MODEL_PROMOTED -> log model transition
  HEARTBEAT                  -> daily/weekly report trigger

PUBLISHES:
  AUDITOR_REPORT_GENERATED   -> AuditReport
  AUDITOR_ALPHA_DECAY_ALERT  -> {alpha_decay_rate, recommended_action}

INPUT DATA:
  TradeRecord stream         (from telemetry)
  ReflectionRecord stream    (from Reflector)
  EvolutionReport stream     (from Darwin)
  Benchmark returns          (BTC for crypto, SPY for equity)

OUTPUT DATA:
  AuditReport               (daily/weekly/monthly)
  Alpha decay alert         (triggers Regenerator retraining)
```

#### Core Logic/Math

**Alpha/Beta Decomposition (Brinson-Fachler Attribution):**

The Auditor separates returns into systematic (beta) and skill (alpha):

```
R_total = R_alpha + R_beta + R_interaction + R_residual

Where:
  R_beta = sum_j( w_j * R_benchmark_j )
    w_j = average weight in asset class j
    R_benchmark_j = benchmark return for asset class j

  R_alpha = R_total - R_beta - R_costs
    R_costs = slippage + fees + funding costs

  R_interaction = sum_j( (w_j - W_j) * (R_j - R_benchmark_j) )
    W_j = benchmark weight (equal-weighted across active assets)
```

**Strategy-Level Attribution:**

```
For each engine E in {TITAN, NAUTILUS, PHOENIX, HERMES}:
  alpha_E = sum(pnl_trade for trades where engine == E) - beta_contribution_E
  sharpe_E = mean(returns_E) / std(returns_E) * sqrt(252)
  information_ratio_E = alpha_E / tracking_error_E
```

**Alpha Decay Detection:**

```
Rolling alpha over 60-trade window, measured every 10 trades.
Fit linear regression: alpha_t = a + b * t + epsilon

If b < -0.02 (alpha declining at >2% per period):
  Publish AUDITOR_ALPHA_DECAY_ALERT
  recommended_action = "RETRAIN" if b < -0.05 else "MONITOR"
```

**Architectural Regret Tracking:**

```
cumulative_regret = sum(reflector.architectural_regret) over period
regret_trend = linear fit of per-trade regret over time

Healthy system: regret_trend slope < 0 (regret decreasing = system learning)
Unhealthy: regret_trend slope > 0 (regret increasing = system degrading)
```

**Regime Attribution:**

```
For each regime R in {TRENDING, RANGING, VOLATILE, CRISIS}:
  pnl_R = sum(pnl for trades where regime_at_entry == R)
  time_in_R = fraction of time spent in regime R
  efficiency_R = pnl_R / time_in_R  (PnL per unit time in regime)
```

#### GPU Utilization

**None.** Pure analytics, all operations are vectorized numpy on trade arrays.
Largest computation is rolling Sharpe/Sortino over 500-trade windows.
CPU-bound at < 100ms per report.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Reflector | <-- receives | ReflectionRecord, regret | On each trade |
| Darwin | <-- receives | EvolutionReport | On each evolution |
| Regenerator | --> sends | alpha_decay_alert | When alpha declining |
| Hyper-Sizer | --> sends | historical_win_rate, payoff_ratio | For Kelly estimation |
| Dashboard/Telegram | --> sends | AuditReport | Daily/weekly |
| Chaos Engine | --> sends | worst drawdown periods | For scenario generation |

---

## 4. Cluster 2 — The Information Eyes

### 4.1 Module (Legacy): Hermes (News Sentiment)

**File:** `src/engines/hermes/engine.py` (EXISTS — 83 lines)

#### Input/Output Contract (Unchanged)

```
SUBSCRIBES TO:
  CANDLE_CLOSE               -> fetch latest news, generate signal

PUBLISHES:
  HERMES_NEWS_RECEIVED, HERMES_ALERT, HERMES_BLOCK,
  HERMES_CLOSE_POSITION, HERMES_ADJUST_SL, HERMES_ADJUST_TP
  SIGNAL_GENERATED           (when generating entry signal)

INPUT:  RSS feeds (crypto/finance/regulatory), FeatureVector
OUTPUT: EngineSignal, HermesPositionInstruction, NewsSentiment
```

#### Core Logic/Math (Existing)

- LLM backend: Ollama (llama3.1:8b local) or Groq (llama-3.3-70b remote)
- Sentiment scoring: -100 to +100
- Signal: CRITICAL + score < -70 -> short (conf >= 0.9);
  score <= -50 -> short (conf >= 0.75); score >= 50 -> long (conf >= 0.75)
- Veto power: Can block entry, force position close, override regime to CRISIS

#### GPU Utilization

**Ollama backend uses GPU for LLM inference:**

| Model | VRAM | Latency |
|---|---|---|
| llama3.1:8b (Q4_K_M) | ~4.5 GB | ~2-3 sec per article |
| llama3.1:8b (Q5_K_M) | ~5.5 GB | ~3-4 sec per article |

**Contention with Oracle:** Cannot run Chronos inference AND Ollama
simultaneously (total > 6 GB). Solution: Hermes has a 2-second budget
in the pipeline. Oracle runs first (100ms), then Hermes runs, then
Oracle model is kept resident (280 MB << Ollama's 4.5 GB).

**Alternative:** Use Groq API for Hermes (zero local GPU) and reserve
full GPU for Oracle + Regenerator. This is the recommended configuration
for the RTX A3000M.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Seer | <-- receives | whale_movement context | Enriches sentiment analysis |
| Harbinger | <-- receives | cross-asset context | Enriches sentiment analysis |
| Reflector | --> sends | hermes_action at trade time | Stored in MarketSnapshot |
| Hive | --> sends | sentiment vote | For ensemble consensus |
| All engines | --> sends | Block/close instructions | Priority CRITICAL |

---

### 4.2 Module 8: Harbinger (Cross-Asset Correlation Engine)

**File:** `src/perception/harbinger.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  CANDLE_CLOSE               -> update correlation matrix
  FEATURES_READY             -> compute cross-asset signals

PUBLISHES:
  HARBINGER_CORRELATION_SHIFT  -> CrossAssetSnapshot
  HARBINGER_DIVERGENCE_ALERT   -> {lead_asset, lag_asset, divergence_pct, expected_reversion}

INPUT DATA:
  Multi-asset price series: BTC, ETH, SOL, NDX, SPX, DXY, XAUUSD, NVDA
  (From data adapters, 1H and 4H timeframes)

OUTPUT DATA:
  CrossAssetSnapshot          (regime + lead/lag signal)
  Divergence alerts           (early warning for mean-reversion opportunities)
```

#### Core Logic/Math

**1. Rolling Correlation Matrix (DCC-GARCH inspired):**

The Harbinger maintains a dynamic correlation matrix between 8 key assets.
Instead of full DCC-GARCH (computationally expensive), use an exponentially
weighted correlation:

```
C_t = lambda * C_{t-1} + (1 - lambda) * (r_t * r_t')

Where:
  C_t = correlation matrix at time t
  r_t = standardized return vector (8 assets)
  lambda = 0.94 (RiskMetrics decay factor, ~16-day half-life)
```

**2. Cross-Asset Regime Classification:**

```
Define 3 macro factors:
  F_risk = 0.4 * NDX_return + 0.3 * BTC_return + 0.3 * NVDA_return
  F_safety = 0.5 * DXY_return + 0.3 * XAUUSD_return + 0.2 * (-BTC_return)
  F_divergence = |corr(BTC, NDX)_30d - corr(BTC, NDX)_90d|

Cross-asset regime:
  If F_risk > 0 AND F_safety < 0:    RISK_ON
  If F_risk < 0 AND F_safety > 0:    RISK_OFF
  If F_divergence > 0.25:            DIVERGENT (decorrelation event)
  Else:                               NEUTRAL
```

**3. Lead/Lag Detection (Granger-like):**

```
For each pair (A, B):
  Compute cross-correlation at lags -6h to +6h
  If max(xcorr) at lag k > 0:  A leads B by k hours
  If max(xcorr) at lag k < 0:  B leads A by |k| hours

Lead-lag signal for target asset:
  signal = sum(w_i * direction_of_leader_i * lag_confidence_i)
  Where w_i = |cross_correlation_at_best_lag_i|
```

Key relationships to monitor:
- **DXY -> BTC** (negative, DXY typically leads by 2-6 hours)
- **NDX -> BTC** (positive, NDX leads during US hours)
- **NVDA -> SOL** (positive, AI narrative correlation)
- **XAUUSD -> BTC** (variable, competitive safe-haven narrative)

**4. Divergence Alert:**

```
For correlated pair (A, B) with historical corr > 0.6:
  z_spread = (r_A - beta * r_B) / sigma_spread
  If |z_spread| > 2.0:
    DIVERGENCE_ALERT
    expected_reversion_direction = -sign(z_spread)
    confidence = min(1.0, (|z_spread| - 2.0) / 2.0)
```

#### GPU Utilization

**Light.** Correlation matrix is 8x8, exponential update is O(64) per tick.
Cross-correlation at 12 lags for 28 pairs = 336 operations per candle.
CPU-adequate. No GPU needed.

**Potential GPU path:** If expanded to 50+ assets with intraday (1-minute)
updates, the correlation matrix update becomes 2500 elements * 60 updates/hour.
At that scale, use cupy for batch matrix operations.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Hive | --> sends | CrossAssetSnapshot | On every candle close |
| Hermes | --> sends | cross-asset context | Enriches sentiment |
| Hyper-Sizer | --> sends | cross_asset_regime | For conviction alignment |
| Chiron | --> sends | lead_lag_signal | For leverage adjustment |
| Atlas | --> sends | macro factor scores | Replaces current VIX/yield heuristic |
| Auditor | --> sends | correlation regime history | For attribution |

---

### 4.3 Module 13: The Seer (Whale Tracking & On-Chain Intelligence)

**File:** `src/perception/seer.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  CANDLE_CLOSE               -> poll on-chain data sources
  HERMES_NEWS_RECEIVED       -> cross-reference news with on-chain

PUBLISHES:
  SEER_WHALE_MOVEMENT         -> WhaleSignal
  SEER_ACCUMULATION_SIGNAL    -> WhaleSignal (event_type=ACCUMULATION)
  SEER_DISTRIBUTION_SIGNAL    -> WhaleSignal (event_type=DISTRIBUTION)

INPUT DATA:
  On-chain data feeds (REST APIs):
    - whale-alert.io or similar (large transaction monitoring)
    - Exchange inflow/outflow (Glassnode, CryptoQuant, or free alternatives)
    - Token holder distribution snapshots

OUTPUT DATA:
  WhaleSignal                 (direction bias + confidence)
```

#### Core Logic/Math

**1. Exchange Flow Imbalance:**

```
net_flow = exchange_inflow - exchange_outflow  (in USD, rolling 4h)
flow_zscore = (net_flow - mean_flow_30d) / std_flow_30d

Interpretation:
  flow_zscore > 2.0:   EXCHANGE_INFLOW (bearish — coins moving to sell)
  flow_zscore < -2.0:  EXCHANGE_OUTFLOW (bullish — coins moving to cold storage)

direction_bias = -tanh(flow_zscore / 3.0)  # Maps to [-1, +1]
confidence = min(1.0, |flow_zscore| / 4.0)
```

**2. Whale Transaction Scoring:**

```
For each large transaction T (> $1M USD equivalent):
  score_T = direction_score * size_score * wallet_score

Where:
  direction_score:
    +1.0 if exchange -> cold wallet (accumulation)
    -1.0 if cold wallet -> exchange (distribution)
    +0.5 if unknown -> cold wallet
    -0.5 if cold wallet -> unknown
    0.0 if exchange -> exchange (neutral)

  size_score = log10(usd_value / 1_000_000)  # Larger = more significant

  wallet_score:
    TOP_100 = 1.5
    TOP_500 = 1.2
    INSTITUTION (known) = 1.3
    UNKNOWN = 0.8

Aggregate:
  whale_signal = EMA(score_T, span=12h) / max_possible_score
```

**3. Accumulation/Distribution Pattern Detection:**

```
Over rolling 7-day window, for target symbol:
  accumulation_days = count(days where net_flow < -1.0 * std)
  distribution_days = count(days where net_flow > +1.0 * std)

If accumulation_days >= 5 out of 7:
  SEER_ACCUMULATION_SIGNAL (strong)

If distribution_days >= 5 out of 7:
  SEER_DISTRIBUTION_SIGNAL (strong)

Confidence = max_streak_length / 7
```

#### GPU Utilization

**None.** Seer is API-bound (HTTP calls to on-chain data providers) and
analytically trivial. All math is scalar or small-array operations.

**Rate limiting consideration:** Free-tier APIs typically allow 30-100
requests/minute. Seer operates on 1-hour cadence per symbol, well within limits.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Hermes | --> sends | whale context | Enriches news sentiment |
| Hive | --> sends | WhaleSignal | For ensemble consensus |
| Hyper-Sizer | --> sends | direction_bias | For conviction alignment |
| Harbinger | --> sends | flow data | Cross-reference with price correlation |
| Auditor | --> sends | signal accuracy history | For attribution |

---

## 5. Cluster 3 — The Predator

### 5.1 Module 7: Executioner (Smart Order Management)

**File:** `src/execution/executor.py` (EXISTS — 90 lines, needs extension)

#### Input/Output Contract

```
SUBSCRIBES TO:
  DECISION_MADE              -> execute() trigger
  GHOST_EXECUTION_COMPLETE   -> reconcile stealth execution
  CHIRON_LEVERAGE_DECISION   -> apply leverage to order

PUBLISHES:
  EXECUTIONER_LIMIT_PLACED    -> {order_id, symbol, side, price, size}
  EXECUTIONER_LIMIT_IMPROVED  -> {order_id, new_price, reason}
  EXECUTIONER_TWAP_TICK       -> {order_id, slice_filled, remaining}
  ORDER_SUBMITTED, ORDER_FILLED, ORDER_REJECTED (existing)

INPUT DATA:
  Decision                    (from MDE gates)
  LeverageDecision           (from Chiron)
  Orderbook snapshot         (from exchange adapter)

OUTPUT DATA:
  ExecutionResult            (success/failure, fill details, slippage)
```

#### Core Logic/Math

**Current state:** Basic market/limit order dispatch through BrokerAdapter.

**v2.5 Extension: 3-tier execution strategy:**

**Tier 1: Passive Limit (low urgency, confidence < 0.7)**
```
Place limit order at:
  LONG:  best_bid - spread * passive_offset  (passive_offset = 0.2)
  SHORT: best_ask + spread * passive_offset

Patience window: 5 minutes
If unfilled after 5 min: improve price by 1 tick every 30 seconds
Max improvements: 10 (then convert to market)

Expected slippage: -0.5 to +0.5 bps (often positive = maker rebate)
```

**Tier 2: Aggressive Limit (high urgency or confidence > 0.8)**
```
Place limit order at:
  LONG:  best_ask (cross the spread immediately)
  SHORT: best_bid

If not filled in 100ms: convert to market order

Expected slippage: 1-3 bps
```

**Tier 3: TWAP (large orders > 5% of average hourly volume)**
```
total_size = order_size
n_slices = ceil(total_size / (avg_hourly_volume * 0.01))
slice_size = total_size / n_slices
interval = 60 / n_slices  (spread over 1 minute)

For each slice:
  Place aggressive limit
  Random jitter: +/- 15% of interval
  If slice unfilled after interval: carry forward to next slice

Expected slippage: 2-5 bps (but zero market impact)
```

**Slippage Model:**
```
expected_slippage = base_slippage * (1 + size_impact + urgency_impact)

Where:
  base_slippage = spread / 2
  size_impact = (order_value / daily_volume) * 100  # Linear market impact
  urgency_impact = {EMERGENCY: 3.0, HIGH: 1.5, NORMAL: 0.5, LOW: 0.0}
```

#### GPU Utilization

**None.** Execution is latency-sensitive, not compute-sensitive.
GPU operations would add latency. All order math is O(1) arithmetic.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Ghost | --> delegates to | Large/stealth orders | When size > threshold or stealth flag |
| Chiron | <-- receives | LeverageDecision | Before order placement |
| Hyper-Sizer | <-- receives | GrowthSizingResult | Position size and risk |
| Sentinel | <-- receives | orderbook quality | For slippage estimation |
| Reflector | --> sends | ExecutionResult | For post-trade analysis |
| Bunker | --> sends | execution heartbeat | For health monitoring |

---

### 5.2 Module 6: Chiron v2 (RL-Based Dynamic Leverage & Weight Optimization)

**File:** `src/intelligence/chiron.py` (NEW — replaces legacy `argus_py/models/chiron/`)

#### Input/Output Contract

```
SUBSCRIBES TO:
  FEATURES_READY             -> observe state, compute action
  REFLECTION_COMPLETE        -> receive reward signal
  CORRECTION_EMITTED         -> receive weight nudge from Reflector
  HARBINGER_CORRELATION_SHIFT -> update state representation

PUBLISHES:
  CHIRON_LEVERAGE_DECISION   -> LeverageDecision

INPUT DATA:
  FeatureVector               (53 features, subset for state representation)
  RegimeState                 (regime, confidence, stability)
  CrossAssetSnapshot          (from Harbinger)
  PortfolioState              (current positions, drawdown)

OUTPUT DATA:
  LeverageDecision            (per-trade leverage recommendation)
  Engine weight adjustments   (council vote weights per regime)
```

#### Core Logic/Math

**Architecture: Soft Actor-Critic (SAC) with discrete action space**

Chiron v2 is a Reinforcement Learning agent that learns the optimal
leverage and engine weighting policy through experience.

**State Space (S):**
```
s_t = [
  # Regime features (4)
  regime_one_hot(4),           # TRENDING, RANGING, VOLATILE, CRISIS

  # Volatility context (3)
  atr_14_pct,
  realized_vol_20d,
  atr_ratio_5_20,

  # Momentum context (3)
  rsi_14 / 100,               # Normalized to [0, 1]
  adx_14 / 50,
  hurst_exponent,

  # Sentiment context (2)
  hermes_sentiment / 100,
  hermes_confidence,

  # Cross-asset context (3)
  cross_asset_regime_one_hot(4),  # From Harbinger
  lead_lag_signal,
  btc_ndx_correlation,

  # Portfolio context (4)
  drawdown / 0.10,            # Normalized to DD threshold
  consecutive_losses / 5,
  position_count / max_positions,
  equity / peak_equity,

  # Oracle context (2)
  chronos_direction_probability,
  chronos_confidence_width / atr_14,

  # Kill switch (1)
  kill_switch_level / 4,
]
# Total: ~26 state dimensions
```

**Action Space (A):**
```
Discrete actions (6 leverage levels x 2 aggression levels = 12):
  Leverage: {1.0, 1.25, 1.5, 1.75, 2.0, 2.5}
  Aggression: {CONSERVATIVE, AGGRESSIVE}
    CONSERVATIVE: standard engine weights
    AGGRESSIVE: amplify lead engine weight by 1.2x, reduce others

Final output:
  leverage = selected_leverage * growth_phase_cap  # Clamped
  weight_adjustment = aggression_modifier applied to engine weights
```

**Reward Function:**
```
r_t = risk_adjusted_pnl - lambda_dd * drawdown_penalty - lambda_regret * regret

Where:
  risk_adjusted_pnl = pnl / max(position_risk, 0.001)  # PnL per unit risk
  drawdown_penalty = max(0, drawdown - 0.02)^2          # Quadratic penalty above 2%
  regret = architectural_regret from Reflector           # Incentivize learning

Hyperparameters:
  lambda_dd = 2.0 (heavy drawdown aversion)
  lambda_regret = 0.5 (moderate regret aversion)
```

**Training (SAC algorithm):**
```
Networks:
  Actor (policy): s -> pi(a|s), 2 hidden layers [128, 64], ReLU
  Critic (Q1, Q2): (s, a) -> Q, 2 hidden layers [128, 64], ReLU
  Target critics: soft-updated with tau = 0.005

Training loop (after each trade):
  1. Store transition (s, a, r, s') in replay buffer (size=10000)
  2. If buffer > 256: sample mini-batch of 64
  3. Update critics via Bellman equation
  4. Update actor via reparameterization trick
  5. Adjust entropy coefficient alpha (target entropy = -log(1/|A|) * 0.98)

Exploration: Entropy regularization (SAC's built-in exploration)
  No epsilon-greedy needed. SAC naturally balances explore/exploit.
```

**Warm-start:** Before live trading, pre-train on backtested trades
(500+ transitions minimum). This avoids the "cold start" problem where
random actions could blow the account.

#### GPU Utilization

**Moderate:**

| Task | VRAM | Compute |
|---|---|---|
| SAC networks (3 nets) | ~15 MB | Inference: <1ms |
| Training step (batch=64) | ~50 MB | ~5ms per step |
| Replay buffer | CPU RAM (~40 MB) | — |

Chiron is the lightest GPU user. Networks are small (26-dim input,
12-dim output, 2 hidden layers). Training runs after each trade
(~10/day), negligible GPU load.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Executioner | --> sends | LeverageDecision | On every trade decision |
| Hyper-Sizer | --> sends | leverage, aggression | For position sizing |
| Reflector | <-- receives | reward signal (PnL, regret) | After trade close |
| Harbinger | <-- receives | CrossAssetSnapshot | For state observation |
| Oracle | <-- receives | direction_probability | For state observation |
| Darwin | <-- coordinates | Weight adjustments complement genome | Chiron adjusts weights, Darwin adjusts indicator params |

**Darwin/Chiron Separation of Concerns:**
```
Darwin optimizes WHAT to look at:    indicator periods, thresholds, gate params
Chiron optimizes HOW MUCH to bet:    leverage, aggression, engine weighting
Reflector tells both WHAT WENT WRONG: genome_deltas -> Darwin, weight_nudges -> Chiron
```

---

### 5.3 Module 14: The Ghost (Stealth Execution)

**File:** `src/execution/ghost.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  DECISION_MADE              -> check if stealth execution needed
  ORDER_FILLED               -> monitor for front-running detection

PUBLISHES:
  GHOST_ICEBERG_PLACED       -> {order_id, total_size, visible_size, slices}
  GHOST_SLICE_FILLED         -> {order_id, slice_num, fill_price, remaining}
  GHOST_EXECUTION_COMPLETE   -> ExecutionResult (aggregated)

INPUT DATA:
  Decision                   (with stealth flag or large size trigger)
  Orderbook depth            (from exchange adapter)
  Recent trade prints        (for front-running detection)

OUTPUT DATA:
  ExecutionResult            (aggregated across all slices)
```

#### Core Logic/Math

**Activation Criteria:**
```
Ghost activates when ANY of:
  1. position_value > 2% of 24h traded volume (market impact risk)
  2. spread > 2x normal (thin orderbook, need patience)
  3. Manual stealth flag in Decision
  4. Front-running detected on previous order
```

**Iceberg Order Algorithm:**

```
Input: total_size, orderbook_depth, avg_spread

1. Determine visible size:
   visible_pct = min(0.30, orderbook_depth[0] * 0.5 / total_size)
   visible_size = total_size * visible_pct
   (Show at most 30% of order, or half the best level depth — whichever is less)

2. Slice count:
   n_slices = ceil(total_size / visible_size)

3. Price ladder:
   For LONG iceberg:
     slice_prices = [best_bid - i * tick_size * random(1, 3) for i in range(n_slices)]
   Ensures each slice is at a slightly different price level

4. Timing:
   inter_slice_delay = random_uniform(2, 8) seconds
   (Randomize to avoid pattern detection)

5. Refill:
   When a slice fills, wait inter_slice_delay, then place next slice
   If price moves favorably by > 0.5 * spread: accelerate remaining slices
   If price moves adversely by > 2 * spread: pause and re-evaluate
```

**Front-Running Detection:**

```
After placing a visible limit order, monitor for:
  1. Sudden appearance of same-side orders within 100ms (mimicry)
  2. Price moving away by > 1 spread within 500ms of placement
  3. Large cancel-and-resubmit on opposite side (spoofing indicator)

If detected:
  Cancel current order
  Wait random(5, 15) seconds
  Re-enter with different visible size and price level
  Log incident for Auditor
```

#### GPU Utilization

**None.** Ghost is pure order management logic, latency-critical.
All decisions are O(1) comparisons and randomization.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Executioner | <-- delegated from | Large/stealth orders | On activation criteria |
| Sentinel | <-- receives | orderbook depth, spread | For sizing visible portion |
| Auditor | --> sends | slippage analysis | Per stealth execution |
| Bunker | --> sends | execution status | For health monitoring |

---

## 6. Cluster 4 — The Scale & Risk

### 6.1 Module 3: Hyper-Sizer (Adaptive Compounding Engine)

**File:** `src/risk/sizing.py` (EXISTS — 430 lines)

#### Input/Output Contract

```
SUBSCRIBES TO:
  (none — pull-based, called by pipeline step 8)

PUBLISHES:
  (none — returns GrowthSizingResult directly to caller)

INPUT DATA:
  GrowthSizingInput          (22 fields: stop, expected return, confidence,
                              equity, all multipliers, conviction alignment,
                              historical performance, safety parameters)

OUTPUT DATA:
  GrowthSizingResult         (13 fields: risk, position_size, leverage,
                              Kelly decomposition, all multiplier values,
                              phase name, USD position size)
```

#### Core Logic/Math (Already Implemented)

**The Growth Equation:**

```
C_n = C_0 * prod_{i=1}^{n} (1 + f_i * R_i)

Target: C_0 = $500, C_target = $1,000,000
Required multiple: 2000x
```

**Kelly Criterion (core):**
```
f* = (p * b - q) / b

Where:
  p = 0.6 * historical_win_rate + 0.4 * current_confidence
  b = expected_return / stop_distance (clamped to [0.5, 5.0])
  q = 1 - p
```

**Fractional Kelly with phase scaling:**
```
f_actual = f* * phase.kelly_fraction * safety_multipliers * conviction_amplifier

safety_multipliers = hard_floor * drawdown * cold_streak * correlation * pipeline
conviction_amplifier = activated only when ALL 3 alignment signals > 0.70
```

**5 Growth Phases (auto-scaling with equity):**
```
SURVIVAL     ($0-2K):    0.30x Kelly, 1.0x lev, 1.5% max risk
FOUNDATION   ($2-10K):   0.50x Kelly, 1.5x lev, 2.5% max risk
GROWTH       ($10-50K):  0.75x Kelly, 2.0x lev, 3.5% max risk
ACCELERATION ($50-200K): 1.00x Kelly, 2.5x lev, 4.5% max risk
COMPOUNDING  ($200K+):   0.85x Kelly, 2.0x lev, 3.5% max risk
```

**Hard Floor (ruin prevention):**
```
floor_equity = peak_equity * 0.60
mult = max(0, 1 - exp(-8 * (equity - floor_equity) / equity))

At equity = 70% of peak: mult ~ 0.75
At equity = 65% of peak: mult ~ 0.35
At equity = 60% of peak: mult = 0.00 (zero sizing, no trades)
```

**Conviction Amplifier (the Singularity multiplier):**
```
Requires ALL THREE > 0.70:
  chronos_alignment   (Oracle agrees with trade direction)
  hermes_alignment    (News sentiment aligns)
  engine_alignment    (Technical engine confidence)

avg = mean(3 alignments)
amplifier = 1.0 + (avg - 0.7) / 0.3 * (phase_cap - 1.0)

Phase caps: SURVIVAL=1.0x, FOUNDATION=1.15x, ..., ACCELERATION=1.50x
```

**Growth Projection (verified):**
```
At p=0.58, b=1.8, f=2%, 10 trades/week:
  G = p*ln(1+f*b) + q*ln(1-f) = 0.01197 per trade
  Trades to $1M: 632
  Time: ~14.6 months
  Doubling every: ~58 trades
```

#### GPU Utilization

**None.** All operations are O(1) arithmetic (exp, log, clamp).
Even `optimal_f()` brute-force search is O(100 * N_trades), negligible.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Chiron | <-- receives | LeverageDecision | leverage input |
| Oracle | <-- receives | direction_probability | conviction alignment |
| Hermes | <-- receives | sentiment alignment | conviction alignment |
| Seer | <-- receives | whale direction_bias | additional conviction signal |
| Harbinger | <-- receives | cross_asset_regime | environmental context |
| Auditor | <-- receives | historical_win_rate, payoff_ratio | Kelly estimation |
| Chaos Engine | <-- receives | StressTestResult | For hard floor calibration |
| Reflector | --> sends | sizing parameters | Stored in MarketSnapshot for post-mortem |

---

### 6.2 Module 11: The Hive (Multi-Agent Ensemble Consensus)

**File:** `src/consensus/hive.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  SIGNAL_GENERATED            -> feed to all agents
  HERMES_NEWS_RECEIVED        -> feed to Guardian agent
  HARBINGER_CORRELATION_SHIFT -> feed to all agents
  SEER_WHALE_MOVEMENT         -> feed to Predator agent
  SEER_ACCUMULATION_SIGNAL    -> feed to Turtle agent

PUBLISHES:
  HIVE_AGENT_VOTE             -> {agent_name, direction, confidence}
  HIVE_CONSENSUS_REACHED      -> HiveConsensus
  HIVE_DEADLOCK               -> {reason, default_action}

INPUT DATA:
  EngineSignal               (from router)
  CrossAssetSnapshot         (from Harbinger)
  WhaleSignal               (from Seer)
  OracleForecast            (from Oracle)
  FeatureVector             (from pipeline)

OUTPUT DATA:
  HiveConsensus              (aggregate vote -> MDE gates)
```

#### Core Logic/Math

**Three Agent Personas:**

Each agent evaluates the same signal through a different risk lens:

**Agent 1: PREDATOR (Aggressive Alpha-Seeker)**
```
Weight: 0.40

Score inputs:
  +0.30 * engine_signal.confidence
  +0.20 * oracle_direction_probability
  +0.20 * whale_direction_bias (from Seer)
  +0.15 * momentum_score (RSI + ADX + ROC composite)
  +0.15 * cross_asset_alignment (from Harbinger)

Vote:
  score > 0.60:  LONG  with confidence = score
  score < -0.60: SHORT with confidence = |score|
  else:          ABSTAIN
```

**Agent 2: GUARDIAN (Risk-Averse Protector)**
```
Weight: 0.35

Score inputs:
  +0.25 * engine_signal.confidence * (1 if regime not VOLATILE else 0.5)
  -0.25 * drawdown_severity  (0 at DD=0, 1 at DD=6%)
  -0.20 * hermes_negative_signal  (1 if sentiment < -30, 0 otherwise)
  +0.15 * hard_floor_distance  (distance from hard floor, normalized)
  +0.15 * regime_stability

Vote:
  score > 0.50:  agrees with engine direction, confidence = score * 0.8
  score < 0:     ABSTAIN (Guardian never initiates, only vetoes)
  
VETO POWER: If drawdown > 5% OR hermes_urgency == CRITICAL:
  Guardian forces ABSTAIN regardless of score
```

**Agent 3: TURTLE (Patient Trend-Follower)**
```
Weight: 0.25

Score inputs:
  +0.30 * trend_strength (ADX * ema_alignment direction)
  +0.25 * accumulation_signal (from Seer, rolling 7d)
  +0.20 * oracle_confidence (low confidence_width = high confidence)
  +0.15 * volume_confirmation (volume_ratio > 1.5 = confirmed)
  +0.10 * regime_is_trending  (1 if TRENDING, 0 otherwise)

Vote:
  score > 0.55:  agrees with trend direction, confidence = score * 0.9
  else:          ABSTAIN (Turtle only enters on strong trends)
```

**Consensus Mechanism:**

```
weighted_vote = sum(agent_weight_i * agent_vote_direction_i * agent_confidence_i)

agreement_ratio = count(agents voting same direction) / count(non-abstaining agents)

If count(non-abstaining) == 0:
  HIVE_DEADLOCK -> default to HOLD

If agreement_ratio >= 0.67 (2-of-3 or 3-of-3 agree):
  CONSENSUS_REACHED
  direction = majority direction
  strength = |weighted_vote|
  override_signal = True if strength > 0.75

If agreement_ratio < 0.67:
  HIVE_DEADLOCK
  If Guardian vetoed: direction = HOLD (safety first)
  Else: direction = ABSTAIN (let engine signal pass through without boost)
```

**Consensus impact on pipeline:**
```
If CONSENSUS_REACHED and override_signal:
  confidence_boost = +0.10 to engine signal confidence
  conviction_alignment boost for Hyper-Sizer

If HIVE_DEADLOCK with Guardian veto:
  reduce position size by 50%
  increase stop distance by 20%

If HIVE_DEADLOCK without veto:
  no modification (pass-through)
```

#### GPU Utilization

**None.** All agents are rule-based scoring functions, O(1) per evaluation.
No neural networks in the Hive — the intelligence comes from diverse
perspectives and voting aggregation, not model complexity.

**Future path:** If agents are upgraded to learned policies (like Chiron's
SAC), each would need ~15 MB VRAM. Total: ~45 MB. Negligible.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| All engines | <-- receives | EngineSignal | For agent evaluation |
| Oracle | <-- receives | forecast distribution | For Turtle/Predator |
| Hermes | <-- receives | sentiment | For Guardian |
| Harbinger | <-- receives | CrossAssetSnapshot | For all agents |
| Seer | <-- receives | WhaleSignal | For Predator/Turtle |
| MDE Gates | --> sends | HiveConsensus | Confidence adjustment |
| Hyper-Sizer | --> sends | consensus_strength | Conviction alignment |
| Auditor | --> sends | agent vote history | For attribution |

---

## 7. Cluster 5 — The Fortification

### 7.1 Module 4: Sentinel v2 (Multi-Exchange Data Integrity)

**File:** `src/data/sentinel/validator.py` (EXISTS — 261 lines, needs extension)

#### Input/Output Contract (Existing + Extensions)

```
SUBSCRIBES TO:
  CANDLE_CLOSE               -> validate data quality

PUBLISHES:
  SENTINEL_CHECK             -> SentinelReport (existing)
  SENTINEL_CROSS_EXCHANGE_DIVERGENCE  -> {primary_price, secondary_price, delta_pct}  (NEW)

INPUT DATA (Extended):
  SentinelInput              (existing 14 fields)
  + secondary_exchange_price: Optional[float]  (NEW — from fallback exchange)
  + secondary_exchange_volume: Optional[float]  (NEW)

OUTPUT DATA:
  SentinelReport             (existing: score, action, checks)
```

#### Core Logic/Math (Existing 6 checks + 2 new)

**Existing checks (unchanged):**
1. Staleness (>2x expected interval)
2. Price anomaly (z-score > 3 without volume confirmation)
3. Spread blowout (>5x normal)
4. Exchange latency (>2000ms)
5. Orderbook depth (crypto, <30% normal)
6. Funding spike (crypto, >10x normal)

**New check 7: Cross-Exchange Price Divergence**
```
If secondary_exchange_price is available:
  delta = |primary_price - secondary_price| / primary_price
  If delta > 0.005 (0.5%):
    FAIL — possible exchange manipulation or stale data
    Use min(primary, secondary) for conservative pricing
```

**New check 8: Volume Anomaly (Wash Trading Detection)**
```
volume_to_mcap_ratio = 24h_volume / market_cap
If volume_to_mcap_ratio > 0.5:  # Suspiciously high
  DEGRADED — potential wash trading, reduce confidence
```

#### GPU Utilization

**None.** All checks are O(1) comparisons and basic statistics.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Pipeline (step 2) | --> sends | SentinelReport | Every candle |
| Ghost | --> sends | spread, depth quality | For stealth sizing |
| Executioner | --> sends | orderbook quality | For slippage estimation |
| Chaos Engine | --> sends | historical anomaly data | For stress scenario generation |
| Bunker | --> sends | data quality trend | For health monitoring |

---

### 7.2 Module 10: Chaos Engine (Synthetic Black Swan Stress Testing)

**File:** `src/risk/chaos_engine.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  DAILY_REPORT               -> run daily stress test battery
  KILL_SWITCH_CHANGE         -> run emergency stress assessment
  POSITION_OPENED            -> run position-specific stress test

PUBLISHES:
  CHAOS_STRESS_TEST_START    -> {scenario_name, timestamp}
  CHAOS_STRESS_TEST_RESULT   -> StressTestResult

INPUT DATA:
  Current portfolio state    (positions, equity, allocations)
  Historical crisis data     (stored scenario library)
  Current market conditions  (volatility, regime, correlation)

OUTPUT DATA:
  StressTestResult           (per scenario: drawdown, VaR, CVaR, survival)
  Aggregated risk report     (across all scenarios)
```

#### Core Logic/Math

**Scenario Library (Pre-built + Synthetic):**

```
Historical scenarios (replay actual market moves):
  COVID_CRASH:        2020-03-09 to 2020-03-23 (BTC -50%, SPX -34%)
  LUNA_COLLAPSE:      2022-05-07 to 2022-05-13 (BTC -35%, LUNA -100%)
  FTX_CONTAGION:      2022-11-06 to 2022-11-14 (BTC -25%, SOL -60%)
  CHINA_BAN_2021:     2021-05-19 to 2021-05-23 (BTC -40%)
  RATE_SHOCK_2022:    2022-06-10 to 2022-06-18 (SPX -12%, BTC -30%)
  BANKING_CRISIS_2023: 2023-03-08 to 2023-03-13 (BTC +20%, SPX -5%)

Synthetic scenarios (parameterized):
  FLASH_CRASH:        -15% in 1 hour, recovery 50% in 4 hours
  EXCHANGE_HALT:      No fills for 30 minutes, gap -10%
  CORRELATION_SPIKE:  All assets corr -> 0.95, -20% across board
  FUNDING_SQUEEZE:    Funding rate spikes to -5%, liquidation cascade
  LIQUIDITY_DRAIN:    Spread widens 10x, depth drops 90%
```

**Monte Carlo VaR/CVaR Calculation:**

```
For each scenario S:
  1. Apply scenario returns to current portfolio positions
  2. For each position P:
     stress_pnl_P = position_value_P * scenario_return_P(asset_class)
  3. Total portfolio stress PnL:
     stress_pnl_total = sum(stress_pnl_P) - liquidation_costs

For Monte Carlo extension (1000 paths per scenario):
  For path j:
    returns_j = scenario_base + N(0, scenario_vol * 0.5)  # Add noise
    pnl_j = portfolio_pnl(returns_j)

  VaR_95 = -percentile(pnl_all_paths, 5)   # 5th worst percentile
  CVaR_95 = -mean(pnl where pnl < -VaR_95)  # Expected shortfall
```

**Survival Assessment:**

```
For each scenario:
  final_equity = current_equity + stress_pnl_total
  hard_floor = peak_equity * 0.60

  survival = (final_equity > hard_floor)

  If NOT survival:
    recovery_time = estimated hours to recover from stress_drawdown
      (based on current avg_pnl_per_day and remaining equity)

Aggregate:
  worst_case_drawdown = max(drawdown across all scenarios)
  survival_rate = count(surviving_scenarios) / total_scenarios
  capital_at_risk = max(|stress_pnl|) across all scenarios
```

**Dynamic Scenario Generation:**

```
The Chaos Engine creates NEW scenarios based on current conditions:

If regime == VOLATILE and VIX > 30:
  Generate "CURRENT_STRESS" scenario:
    base_return = -2 * current_atr_14_pct (2x current volatility shock)
    correlation_assumption = 0.8 (elevated correlation)
    duration = 24 hours

If Seer reports large exchange inflows:
  Generate "IMMINENT_SELL_PRESSURE" scenario:
    base_return = -3 * (inflow_value / market_cap)
    duration = 6 hours
```

#### GPU Utilization

**Moderate — for Monte Carlo simulation:**

| Task | VRAM | Compute |
|---|---|---|
| Monte Carlo (1000 paths x 12 scenarios) | ~200 MB | ~500ms on GPU |
| CPU fallback | 0 | ~5 seconds |

**Implementation:** Use CUDA random number generation (`cupy.random` or
`torch.cuda.FloatTensor.normal_()`) for path generation. Matrix multiplication
for portfolio impact calculation. Batch all 12,000 paths in a single kernel.

**Frequency:** Daily full stress test + on-demand per new position.
GPU time is negligible at once per day.

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Hyper-Sizer | --> sends | VaR, CVaR, survival | For hard floor calibration |
| Bunker | --> sends | worst-case assessment | For failover threshold |
| Auditor | --> sends | stress test history | For risk reporting |
| Regenerator | --> sends | synthetic crisis data | For training augmentation |
| Kill Switch | --> sends | stress-implied risk level | For preemptive escalation |
| Sentinel | <-- receives | historical anomaly data | For scenario library |

---

### 7.3 Module 12: The Bunker (Cross-Platform Fail-Safe & Watchdog)

**File:** `src/ops/bunker.py` (NEW)

#### Input/Output Contract

```
SUBSCRIBES TO:
  HEARTBEAT                  -> verify system liveness
  ERROR                      -> track error frequency
  KILL_SWITCH_CHANGE         -> escalation awareness
  All execution events       -> verify execution health

PUBLISHES:
  BUNKER_HEARTBEAT           -> {platform, status, uptime, last_trade_age}
  BUNKER_FAILOVER_TRIGGERED  -> {reason, primary_platform, failover_target}
  BUNKER_RECOVERY_COMPLETE   -> {downtime_seconds}

INPUT DATA:
  System heartbeats          (from pipeline, every 60 seconds)
  Platform health metrics    (CPU, memory, disk, network, GPU)
  Exchange connectivity      (ping latency, order success rate)

OUTPUT DATA:
  Health status              (GREEN / YELLOW / RED / BLACK)
  Failover commands          (pause trading, switch platform, alert operator)
```

#### Core Logic/Math

**Multi-Tier Health Assessment:**

```
health_score = weighted average of:
  0.25 * heartbeat_regularity   (1.0 if on-time, decays to 0 if >3 missed)
  0.20 * exchange_connectivity  (1.0 if latency < 500ms, 0 if > 5000ms)
  0.20 * execution_success_rate (rolling 10 orders)
  0.15 * resource_utilization   (1.0 if CPU < 80%, GPU < 90%, RAM < 85%)
  0.10 * error_frequency        (1.0 if < 1/hour, 0 if > 10/hour)
  0.10 * data_quality           (1.0 if Sentinel score > 0.7 on average)

Status mapping:
  score >= 0.80:  GREEN   (all systems nominal)
  score >= 0.60:  YELLOW  (degraded but operational)
  score >= 0.30:  RED     (critical issues, reduce trading)
  score < 0.30:   BLACK   (system failure, failover or halt)
```

**Heartbeat Watchdog:**

```
expected_heartbeat_interval = 60 seconds
max_missed = 3

On each tick (every 10 seconds):
  elapsed = now - last_heartbeat_received
  if elapsed > expected_interval * 2:
    missed_count += 1
  if missed_count >= max_missed:
    BUNKER_FAILOVER_TRIGGERED(reason="heartbeat_timeout")
```

**Failover Protocol:**

```
Level 1 (YELLOW): Log warning, increase monitoring frequency to 10s
Level 2 (RED):    Close all open positions, halt new trades
                   Send Telegram alert to operator
Level 3 (BLACK):  Execute emergency close-all via exchange API
                   If primary platform unresponsive for > 5 minutes:
                     Activate secondary platform (if configured)
                   Send CRITICAL alert with full status dump
```

**Cross-Platform Architecture:**

```
Primary:    Windows PC (RTX A3000M) — full system
Secondary:  Mac (M-series) — lightweight monitoring + emergency close
Tertiary:   Cloud VPS — API-only emergency position closure

Communication: HTTP health endpoint + SQLite shared state file
(synced via file system or simple HTTP polling)

Each platform runs a Bunker instance. The primary Bunker is the
authority. Secondary/tertiary Bunkers only activate when primary
fails heartbeat for > 5 minutes.
```

**Recovery Protocol:**

```
When primary recovers after failover:
  1. Secondary Bunker publishes BUNKER_RECOVERY_INITIATED
  2. Primary syncs state: current positions, equity, kill switch level
  3. Primary validates: positions match exchange records
  4. If consistent: BUNKER_RECOVERY_COMPLETE, secondary stands down
  5. If inconsistent: ALERT operator, remain in dual-monitor mode
```

#### GPU Utilization

**None.** Bunker is pure monitoring and control logic.
Must not depend on GPU availability (GPU failure is a monitored condition).

#### Integration Points

| Target Module | Direction | Data | Trigger |
|---|---|---|---|
| Every module | <-- monitors | heartbeats, errors | Continuously |
| Kill Switch | <-- coordinates | risk level | On escalation |
| Executioner | --> commands | Emergency close-all | On BLACK status |
| Chaos Engine | <-- receives | worst-case scenarios | For failover threshold calibration |
| Telegram bot | --> sends | alerts | On YELLOW/RED/BLACK |
| Sentinel | <-- receives | data quality trend | For health score |

---

## 8. Cross-Cluster Data Flow

### 8.1 The Full Pipeline Loop (v2.5)

```
TICK (Candle Close)
  |
  v
[Cluster 5: Sentinel] ----data quality----> Gate 0
  |
  v
[Cluster 2: Harbinger] ---cross-asset---->
[Cluster 2: Seer]      ---on-chain------>  State enrichment
[Cluster 2: Hermes]    ---sentiment----->
  |
  v
[Feature Builder] ----53 features----> FeatureVector
  |
  v
[Regime Detector] ----RegimeState----> Gate 1 (CRISIS check)
  |
  v
[Cluster 1: Oracle] ---forecast---->
  |                                    Signal generation
[Engine Router: Titan/Nautilus/Phoenix + Hermes override]
  |
  v
[Cluster 4: Hive] ----consensus----> Gate 5+ (confidence boost/veto)
  |
  v
[MDE Gates 0-7] ----approved signal---->
  |
  v
[Cluster 3: Chiron] ---leverage---->
[Cluster 4: Hyper-Sizer] ---position size----> Decision
  |
  v
[Cluster 5: Chaos Engine] ---VaR check----> Final risk gate
  |
  v
[Cluster 3: Executioner / Ghost] ---fill---->
  |
  v
[Telemetry] ----TradeRecord---->
  |
  v
[Cluster 1: Reflector] ----CorrectionVector---->
  |                          |                    |
  v                          v                    v
[Cluster 1: Darwin]    [Chiron update]    [Auditor log]
  |
  v
[Genome Promoted] ---new params---> Engines (next tick)
```

### 8.2 The Three Feedback Loops

**Loop 1: Fast Correction (per-trade, ~seconds)**
```
Trade closes -> Reflector -> CorrectionVector -> Chiron weight nudge
Latency: immediate (same candle)
Effect: Next trade has adjusted engine weights
```

**Loop 2: Micro-Evolution (per failure pattern, ~days)**
```
Reflector tracks failure modes -> threshold hit (5 of same in 20 trades)
  -> Darwin.micro_evolve() -> targeted genome mutation
  -> if improved: GENOME_PROMOTED -> engine parameters updated
Latency: 1-5 days (depends on trade frequency)
Effect: Indicator periods and thresholds adapted to current market
```

**Loop 3: Full Evolution (periodic, ~weekly)**
```
Weekly scheduler -> Darwin.full_evolve() -> population-wide GA cycle
  -> best genome promoted -> engine parameters updated
Simultaneously: Regenerator -> retrain ML models -> Oracle/LightGBM updated
  -> Auditor evaluates -> alpha decay check -> triggers next cycle if needed
Latency: 7 days
Effect: System-wide parameter refresh, model refresh
```

### 8.3 Priority Interrupt Chain

```
Priority 0 (CRITICAL): Kill switch -> Bunker failover -> Ghost cancel-all
  Override: Everything stops. No trades. Close positions if needed.

Priority 1 (HIGH): Hermes CRITICAL veto -> Chaos Engine survival=false
  Override: Halt new trades, tighten stops on open positions.

Priority 2 (NORMAL): Standard pipeline flow
  Normal operation: Generate signal, size, execute.

Priority 3 (LOW): Darwin evolution, Regenerator retraining, Auditor reports
  Background: Never interrupts trading, runs in spare cycles.

Priority 4 (BACKGROUND): Seer polling, Harbinger correlation update
  Asynchronous: Updates state for next candle, no urgency.
```

---

## 9. GPU Memory Budget (RTX A3000M — 6 GB VRAM)

```
+----------------------------------------------+
|          RTX A3000M — 6144 MB VRAM           |
+----------------------------------------------+
|                                              |
|  RESIDENT (always loaded):                   |
|    Chronos-Bolt inference    ~280 MB         |
|    Chiron SAC networks       ~ 15 MB         |
|    CUDA runtime overhead     ~300 MB         |
|    TOTAL RESIDENT:           ~595 MB         |
|                                              |
|  INFERENCE SPIKES:                           |
|    Chronos batch (5 symbols) ~400 MB temp    |
|    LightGBM GPU inference    ~ 50 MB temp    |
|    Chaos Engine Monte Carlo  ~200 MB temp    |
|    PEAK INFERENCE:           ~1245 MB        |
|                                              |
|  TRAINING (exclusive, scheduled):            |
|    Chronos fine-tune         ~1500 MB        |
|    (unloads inference model first)           |
|    LightGBM retrain          ~ 800 MB        |
|    Chiron SAC training       ~  50 MB        |
|    PEAK TRAINING:            ~2650 MB        |
|                                              |
|  RESERVED FOR OS/DISPLAY:    ~500 MB         |
|                                              |
|  SUMMARY:                                    |
|    Normal operation (inference): ~1.7 GB     |
|    Training mode:                ~3.2 GB     |
|    Headroom:                     ~2.9 GB     |
|                                              |
+----------------------------------------------+

CONTENTION RULES:
  1. Hermes LLM (Ollama) does NOT run on local GPU.
     Use Groq API for LLM inference (zero VRAM).
  2. Regenerator training unloads Chronos inference first.
  3. Training never runs during active trading candle processing.
  4. Chaos Engine Monte Carlo runs after inference, before training.
```

---

## 10. Deployment Topology

### 10.1 Build Order (Dependency-Aware)

```
Phase 0: Foundation (EXISTS)
  src/core/*, src/data/*, src/regime/*, src/mde/*
  src/engines/titan, nautilus, phoenix, hermes
  src/execution/executor.py, src/risk/kill_switch.py, src/risk/pre_trade.py

Phase 1: Core Intelligence (EXISTS, integrate)
  src/learning/darwin.py      <- Integrate with pipeline step 10
  src/learning/reflector.py   <- Integrate with POSITION_CLOSED event
  src/risk/sizing.py          <- Replace mde/sizing.py in pipeline step 8

Phase 2: Enhanced Perception (NEW, parallel build)
  src/perception/harbinger.py <- Needs multi-asset data adapters
  src/perception/seer.py      <- Needs on-chain API integration
  src/intelligence/chiron.py  <- Needs replay buffer + pre-training

Phase 3: Execution Upgrade (NEW, sequential)
  src/execution/executor.py   <- Extend with smart limit + TWAP
  src/execution/ghost.py      <- Needs orderbook depth feed

Phase 4: Ensemble & Stress (NEW, parallel build)
  src/consensus/hive.py       <- Depends on Harbinger + Seer
  src/risk/chaos_engine.py    <- Independent, needs historical crisis data

Phase 5: Lifecycle & Safety (NEW, parallel build)
  src/ml/regenerator.py       <- Depends on Oracle + backtest infra
  src/analytics/auditor.py    <- Depends on Reflector + telemetry
  src/ops/bunker.py           <- Independent, cross-platform

Phase 6: Integration Testing
  End-to-end backtest with all 15 modules active
  Paper trading validation (minimum 200 trades)
  Stress test with Chaos Engine scenarios
```

### 10.2 File System Layout (Target)

```
src/
  core/           # types, config, events, clock, constants, protocols, hardware
  data/           # features, sentinel, data store
  regime/         # rule-based, consensus, state machine
  engines/        # titan, nautilus, phoenix, hermes, atlas
  mde/            # gates, router, sizing (v2.0 compat)
  perception/     # harbinger.py, seer.py          [NEW CLUSTER 2]
  intelligence/   # chiron.py (v2, RL-based)        [NEW CLUSTER 3]
  consensus/      # hive.py                         [NEW CLUSTER 4]
  execution/      # executor.py, ghost.py           [EXTENDED CLUSTER 3]
  risk/           # sizing.py, kill_switch.py, pre_trade.py, chaos_engine.py
  learning/       # darwin.py, reflector.py          [CLUSTER 1]
  ml/             # chronos/, lgbm/, meta_label/, regenerator.py
  analytics/      # auditor.py                       [NEW CLUSTER 1]
  portfolio/      # allocator.py
  telemetry/      # event_logger.py
  ops/            # bunker.py                        [NEW CLUSTER 5]
  backtest/       # engine, metrics, lab/
```

---

*End of Blueprint — ARGUS Singularity v2.5*
*15 modules. 5 clusters. One recursive learning loop.*
