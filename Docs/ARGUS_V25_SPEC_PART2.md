# ARGUS v2.5 — SPEC PART 2: Schemas + Algorithm Specs

---

## 3. SQLITE SCHEMAS

### 3.1 trades

```sql
CREATE TABLE trades (
  trade_id          TEXT PRIMARY KEY,
  symbol            TEXT NOT NULL,
  side              TEXT NOT NULL CHECK(side IN ('long','short')),
  capital_engine    TEXT NOT NULL CHECK(capital_engine IN ('core','accel')),
  entry_time        TEXT NOT NULL,     -- ISO8601
  exit_time         TEXT,              -- NULL if open
  entry_price       REAL NOT NULL,
  exit_price        REAL,
  size              REAL NOT NULL,
  pnl               REAL,
  pnl_pct           REAL,
  fees              REAL DEFAULT 0,
  slippage          REAL DEFAULT 0,
  net_pnl_pct       REAL,
  regime_at_entry   TEXT NOT NULL,
  regime_at_exit    TEXT,
  engine            TEXT NOT NULL,
  sub_strategy      TEXT NOT NULL,
  confidence        REAL NOT NULL,
  sqs_score         REAL NOT NULL,
  stop_distance     REAL NOT NULL,
  duration_hours    REAL,
  reason_entry      TEXT NOT NULL,
  reason_exit       TEXT,
  features_json     TEXT,              -- JSON blob of FeatureVector at entry
  config_hash       TEXT,              -- SHA256 of config at trade time
  created_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_engine ON trades(engine);
CREATE INDEX idx_trades_time ON trades(entry_time);
CREATE INDEX idx_trades_capital ON trades(capital_engine);
```

### 3.2 decisions

```sql
CREATE TABLE decisions (
  decision_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id            TEXT NOT NULL,
  timestamp         TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  action            TEXT NOT NULL,
  capital_engine    TEXT NOT NULL,
  position_size_pct REAL,
  leverage          REAL,
  stop_loss_pct     REAL,
  confidence        REAL,
  sqs_score         REAL,
  engine            TEXT,
  sub_strategy      TEXT,
  regime            TEXT NOT NULL,
  reason            TEXT NOT NULL,
  gate_results_json TEXT,              -- JSON: which gates passed/failed
  inputs_hash       TEXT               -- SHA256 of MarketSnapshot
);

CREATE INDEX idx_decisions_time ON decisions(timestamp);
CREATE INDEX idx_decisions_regime ON decisions(regime);
```

### 3.3 ledger

```sql
CREATE TABLE ledger (
  event_id          TEXT PRIMARY KEY,
  event_type        TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  capital_engine    TEXT NOT NULL,
  amount            REAL NOT NULL,     -- signed
  balance_after     REAL NOT NULL,
  equity_after      REAL NOT NULL,
  position_id       TEXT,
  metadata_json     TEXT,
  timestamp         TEXT NOT NULL
);

CREATE INDEX idx_ledger_time ON ledger(timestamp);
CREATE INDEX idx_ledger_type ON ledger(event_type);
CREATE INDEX idx_ledger_engine ON ledger(capital_engine);
```

### 3.4 kill_switch_state

```sql
CREATE TABLE kill_switch_state (
  id                INTEGER PRIMARY KEY CHECK(id = 1),  -- singleton row
  level             INTEGER NOT NULL DEFAULT 0,
  entered_at        TEXT NOT NULL,
  reason            TEXT NOT NULL,
  dd_at_entry       REAL NOT NULL DEFAULT 0.0,
  last_escalation   TEXT,
  last_de_escalation TEXT,
  updated_at        TEXT DEFAULT (datetime('now'))
);
```

### 3.5 sqs_log

```sql
CREATE TABLE sqs_log (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp         TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  total_score       REAL NOT NULL,
  regime_consistency REAL NOT NULL,
  trend_structure   REAL NOT NULL,
  microstructure    REAL NOT NULL,
  fee_adj_expectancy REAL NOT NULL,
  hermes_news_risk  REAL NOT NULL,
  threshold_used    REAL NOT NULL,
  passed            INTEGER NOT NULL,  -- 0/1
  reason_if_failed  TEXT
);

CREATE INDEX idx_sqs_time ON sqs_log(timestamp);
CREATE INDEX idx_sqs_passed ON sqs_log(passed);
```

### 3.6 regime_history

```sql
CREATE TABLE regime_history (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp         TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  regime            TEXT NOT NULL,
  sub_regime        TEXT,
  confidence        REAL NOT NULL,
  stability         REAL NOT NULL,
  direction         INTEGER,
  candles_in_regime INTEGER NOT NULL,
  trigger_reason    TEXT
);

CREATE INDEX idx_regime_time ON regime_history(timestamp);
```

### 3.7 counterfactuals

```sql
CREATE TABLE counterfactuals (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp         TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  signal_json       TEXT NOT NULL,     -- full Signal contract as JSON
  sqs_score         REAL NOT NULL,
  reject_reason     TEXT NOT NULL,
  reject_gate       TEXT NOT NULL,     -- which gate rejected
  theoretical_entry REAL NOT NULL,
  theoretical_exit  REAL,              -- filled after 24h
  theoretical_pnl   REAL,             -- filled after 24h
  resolved          INTEGER DEFAULT 0  -- 0/1
);

CREATE INDEX idx_cf_time ON counterfactuals(timestamp);
CREATE INDEX idx_cf_resolved ON counterfactuals(resolved);
```

### 3.8 edge_health

```sql
CREATE TABLE edge_health (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp         TEXT NOT NULL,
  engine            TEXT NOT NULL,
  sub_strategy      TEXT NOT NULL,
  rolling_sharpe_30 REAL,
  rolling_winrate_30 REAL,
  rolling_pf_30     REAL,             -- profit factor
  avg_rr_30         REAL,             -- avg reward:risk
  trade_count_30    INTEGER,
  status            TEXT NOT NULL,     -- "HEALTHY"|"DEGRADED"|"RETIRED"
  decay_score       REAL              -- [0.0-1.0], 0=healthy, 1=dead
);

CREATE INDEX idx_edge_engine ON edge_health(engine);
```

### 3.9 experiment_versions

```sql
CREATE TABLE experiment_versions (
  version_id        TEXT PRIMARY KEY,
  created_at        TEXT NOT NULL,
  config_hash       TEXT NOT NULL,
  parameter_json    TEXT NOT NULL,     -- full param snapshot
  parent_version    TEXT,              -- NULL for initial
  change_desc       TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'candidate',  -- candidate|active|retired
  min_trades_before_eval INTEGER DEFAULT 30,
  activated_at      TEXT,
  retired_at        TEXT,
  retire_reason     TEXT
);
```

---

## 4. TIME MACHINE SCHEMA

The Time Machine replays historical data through the full pipeline to validate strategies.

### 4.1 backtest_runs

```sql
CREATE TABLE backtest_runs (
  run_id            TEXT PRIMARY KEY,
  start_date        TEXT NOT NULL,
  end_date          TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  config_hash       TEXT NOT NULL,
  strategy_version  TEXT NOT NULL,
  initial_capital   REAL NOT NULL,
  final_capital     REAL NOT NULL,
  total_return_pct  REAL NOT NULL,
  sharpe_ratio      REAL,
  sortino_ratio     REAL,
  max_drawdown_pct  REAL NOT NULL,
  total_trades      INTEGER NOT NULL,
  win_rate          REAL,
  profit_factor     REAL,
  avg_trade_pnl_pct REAL,
  avg_duration_h    REAL,
  regime_distribution_json TEXT,       -- {"TREND":0.4,"CHOP":0.3,...}
  engine_pnl_json   TEXT,              -- {"TITAN":1200,"NAUTILUS":800,...}
  fees_total        REAL,
  slippage_total    REAL,
  walk_forward_fold INTEGER,           -- NULL if not WF
  created_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_bt_strategy ON backtest_runs(strategy_version);
CREATE INDEX idx_bt_dates ON backtest_runs(start_date, end_date);
```

### 4.2 backtest_trades

```sql
CREATE TABLE backtest_trades (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id            TEXT NOT NULL REFERENCES backtest_runs(run_id),
  trade_id          TEXT NOT NULL,
  symbol            TEXT NOT NULL,
  side              TEXT NOT NULL,
  capital_engine    TEXT NOT NULL,
  entry_time        TEXT NOT NULL,
  exit_time         TEXT NOT NULL,
  entry_price       REAL NOT NULL,
  exit_price        REAL NOT NULL,
  size              REAL NOT NULL,
  pnl               REAL NOT NULL,
  pnl_pct           REAL NOT NULL,
  net_pnl_pct       REAL NOT NULL,
  fees              REAL NOT NULL,
  slippage          REAL NOT NULL,
  regime_at_entry   TEXT NOT NULL,
  engine            TEXT NOT NULL,
  sub_strategy      TEXT NOT NULL,
  sqs_score         REAL NOT NULL,
  confidence        REAL NOT NULL,
  stop_distance     REAL NOT NULL,
  reason_entry      TEXT,
  reason_exit       TEXT
);

CREATE INDEX idx_bt_trades_run ON backtest_trades(run_id);
```

### 4.3 backtest_equity_curve

```sql
CREATE TABLE backtest_equity_curve (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id            TEXT NOT NULL REFERENCES backtest_runs(run_id),
  timestamp         TEXT NOT NULL,
  equity            REAL NOT NULL,
  drawdown_pct      REAL NOT NULL,
  regime            TEXT NOT NULL,
  kill_switch_level INTEGER NOT NULL
);

CREATE INDEX idx_bt_eq_run ON backtest_equity_curve(run_id);
```

### 4.4 walk_forward_results

```sql
CREATE TABLE walk_forward_results (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  experiment_id     TEXT NOT NULL,
  fold              INTEGER NOT NULL,
  train_start       TEXT NOT NULL,
  train_end         TEXT NOT NULL,
  test_start        TEXT NOT NULL,
  test_end          TEXT NOT NULL,
  in_sample_sharpe  REAL NOT NULL,
  oos_sharpe        REAL NOT NULL,
  oos_return_pct    REAL NOT NULL,
  oos_max_dd_pct    REAL NOT NULL,
  oos_trades        INTEGER NOT NULL,
  oos_win_rate      REAL,
  degradation_ratio REAL,             -- oos_sharpe / is_sharpe
  purge_gap_days    INTEGER NOT NULL DEFAULT 5,
  created_at        TEXT DEFAULT (datetime('now'))
);
```

### Time Machine Invariants

```
1. Fee model MUST use 2x estimated costs (pessimistic).
2. Slippage model: 0.02% base + 0.01% per $10k notional.
3. Walk-forward: minimum 5 folds, purge gap = 5 days.
4. No lookahead bias: features computed only from data available at signal time.
5. Regime detection uses same state machine as live (same confirmation windows).
6. Monte Carlo: 1000 permutations of trade sequence.
7. Pass criteria: OOS Sharpe > 0 on >= 4 of 5 folds.
```

---

## 5. ALGORITHM SPECIFICATIONS

### 5.1 Darwin (Genetic Algorithm Parameter Optimizer)

**Purpose:** Evolve strategy parameters offline to find robust parameter sets.

**Inputs:**
- `parameter_space`: dict of {param_name: (min, max, step)}
- `historical_data`: OHLCV + features for backtest period
- `fitness_function`: see below

**Configuration:**
```
population_size:    30
elite_count:        3      # top N survive unchanged
tournament_size:    3      # tournament selection
crossover_rate:     0.70   # probability of crossover
base_mutation_rate: 0.15   # per-gene mutation probability
mutation_strength:  0.20   # max mutation as fraction of range
full_evolution_interval: 168 hours (weekly)
micro_evolution_trigger: 5 consecutive losses
micro_evolution_lookback: 20 trades
```

**Fitness Function:**
```
fitness = sortino_ratio × sqrt(trade_count / 100) × (1 - max_dd / 0.12)

WHERE:
  sortino_ratio    = annualized excess return / downside deviation
  trade_count      = number of trades in evaluation window
  max_dd           = maximum drawdown in evaluation window
  
CONSTRAINTS (hard, any violation → fitness = -999):
  max_dd           > 0.12  → REJECT
  trade_count      < 10    → REJECT
  profit_factor    < 1.0   → REJECT
```

**Algorithm (per generation):**
```
1. EVALUATE: Run backtest for each individual → fitness score
2. SORT: Rank by fitness descending
3. ELITE: Copy top elite_count to next generation unchanged
4. SELECT: Tournament selection for remaining slots
   - Pick tournament_size random individuals
   - Winner = highest fitness
5. CROSSOVER: For each pair of selected parents:
   - If random() < crossover_rate: uniform crossover (50/50 per gene)
   - Else: clone parent1
6. MUTATE: For each gene in child:
   - If random() < mutation_rate: 
     gene += uniform(-mutation_strength, +mutation_strength) × (max - min)
     gene = clamp(gene, min, max)
     gene = round_to_step(gene, step)
7. REPEAT until max_generations or convergence (top fitness stable for 5 gens)
```

**Anti-Overfitting Rules:**
```
1. Train period: 60% of data
2. Validation period: 20% of data (param selection)
3. Test period: 20% of data (final evaluation, NEVER used for selection)
4. Purge gap: 5 days between train/validation/test
5. Fitness evaluated on VALIDATION set, not train
6. If validation fitness < 0.5 × train fitness → OVERFIT, reject
7. Final candidate tested on test set. If test < 0.7 × validation → REJECT
```

**Output:** `ExperimentVersion` with optimized parameter set

---

### 5.2 Reflector (Bounded Self-Adjustment)

**Purpose:** After losses, compute a bounded adjustment vector. NOT a full reoptimization — just targeted parameter shifts within safe bounds.

**Trigger Conditions (ANY one):**
```
1. Single trade loss > loss_threshold (-0.2%)
2. Rolling 20-trade win rate < underperformance_ratio (30%)  
3. 5+ consecutive losing trades (micro_evolution_threshold)
```

**AdjustmentVector Definition:**
```
AdjustmentVector:
  stop_multiplier_delta:    float  # [-0.3, +0.3]  relative to current
  confidence_threshold_delta: float # [-0.05, +0.05]
  position_size_mult:       float  # [0.5, 1.0] — can only REDUCE, never increase
  cooldown_candles:         int    # [0, 12] — forced wait after adjustment
  regime_filter_tighten:    bool   # if true, require 1 extra confirmation candle
```

**Algorithm:**
```
1. DETECT: Check trigger conditions after every trade close
2. DIAGNOSE: Analyze last 20 trades:
   a. loss_by_regime = group losses by regime → identify worst regime
   b. loss_by_engine = group losses by engine → identify worst engine  
   c. avg_stop_hit_pct = fraction of trades hitting SL
   d. avg_entry_quality = mean SQS at entry for losing trades
3. PRESCRIBE (bounded adjustments):
   IF avg_stop_hit_pct > 0.6:
     stop_multiplier_delta = +0.15 (widen stops)
   IF avg_entry_quality < 0.5:
     confidence_threshold_delta = +0.03 (be more selective)
   IF loss streak >= 5:
     position_size_mult = 0.7 (reduce size 30%)
     cooldown_candles = 6
   IF worst_regime losses > 2x avg:
     regime_filter_tighten = true
4. APPLY: Merge AdjustmentVector with current params
5. LOG: Record adjustment in experiment_versions with parent link
6. EXPIRY: Adjustment auto-reverts after 50 trades if performance recovers
```

**Hard Constraints:**
```
- Reflector can NEVER increase position size above current config
- Reflector can NEVER decrease stop distance
- Reflector can NEVER lower confidence thresholds
- Reflector changes are logged as new experiment_version
- Minimum 30 trades before ANY Reflector action (prevents adjustment on noise)
- Maximum 3 active adjustments at once (prevents cascading micro-changes)
```

---

### 5.3 HyperSizer (Adaptive Position Sizer)

**Purpose:** Growth-phase-aware position sizing. Uses equity level to determine risk appetite.

**Phase Definitions (from config):**
```
SURVIVAL:       equity [0, 2000]        kelly_frac=0.30  max_lev=1.0  max_risk=1.5%
FOUNDATION:     equity [2000, 10000]    kelly_frac=0.50  max_lev=1.5  max_risk=2.5%
GROWTH:         equity [10000, 50000]   kelly_frac=0.75  max_lev=2.0  max_risk=3.5%
ACCELERATION:   equity [50000, 200000]  kelly_frac=1.00  max_lev=2.5  max_risk=4.5%
COMPOUNDING:    equity [200000, ∞)      kelly_frac=0.85  max_lev=2.0  max_risk=3.5%
```

**Algorithm:**
```
FUNCTION compute_size(equity, signal, regime, sqs_score, portfolio_state):
  
  1. phase = determine_phase(equity)
  
  2. base_risk = phase.max_risk
  
  3. conviction = min(
       signal.confidence × sqs_score × regime.confidence,
       phase.conviction_cap
     )
  
  4. IF portfolio_state.consecutive_losses >= 3:
       cold_streak_mult = max(0.3, 1.0 - cold_streak_decay_rate × consecutive_losses)
     ELSE:
       cold_streak_mult = 1.0
  
  5. equity_floor_mult = sigmoid_floor(
       equity / peak_equity, 
       floor = hard_floor_pct,
       steepness = hard_floor_decay_steepness
     )
     // Returns 1.0 when equity >> floor, approaches 0.0 near floor
  
  6. risk_per_trade = base_risk × conviction × cold_streak_mult 
                      × equity_floor_mult × atlas_mult × dd_mult × rsl_mult
  
  7. risk_per_trade = clamp(risk_per_trade, 0.005, phase.max_risk)
  
  8. position_size = risk_per_trade / signal.stop_distance
     position_size = clamp(position_size, 0.0, 0.15)
  
  9. leverage = min(position_size / available_margin_pct, phase.max_lev)
  
  10. RETURN SizingDecision(...)
```

**Sigmoid Floor Function:**
```
sigmoid_floor(ratio, floor, steepness):
  IF ratio <= floor: RETURN 0.0
  x = (ratio - floor) / (1.0 - floor)  // normalize to [0,1]
  RETURN 1.0 / (1.0 + exp(-steepness × (x - 0.5)))
```

**Accel Engine Override:**
```
IF capital_engine == "accel":
  REQUIRE regime.sub_regime == "STRONG_TREND"
  REQUIRE alignment_score >= 0.95
  REQUIRE sqs_score >= 0.85
  REQUIRE kill_switch_level == 0
  leverage_cap = 3.0 (instead of phase cap)
  position_pool = 0.20 × total_equity (NOT the core 80%)
  // Accel losses still count toward global drawdown
```

---

### 5.4 SignalQualityGate (SQS)

**Purpose:** Score every potential trade on a [0.0–1.0] scale BEFORE it enters the engine pipeline. Low-quality setups are rejected with full counterfactual logging.

**Component Scores (5 dimensions):**

```
1. REGIME CONSISTENCY (weight=0.25):
   score = regime.stability × regime.confidence
   IF candles_in_regime < 6: score × 0.5  (new regime penalty)
   IF pending_transition != None: score × 0.3  (unstable regime)

2. TREND/RANGE STRUCTURE (weight=0.20):
   IF regime == TREND:
     score = normalize(adx_14, 20, 60) × directional_alignment
     WHERE directional_alignment = 1.0 if price > EMA21 > EMA55 (or reverse for short)
                                    0.5 if partial alignment
                                    0.0 if no alignment
   IF regime == CHOP:
     distance_from_mid = abs(close - chop_midpoint) / atr_14
     score = clamp(distance_from_mid / 2.0, 0.0, 1.0)
     // Higher score when FURTHER from midpoint (near bands)
   IF regime == VOLATILE:
     score = 0.5 (neutral — PHOENIX carry doesn't depend on structure)

3. MICROSTRUCTURE QUALITY (weight=0.20):
   obi_score = normalize(abs(orderbook_imbalance), 0, 0.5)
   // Higher imbalance in signal direction = better
   IF orderbook_imbalance sign matches signal.bias: obi_score = obi_score
   ELSE: obi_score = 1.0 - obi_score
   
   volume_score = normalize(volume_ratio, 0.5, 3.0)
   spread_score = 1.0 - normalize(spread_pct, 0.0, 0.003)
   
   score = 0.4 × obi_score + 0.3 × volume_score + 0.3 × spread_score

4. FEE-ADJUSTED EXPECTANCY (weight=0.20):
   gross_ev = signal.expected_return
   round_trip_cost = 0.0013  // from Constitution 13.5
   net_ev = gross_ev - round_trip_cost
   
   IF net_ev <= 0: score = 0.0
   ELSE: score = normalize(net_ev, 0.0, 0.02)
   
   rr_ratio = signal.take_profit_distance / signal.stop_distance
   IF rr_ratio < 1.5: score × 0.5

5. HERMES NEWS RISK (weight=0.15):
   IF no_recent_news: score = 0.7 (neutral baseline)
   IF positive_sentiment AND matches_signal_direction: score = 0.9
   IF negative_sentiment OR critical_news: score = 0.1
   IF regulatory_news: score = 0.0
   // Hermes LLM outputs sentiment [-100, +100], normalize to [0,1]
```

**Composite Score:**
```
total = 0.25 × regime_consistency
      + 0.20 × trend_structure  
      + 0.20 × microstructure
      + 0.20 × fee_adj_expectancy
      + 0.15 × hermes_news_risk
```

**Threshold Logic:**
```
IF regime == TREND AND sub_regime == STRONG_TREND:
  threshold = 0.55   (more permissive in strong trends)
ELIF regime == TREND:
  threshold = 0.60
ELIF regime == CHOP:
  threshold = 0.70   (higher bar in chop — only best setups)
ELIF regime == VOLATILE:
  threshold = 0.65
ELIF regime == CRISIS:
  threshold = 1.01   (impossible — no trades in crisis)
```

**On Rejection:**
```
1. Log full SignalQualityScore to sqs_log table
2. Log signal to counterfactuals table with theoretical_entry price
3. After 24h, fill theoretical_exit and theoretical_pnl
4. This counterfactual data feeds Reflector and Edge Health Monitor
```

---

*Continued in ARGUS_V25_SPEC_PART3.md*
