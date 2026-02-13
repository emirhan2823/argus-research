# ARGUS v2.5 — SPEC PART 3: CHOP Rules, Acceptance Tests, Implementation Plan

---

## 5.5 CHOP Regime Rules (Mandatory)

**CHOP replaces RANGING from v2.0.** Same concept, stricter rules.

### CHOP Detection

```
CHOP is declared when ALL of:
  ADX(14) < 20
  Hurst exponent < 0.45
  Price within BB(20,2) for 20+ bars
  No active VOLATILE or CRISIS triggers
```

### CHOP Trading Rules

```
RULE 1: MEAN-REVERSION PREFERRED
  Lead engine: NAUTILUS (bb_reversion, funding_reversion)
  TITAN is DISABLED in CHOP
  Bias: fade extremes, trade toward mid

RULE 2: NO-TRADE ZONE (MIDPOINT)
  chop_midpoint = (BB_upper + BB_lower) / 2
  dead_zone = chop_midpoint ± 0.3 × ATR(14)
  IF close is within dead_zone:
    action = HOLD
    reason = "Price in CHOP midpoint dead zone"
  ONLY trade when price is near BB bands (outer 30% of range)

RULE 3: FALSE BREAKOUT FILTER
  IF close > BB_upper AND volume_ratio < 1.2:
    IGNORE breakout signal — likely false
    Log as counterfactual
  IF close below BB_upper within 2 candles of "breakout":
    Confirm false breakout → fade signal valid
  Same logic applies for downside (close < BB_lower)

RULE 4: LIMIT-ORDER-FIRST
  In CHOP, default order type = PASSIVE_LIMIT
  NO market orders unless kill_switch triggered
  Urgency forced to LOW or NORMAL (never HIGH)
  Timeout = 5 minutes, cancel if not filled

RULE 5: REDUCED LEVERAGE
  max_leverage_in_chop = 1.0
  position_size_mult = 0.6  (60% of normal sizing)

RULE 6: TIGHTER STOPS
  nautilus_bb_reversion stop_mult = 0.8 × ATR (tighter than normal 1.0)
  IF trade goes 0.5 × ATR in profit → move SL to breakeven
```

### Accel Engine in CHOP

```
Acceleration Engine is ALWAYS DISABLED in CHOP.
No exceptions. No override. Accel requires STRONG_TREND sub-regime.
```

---

## 6. ACCEPTANCE TESTS

### 6.1 Risk Layer Tests

```
TEST-R01: Equity Floor
  GIVEN equity = $1000, peak = $2000, hard_floor_pct = 0.60
  WHEN equity drops to $1200 (ratio = 0.60 = floor exactly)
  THEN position_size_mult → 0.0 (sigmoid returns ~0)
  AND no new trades permitted
  AND all existing positions begin trailing-stop tightening

TEST-R02: Max Drawdown Kill
  GIVEN peak_equity = $5000
  WHEN equity drops to $4400 (DD = 12%)
  THEN kill_switch escalates to LOCKDOWN (level 4)
  AND ALL positions closed at market immediately
  AND system halts INDEFINITELY
  AND alert sent on ALL channels

TEST-R03: Daily Loss Cap
  GIVEN daily_pnl = -2.6%
  WHEN next candle triggers signal evaluation
  THEN hard_cap exceeded (-2.5%)
  AND kill_switch escalates to HALT (level 3)
  AND ALL positions closed
  AND system halts 24h minimum

TEST-R04: Per-Trade Risk Cap
  GIVEN signal requests risk_per_trade = 4%
  WHEN HyperSizer computes position size
  THEN risk_per_trade clamped to max 3%
  AND log: "Risk clamped from 4.0% to 3.0%"

TEST-R05: Risk Overrides Everything
  GIVEN TITAN generates high-confidence LONG signal, SQS = 0.95
  WHEN kill_switch_level = 3 (HALT)
  THEN trade REJECTED regardless of signal quality
  AND reason = "Kill switch HALT — no new trades"
```

### 6.2 SQS Gate Tests

```
TEST-SQS01: Full Pass
  GIVEN regime = TREND, confidence = 0.8, stability = 0.9
  AND adx = 35, price > EMA21 > EMA55
  AND OBI = 0.3 matching signal direction, volume_ratio = 2.0
  AND expected return = 1.5%, round_trip_cost = 0.13%
  AND hermes sentiment = neutral
  WHEN SQS computes score
  THEN total_score >= 0.60 (TREND threshold)
  AND passed = true

TEST-SQS02: CHOP High Bar
  GIVEN regime = CHOP, threshold = 0.70
  AND regime_consistency = 0.6 (mediocre)
  AND trend_structure = 0.4 (price near midpoint)
  AND microstructure = 0.5 (average)
  WHEN SQS computes
  THEN total_score < 0.70
  AND passed = false
  AND counterfactual logged

TEST-SQS03: News Risk Veto
  GIVEN all other components score > 0.8
  AND hermes detects critical regulatory news (score = 0.0)
  WHEN SQS computes
  THEN hermes_news_risk contribution = 0.0
  AND total_score reduced by 0.15 × 0.8 = 0.12
  AND IF this drops below threshold → trade rejected
  AND reason includes "critical news risk"

TEST-SQS04: Counterfactual Tracking
  GIVEN SQS rejects signal at price $50,000
  WHEN 24 hours elapse
  THEN counterfactuals table updated with theoretical_exit
  AND theoretical_pnl calculated
  AND resolved = 1
```

### 6.3 Regime Tests

```
TEST-REG01: CHOP Midpoint Dead Zone
  GIVEN regime = CHOP
  AND BB_upper = 52000, BB_lower = 48000
  AND chop_midpoint = 50000, ATR = 500
  AND dead_zone = [49850, 50150]
  WHEN close = 50050 (inside dead zone)
  THEN action = HOLD
  AND reason = "Price in CHOP midpoint dead zone"

TEST-REG02: CHOP False Breakout Filter
  GIVEN regime = CHOP, BB_upper = 52000
  AND close = 52100 (above BB_upper)
  AND volume_ratio = 0.9 (< 1.2 threshold)
  WHEN signal evaluation runs
  THEN breakout signal IGNORED
  AND logged as potential false breakout

TEST-REG03: STRONG_TREND Sub-Regime
  GIVEN regime = TREND
  AND adx = 40, alignment = price > EMA21 > EMA55 > EMA200
  AND candles_in_regime >= 12
  AND regime.confidence >= 0.85
  WHEN regime sub-classification runs
  THEN sub_regime = "STRONG_TREND"
  AND accel_eligible = true (pending SQS check)

TEST-REG04: Crisis Auto-Transition
  GIVEN any regime
  WHEN price drops 9% in 24h
  THEN regime → CRISIS immediately (0 confirmation candles)
  AND all positions closed
  AND no new trades
```

### 6.4 Dual-Speed Engine Tests

```
TEST-DS01: Core Always Active
  GIVEN any regime (TREND, CHOP, VOLATILE)
  AND kill_switch_level < 3
  WHEN signal passes SQS gate
  THEN core engine generates TradeDecision
  AND capital_engine = "core"
  AND position drawn from 80% pool

TEST-DS02: Accel Activates Only in STRONG_TREND
  GIVEN regime = TREND, sub_regime = STRONG_TREND
  AND alignment_score = 0.97 (>=0.95)
  AND sqs_score = 0.88 (>=0.85)
  AND kill_switch_level = 0
  WHEN accel evaluation runs
  THEN accel engine ACTIVATES
  AND capital_engine = "accel"
  AND position drawn from 20% pool
  AND leverage up to 3.0x allowed

TEST-DS03: Accel Disabled in CHOP
  GIVEN regime = CHOP
  WHEN any signal evaluated
  THEN accel_eligible = false always
  AND no trades with capital_engine = "accel"

TEST-DS04: Accel Cannot Override Risk
  GIVEN accel wants to trade, SQS = 0.90
  AND kill_switch_level = 1 (CAUTION)
  WHEN risk check runs
  THEN accel DISABLED (requires level 0)
  AND reason = "Accel requires kill_switch NORMAL"

TEST-DS05: Shared Risk Pool
  GIVEN core has -1.5% daily PnL, accel has -0.8% daily PnL
  WHEN combined daily PnL = -2.3%
  THEN daily_pnl evaluated against combined -2.3%
  AND if exceeds soft_cap (-1.5%) → CAUTION escalation
```

### 6.5 Darwin & Reflector Tests

```
TEST-DAR01: Overfitting Guard
  GIVEN Darwin produces candidate with train_sharpe = 3.0
  AND validation_sharpe = 1.2
  WHEN degradation check: 1.2 < 0.5 × 3.0 = 1.5
  THEN candidate REJECTED as overfit
  AND logged in experiment_versions with status = "rejected_overfit"

TEST-REF01: Bounded Adjustment
  GIVEN 5 consecutive losses
  WHEN Reflector activates
  THEN position_size_mult reduced to max 0.7 (30% reduction)
  AND cooldown_candles set to 6
  AND adjustment logged as new experiment_version
  AND adjustment auto-reverts after 50 trades if performance recovers

TEST-REF02: Reflector Cannot Increase Risk
  GIVEN Reflector runs analysis
  WHEN computing AdjustmentVector
  THEN position_size_mult ALWAYS <= 1.0 (never increases)
  AND stop_multiplier_delta ALWAYS >= 0 (never tightens stops — widens only)
  AND confidence_threshold_delta ALWAYS >= 0 (never lowers bar)

TEST-REF03: Minimum Trade Count
  GIVEN system has completed 15 trades total
  WHEN Reflector trigger conditions are met
  THEN Reflector does NOT activate (requires 30 minimum)
  AND log: "Reflector skipped — insufficient trade count (15 < 30)"
```

---

## 7. PHASED IMPLEMENTATION PLAN

### Package 0: Foundation (Weeks 1–3)

```
Goal: Core contracts + infrastructure only. No trading logic.

Deliverables:
  P0.1  Pydantic v2 contracts (all 13 types from Section 2)
        Test: Frozen immutability, validation, NaN rejection
  P0.2  SQLite schema creation (all 9 tables from Section 3)
        Test: CRUD operations, index verification
  P0.3  Config loader (YAML → typed objects)
        Test: All config files parse without error
  P0.4  Event bus (pub/sub for telemetry)
        Test: Publish event → subscriber receives
  P0.5  LedgerEvent system (financial audit trail)
        Test: Every debit/credit tracked, balance_after correct

Exit Gate:
  - All 13 contracts instantiable with valid data
  - All contracts reject invalid data (NaN, out-of-range)
  - All 9 SQLite tables created, indexed, writable
  - Config files loaded into typed objects
  - Zero production logic — contracts and infra only
```

### Package 1: Signal Quality + CHOP (Weeks 4–7)

```
Goal: SQS gate operational. CHOP regime fully implemented.

Deliverables:
  P1.1  SignalQualityGate implementation (5 components)
        Test: TEST-SQS01 through TEST-SQS04 pass
  P1.2  CHOP regime rules (all 6 rules from Section 5.5)
        Test: TEST-REG01, TEST-REG02 pass
  P1.3  STRONG_TREND sub-regime detection
        Test: TEST-REG03 passes
  P1.4  Counterfactual logging system
        Test: Rejected signals tracked, 24h theoretical PnL filled
  P1.5  SQS threshold tuning via backtest on 2024-2025 BTC data
        Test: Threshold rejects at least 30% of signals
        Test: Rejected signals have lower avg PnL than accepted

Dependencies: Package 0 complete

Exit Gate:
  - SQS scores computed for every signal
  - CHOP midpoint dead zone enforced
  - False breakout filter operational
  - Counterfactuals logged and resolved after 24h
  - Backtest shows SQS filtering improves net Sharpe
```

### Package 2: Dual-Speed Engine (Weeks 8–12)

```
Goal: Core + Accel architecture operational. HyperSizer active.

Deliverables:
  P2.1  Capital pool separation (80/20 split tracked in ledger)
        Test: Trades tagged core/accel, pools independent
  P2.2  HyperSizer implementation (growth phases + sigmoid floor)
        Test: Correct sizing per phase, floor behavior verified
  P2.3  Accel activation logic (STRONG_TREND + alignment + SQS)
        Test: TEST-DS01 through TEST-DS05 pass
  P2.4  Shared risk pool (combined DD tracking)
        Test: Combined daily PnL triggers single kill switch
  P2.5  Accel auto-disable on regime change to CHOP/VOLATILE/CRISIS
        Test: Accel positions closed when regime exits STRONG_TREND
  P2.6  Edge Health Monitor (rolling 30-trade metrics per engine)
        Test: edge_health table populated, DEGRADED status triggers alert

Dependencies: Package 1 complete

Exit Gate:
  - Core engine trades in all regimes (except CRISIS)
  - Accel engine activates ONLY in STRONG_TREND with all gates passed
  - HyperSizer correctly sizes per equity phase
  - Single kill switch governs both engines
  - Edge health tracked per engine/sub-strategy
```

### Package 3: Evolution + Time Machine (Weeks 13–18)

```
Goal: Offline optimization operational. Full backtest validation.

Deliverables:
  P3.1  Darwin genetic optimizer (full algorithm from Section 5.1)
        Test: TEST-DAR01 passes (overfitting guard)
        Test: Produces experiment_version entries
  P3.2  Reflector bounded adjustment (Section 5.2)
        Test: TEST-REF01 through TEST-REF03 pass
        Test: Adjustments auto-revert after 50 trades
  P3.3  Time Machine backtest engine (Section 4)
        Test: Walk-forward 5-fold on 2020-2025 BTC data
        Test: OOS Sharpe > 0 on >= 4/5 folds
  P3.4  Experiment Manager (version tracking, candidate→active→retired)
        Test: Parameter changes tracked with parent linkage
  P3.5  Cooldown/Retirement logic
        Test: Engine with 90d rolling Sharpe < 0 for 3 months → status RETIRED
        Test: Retired engine excluded from signal generation
  P3.6  Monte Carlo validation (1000 permutations)
        Test: 95th percentile MaxDD < 2× mean MaxDD

Dependencies: Package 2 complete

Exit Gate:
  - Darwin evolves params offline, anti-overfitting guards functional
  - Reflector adjusts within bounds, never increases risk
  - Time Machine backtests with 2× cost model
  - Walk-forward validation passes
  - Strategy versioning tracks all parameter changes
  - System ready for Phase 1 live deployment (BTC-only, core engine)
```

### Phase 2 Stub (Post Package 3, Not Detailed Here)

```
Add XAU as second asset:
  - XAU data adapter (OHLCV via TradingView or MetalPrice API)
  - XAU-specific FeatureVector extensions (gold-specific indicators)
  - Cross-asset correlation monitoring (BTC-XAU)
  - Dynamic allocation engine (split capital based on relative regime quality)
  - Full SQS for XAU signals
  - Combined portfolio risk (correlation-adjusted)
  
Architecture is READY from Package 0-3:
  - All contracts support symbol field
  - All schemas support multiple symbols
  - Config supports multi-asset
  - XAU is inactive until explicitly enabled
```

---

## APPENDIX A: CONFIG CHANGES FOR v2.5

### New in config/engines.yaml

```yaml
# Add to existing engines.yaml
dual_speed:
  core:
    capital_pct: 0.80
    max_leverage: 2.0
    active_regimes: ["TREND", "CHOP", "VOLATILE"]
  accel:
    capital_pct: 0.20
    max_leverage: 3.0
    active_regimes: ["TREND"]
    required_sub_regime: "STRONG_TREND"
    min_alignment: 0.95
    min_sqs: 0.85
    required_kill_switch: 0
```

### New in config/regimes.yaml

```yaml
# Replace "RANGING" with "CHOP" throughout
regime:
  states: ["TREND", "CHOP", "VOLATILE", "CRISIS"]
  default: "CHOP"

  sub_regimes:
    TREND:
      STRONG_TREND:
        min_adx: 35
        min_alignment_candles: 12
        min_confidence: 0.85
      WEAK_TREND:
        adx_range: [25, 35]

  chop:
    dead_zone_atr_mult: 0.3
    false_breakout_volume_min: 1.2
    false_breakout_reentry_candles: 2
    max_leverage: 1.0
    position_size_mult: 0.6
    stop_mult_override: 0.8
    order_type: "passive_limit"
```

### New in config/risk.yaml

```yaml
# Add to existing risk.yaml
sqs:
  weights:
    regime_consistency: 0.25
    trend_structure: 0.20
    microstructure: 0.20
    fee_adj_expectancy: 0.20
    hermes_news_risk: 0.15
  thresholds:
    TREND: 0.60
    STRONG_TREND: 0.55
    CHOP: 0.70
    VOLATILE: 0.65
    CRISIS: 1.01
  round_trip_cost: 0.0013

max_drawdown_absolute: 0.12
```

---

## APPENDIX B: v2.0 → v2.5 MIGRATION SUMMARY

| Component | v2.0 | v2.5 | Action |
|-----------|------|------|--------|
| Regime: RANGING | Active | Renamed to CHOP | Rename all references |
| Sub-regimes | None | STRONG_TREND, WEAK_TREND | New detection logic |
| SQS Gate | None | 5-component scoring | New module `src/mde/sqs.py` |
| Capital engine | Single pool | Core (80%) + Accel (20%) | New `src/engines/capital_router.py` |
| Position sizing | Fixed fractional only | HyperSizer (phase-aware) | Replace `src/mde/sizing.py` |
| Kill switch DD | 10% lockdown | 12% absolute kill | Update config threshold |
| Darwin | Config only | Full GA implementation | New `src/ml/darwin.py` |
| Reflector | Config only | Bounded adjustment | New `src/telemetry/reflector.py` |
| Counterfactuals | Not tracked | Full tracking + resolution | New table + module |
| Ledger | Not present | Full financial audit trail | New table + module |
| Experiment versions | Not present | Version tracking | New table + module |
| Edge health | Not present | Per-engine rolling metrics | New table + module |

---

**END OF ARGUS v2.5 SPECIFICATION**
