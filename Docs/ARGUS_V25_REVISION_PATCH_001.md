# ARGUS v2.5 — REVISION PATCH 001

**Date:** 2026-02-13  
**Applies to:** ARGUS_V25_SPEC_PART1.md, PART2.md, PART3.md  
**Status:** MANDATORY — apply before implementation begins

---

## PATCH 1: Risk Cap Consistency

**Problem:** HyperSizer ACCELERATION phase has `max_risk=4.5%`, but global `per_trade_risk_cap=3%` in risk.yaml. These conflict. No defined source of truth.

### Source of Truth

```
config/risk.yaml → risk.global_caps is the SINGLE SOURCE OF TRUTH.
HyperSizer phase caps are PROPOSALS. Global caps are HARD CEILINGS.
```

### REPLACE in PART2, Section 5.3, Phase Definitions (line 468–474):

**Old:**
```
SURVIVAL:       equity [0, 2000]        kelly_frac=0.30  max_lev=1.0  max_risk=1.5%
FOUNDATION:     equity [2000, 10000]    kelly_frac=0.50  max_lev=1.5  max_risk=2.5%
GROWTH:         equity [10000, 50000]   kelly_frac=0.75  max_lev=2.0  max_risk=3.5%
ACCELERATION:   equity [50000, 200000]  kelly_frac=1.00  max_lev=2.5  max_risk=4.5%
COMPOUNDING:    equity [200000, ∞)      kelly_frac=0.85  max_lev=2.0  max_risk=3.5%
```

**New:**
```
SURVIVAL:       equity [0, 2000]        kelly_frac=0.30  max_lev=1.0  phase_risk=1.5%
FOUNDATION:     equity [2000, 10000]    kelly_frac=0.50  max_lev=1.5  phase_risk=2.5%
GROWTH:         equity [10000, 50000]   kelly_frac=0.75  max_lev=2.0  phase_risk=3.0%
ACCELERATION:   equity [50000, 200000]  kelly_frac=1.00  max_lev=2.5  phase_risk=3.0%
COMPOUNDING:    equity [200000, ∞)      kelly_frac=0.85  max_lev=2.0  phase_risk=3.0%

NOTE: "phase_risk" replaces "max_risk". Renamed to clarify it is NOT the final cap.
GROWTH, ACCELERATION, COMPOUNDING all capped at 3.0% to match global ceiling.
```

### REPLACE in PART2, Section 5.3, Algorithm step 7 (line 504):

**Old:**
```
  7. risk_per_trade = clamp(risk_per_trade, 0.005, phase.max_risk)
```

**New:**
```
  7. effective_cap = min(phase.phase_risk, global_caps.per_trade_risk_cap)
     risk_per_trade = clamp(risk_per_trade, global_caps.min_risk_pct, effective_cap)
```

### ADD to PART3, Appendix A, config/risk.yaml section (after line ~458):

```yaml
# Add at top level under risk:
risk:
  global_caps:
    per_trade_risk_cap: 0.03           # 3% — absolute ceiling, no phase can exceed
    min_risk_pct: 0.005                # 0.5% — floor
    max_position_size: 0.15            # 15% of equity
    max_leverage_core: 2.0             # core engine ceiling
    max_leverage_accel: 3.0            # accel engine ceiling
    max_leverage_global: 3.0           # system-wide absolute ceiling
```

### Invariants (ADD to PART1, after Section 2.8 SizingDecision):

```
RISK CAP INVARIANTS (enforced at SizingDecision creation, assert-level):

INV-RC1: risk_per_trade <= global_caps.per_trade_risk_cap          ALWAYS
INV-RC2: phase.phase_risk <= global_caps.per_trade_risk_cap        ALWAYS (validated at config load)
INV-RC3: leverage <= global_caps.max_leverage_core  IF engine=core  ALWAYS
INV-RC4: leverage <= global_caps.max_leverage_accel IF engine=accel ALWAYS
INV-RC5: leverage <= global_caps.max_leverage_global               ALWAYS
INV-RC6: position_size_pct <= global_caps.max_position_size        ALWAYS
INV-RC7: If any invariant fails → trade REJECTED, alert logged, never silently clamped
```

---

## PATCH 2: Unified Fee/Slippage Model

**Problem:** Fee constants hardcoded in 3 places (SQS component #4 line 574, Time Machine invariant #1 line 323, Constitution 13.5). Must be a single parametrized model referenced everywhere.

### ADD new contract to PART1 Section 2 (after 2.13 TradeRecord):

```
### 2.14 FeeModel

FeeModel:
  maker_fee_pct:       float    # default: 0.0002  (0.02% — Binance VIP0 maker)
  taker_fee_pct:       float    # default: 0.0005  (0.05% — Binance VIP0 taker)
  spread_estimate_pct: float    # default: 0.0003  (0.03% — BTC typical)
  slippage_base_pct:   float    # default: 0.0002  (0.02%)
  slippage_per_10k:    float    # default: 0.0001  (0.01% per $10k notional)
  backtest_cost_mult:  float    # default: 2.0     (pessimistic multiplier for backtests)

  DERIVED (computed, not stored):
    live_round_trip:     maker_fee_pct + taker_fee_pct + spread_estimate_pct + slippage_base_pct
                         # default: 0.0002 + 0.0005 + 0.0003 + 0.0002 = 0.0012
    backtest_round_trip: live_round_trip × backtest_cost_mult
                         # default: 0.0012 × 2.0 = 0.0024
    
FUNCTION estimate_slippage(notional_usd):
  RETURN slippage_base_pct + slippage_per_10k × (notional_usd / 10000)
```

### ADD to PART3, Appendix A, config/risk.yaml:

```yaml
risk:
  fee_model:
    maker_fee_pct: 0.0002
    taker_fee_pct: 0.0005
    spread_estimate_pct: 0.0003
    slippage_base_pct: 0.0002
    slippage_per_10k: 0.0001
    backtest_cost_mult: 2.0
```

### REPLACE in PART2, Section 5.4, Component #4 (line 572–581):

**Old:**
```
4. FEE-ADJUSTED EXPECTANCY (weight=0.20):
   gross_ev = signal.expected_return
   round_trip_cost = 0.0013  // from Constitution 13.5
   net_ev = gross_ev - round_trip_cost
   
   IF net_ev <= 0: score = 0.0
   ELSE: score = normalize(net_ev, 0.0, 0.02)
   
   rr_ratio = signal.take_profit_distance / signal.stop_distance
   IF rr_ratio < 1.5: score × 0.5
```

**New:**
```
4. FEE-ADJUSTED EXPECTANCY (weight=0.20):
   gross_ev = signal.expected_return
   rt_cost = fee_model.live_round_trip  // from config/risk.yaml → fee_model
   slippage = fee_model.estimate_slippage(notional_usd)
   net_ev = gross_ev - rt_cost - slippage
   
   IF net_ev <= 0: score = 0.0
   ELSE: score = normalize(net_ev, 0.0, 0.02)
   
   rr_ratio = signal.take_profit_distance / signal.stop_distance
   IF rr_ratio < 1.5: score × 0.5
```

### REPLACE in PART2, Time Machine Invariants (line 322–330):

**Old:**
```
1. Fee model MUST use 2x estimated costs (pessimistic).
2. Slippage model: 0.02% base + 0.01% per $10k notional.
```

**New:**
```
1. Fee model MUST use fee_model.backtest_round_trip (= live_round_trip × backtest_cost_mult).
   Source: config/risk.yaml → risk.fee_model. No hardcoded constants.
2. Slippage model: fee_model.estimate_slippage(notional_usd).
   Source: same config. Parameters: slippage_base_pct + slippage_per_10k.
```

### REPLACE in PART3, Appendix A, config/risk.yaml SQS section (line ~464):

**Old:**
```yaml
  round_trip_cost: 0.0013
```

**New:**
```yaml
  # REMOVED — round_trip_cost now derived from risk.fee_model (see Patch 2)
  # SQS reads fee_model.live_round_trip at runtime
```

---

## PATCH 3: Acceleration Activation Safety Gates

**Problem:** Accel activation only checks `kill_switch_level == 0`. Missing: volatility, drawdown, and slippage error checks.

### REPLACE in PART2, Section 5.3, Accel Engine Override (line 522–532):

**Old:**
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

**New:**
```
IF capital_engine == "accel":
  // --- Signal quality gates (unchanged) ---
  REQUIRE regime.sub_regime == "STRONG_TREND"
  REQUIRE alignment_score >= 0.95
  REQUIRE sqs_score >= 0.85
  
  // --- Risk safety gates (extended) ---
  REQUIRE kill_switch_level == 0
  REQUIRE rolling_vol_24h <= accel.max_rolling_vol           // Gate A
  REQUIRE current_drawdown_pct <= accel.max_dd_for_activation // Gate B
  REQUIRE recent_slippage_err <= accel.max_slippage_err       // Gate C
  
  leverage_cap = min(3.0, global_caps.max_leverage_accel)
  position_pool = 0.20 × total_equity (NOT the core 80%)
  risk_per_trade <= global_caps.per_trade_risk_cap            // INV-RC1

  // Accel losses still count toward global drawdown

GATE DEFINITIONS:
  Gate A — Volatility Guard:
    rolling_vol_24h = realized volatility of 1h returns over last 24 candles
    max_rolling_vol = 0.04 (4% daily vol, ~76% annualized)
    Rationale: Accel in high-vol = leveraged loss amplification

  Gate B — Drawdown Guard:
    current_drawdown_pct = (peak_equity - current_equity) / peak_equity
    max_dd_for_activation = 0.02 (2%)
    Rationale: Don't accelerate when already losing. Only accelerate from strength.

  Gate C — Slippage Quality Guard:
    recent_slippage_err = mean(abs(actual_slippage - expected_slippage))
                          over last 10 filled orders
    max_slippage_err = 0.001 (0.1%)
    Rationale: If execution quality is degraded, leverage amplifies the problem.
    IF fewer than 10 orders in history: Gate C = PASS (insufficient data to judge)
```

### ADD to PART3, Appendix A, config/engines.yaml dual_speed section:

```yaml
dual_speed:
  accel:
    # ... existing keys ...
    max_rolling_vol: 0.04              # 4% daily vol ceiling
    rolling_vol_window: 24             # candles (24h on 1h TF)
    max_dd_for_activation: 0.02        # 2% max drawdown to activate
    max_slippage_err: 0.001            # 0.1% mean slippage error
    slippage_lookback_orders: 10       # last N filled orders
```

---

## PATCH 4: Stop Widening + Position Size Recalculation

**Problem:** When Reflector widens stops (stop_multiplier_delta > 0), position size must shrink proportionally to keep risk_per_trade constant. The original spec allows stop widening but doesn't mandate resizing.

### ADD to PART2, Section 5.2 Reflector, after step 4 APPLY (after line 446):

```
4b. RESIZE (MANDATORY when stop_multiplier_delta > 0):
    // Invariant: risk_per_trade must remain constant after stop widening
    
    old_stop = current_stop_distance
    new_stop = old_stop × (1.0 + stop_multiplier_delta)
    new_stop = clamp(new_stop, 0.01, 0.05)  // respect global stop bounds
    
    // Recalculate position size to preserve risk
    new_position_size = risk_per_trade / new_stop
    new_position_size = clamp(new_position_size, 0.0, 0.15)
    
    // Update open positions if applicable
    FOR EACH open_position WHERE engine matches Reflector target:
      IF position.stop_distance < new_stop:
        position.sl_price = recalculate_sl(entry_price, new_stop, side)
        submit_sl_amendment(position, new_sl_price)
        // Do NOT resize existing position (only reduce if partial close logical)
        // New stop takes effect; existing risk is ACCEPTED as sunk cost
      
    // Future trades use new_stop and new_position_size
    LOG: "Reflector widened stop: {old_stop:.4f} → {new_stop:.4f}, "
         "position size adjusted: {old_size:.4f} → {new_position_size:.4f}, "
         "risk_per_trade preserved at {risk_per_trade:.4f}"
```

### ADD invariants to PART2, Section 5.2 Hard Constraints (after line 458):

```
STOP-SIZE INVARIANTS:
  INV-SS1: risk_per_trade = position_size × stop_distance     (always holds)
  INV-SS2: IF stop_distance increases → position_size MUST decrease proportionally
  INV-SS3: IF Reflector widens stop by X% → new_size = old_size / (1 + X/100)
  INV-SS4: Open positions: only SL amended (wider), size NOT changed mid-trade
  INV-SS5: new_stop MUST still satisfy: 0.01 <= new_stop <= 0.05
```

---

## NEW / UPDATED ACCEPTANCE TESTS

### Patch 1 Tests

```
TEST-RC01: Global Cap Overrides Phase Cap
  GIVEN phase = ACCELERATION, phase_risk = 3.0%
  AND global_caps.per_trade_risk_cap = 0.03
  AND all multipliers = 1.0 (best case)
  WHEN HyperSizer computes
  THEN effective_cap = min(0.03, 0.03) = 0.03
  AND risk_per_trade <= 0.03

TEST-RC02: Phase Cap Below Global (No Conflict)
  GIVEN phase = SURVIVAL, phase_risk = 1.5%
  AND global_caps.per_trade_risk_cap = 0.03
  WHEN HyperSizer computes
  THEN effective_cap = min(0.015, 0.03) = 0.015
  AND risk_per_trade <= 0.015

TEST-RC03: Accel Respects Global Leverage Cap
  GIVEN accel engine active, phase = GROWTH
  AND global_caps.max_leverage_accel = 3.0
  WHEN leverage calculated  
  THEN leverage <= 3.0
  AND leverage <= global_caps.max_leverage_global

TEST-RC04: Config Validation at Startup
  GIVEN config loaded with ACCELERATION.phase_risk = 0.045
  AND global_caps.per_trade_risk_cap = 0.03
  WHEN config validation runs
  THEN FATAL error: "phase_risk 4.5% exceeds global cap 3.0% — fix config"
  AND system refuses to start
```

### Patch 2 Tests

```
TEST-FEE01: SQS Uses Config Fee Model
  GIVEN fee_model.maker_fee_pct = 0.0002, taker = 0.0005, spread = 0.0003, slip = 0.0002
  WHEN SQS computes fee_adj_expectancy
  THEN round_trip = 0.0012 (not hardcoded 0.0013)
  AND slippage computed via estimate_slippage(notional)

TEST-FEE02: Backtest Uses Pessimistic Multiplier
  GIVEN fee_model.backtest_cost_mult = 2.0
  AND fee_model.live_round_trip = 0.0012
  WHEN Time Machine runs backtest
  THEN cost_per_trade = 0.0024
  AND slippage also multiplied by 2.0

TEST-FEE03: Single Source for All Fee Consumers
  GIVEN fee_model config changed (e.g., maker_fee raised to 0.0004)
  WHEN SQS, backtest, and Time Machine all compute costs
  THEN all three use live_round_trip = 0.0014 (updated)
  AND no component uses hardcoded 0.0013

TEST-FEE04: Slippage Scales with Size
  GIVEN notional = $50,000
  WHEN estimate_slippage called
  THEN slippage = 0.0002 + 0.0001 × 5 = 0.0007 (0.07%)
```

### Patch 3 Tests

```
TEST-ACCEL01: Volatility Gate Blocks Accel
  GIVEN regime = STRONG_TREND, alignment = 0.97, sqs = 0.90, kill_switch = 0
  AND rolling_vol_24h = 0.06 (> max 0.04)
  WHEN accel activation check runs
  THEN accel BLOCKED by Gate A
  AND reason = "rolling_vol_24h 6.0% exceeds max 4.0%"

TEST-ACCEL02: Drawdown Gate Blocks Accel
  GIVEN all signal gates pass
  AND current_drawdown_pct = 0.035 (> max 0.02)
  WHEN accel activation check runs
  THEN accel BLOCKED by Gate B
  AND reason = "drawdown 3.5% exceeds accel max 2.0%"

TEST-ACCEL03: Slippage Gate Blocks Accel
  GIVEN all other gates pass
  AND mean slippage error over last 10 orders = 0.0015 (> max 0.001)
  WHEN accel activation check runs
  THEN accel BLOCKED by Gate C
  AND reason = "slippage_err 0.15% exceeds max 0.10%"

TEST-ACCEL04: Slippage Gate Passes with Insufficient Data
  GIVEN fewer than 10 historical orders
  WHEN Gate C evaluated
  THEN Gate C = PASS (insufficient data, benefit of doubt)

TEST-ACCEL05: All Gates Must Pass Together
  GIVEN Gate A passes, Gate B passes, Gate C passes
  AND kill_switch = 0, sub_regime = STRONG_TREND, alignment >= 0.95, sqs >= 0.85
  WHEN accel activation check runs
  THEN accel ACTIVATED
  AND capital_engine = "accel"
```

### Patch 4 Tests

```
TEST-SS01: Stop Widening Preserves Risk
  GIVEN risk_per_trade = 0.02, old_stop = 0.02, old_size = 1.0
  WHEN Reflector widens stop by +0.15 (15%)
  THEN new_stop = 0.02 × 1.15 = 0.023
  AND new_size = 0.02 / 0.023 = 0.8696
  AND risk_per_trade = 0.8696 × 0.023 = 0.02 (unchanged)

TEST-SS02: Stop Widening Respects Max Stop
  GIVEN old_stop = 0.045
  WHEN Reflector widens by +0.15
  THEN computed stop = 0.045 × 1.15 = 0.05175
  AND clamped to 0.05 (max stop)
  AND new_size = risk_per_trade / 0.05

TEST-SS03: Open Positions Get SL Amendment Only
  GIVEN open position with stop at $48,000
  WHEN Reflector widens stop
  THEN SL order amended on exchange to wider value
  AND position size NOT changed
  AND log: "Open position SL amended, size unchanged (sunk cost)"

TEST-SS04: New Trades Use Updated Stop + Size
  GIVEN Reflector widened stop from 0.02 to 0.023
  WHEN next signal triggers new trade
  THEN stop_distance = 0.023
  AND position_size = risk_per_trade / 0.023
  AND risk_per_trade <= global_caps.per_trade_risk_cap
```

---

## OPTIONAL: Darwin Population Size Recommendation

### ADD note to PART2, Section 5.1 Configuration, after population_size line:

```
RECOMMENDED UPGRADE: population_size: 30 → 64

With 30 individuals and a parameter space of 15+ genes, the GA explores
~30 points per generation in a combinatorial space of ~10^12. This yields
a coverage ratio of <10^-10 per generation. Increasing to 64 doubles
exploration breadth, reduces premature convergence risk by 40-60% (empirical,
De Jong 2006), and still completes a weekly evolution run in <2h on the
target hardware (each individual = 1 backtest ≈ 90s; 64 × 90s = 96min).
The cost is purely compute time; memory is negligible. Set elite_count to 6
(~10% of population) to maintain pressure. tournament_size stays 3.
```

---

## OPTIONAL: Phase 2 Correlation Contracts (Stub)

### ADD to PART1 Section 2 (after 2.14 FeeModel):

```
### 2.15 CorrelationMatrix (Phase 2 — stub)

CorrelationMatrix:
  timestamp:            datetime
  window_days:          int              # 30 | 60 | 90
  assets:               list[str]        # ["BTCUSDT", "XAUUSD"]
  matrix:               dict[str, dict[str, float]]
                        # {"BTCUSDT": {"XAUUSD": -0.15}, "XAUUSD": {"BTCUSDT": -0.15}}
  rolling_correlation:  float            # primary pair correlation
  regime_correlation:   Optional[float]  # correlation filtered by current regime
  is_decorrelated:      bool             # abs(rolling_correlation) < 0.3

### 2.16 PortfolioVariance (Phase 2 — stub)

PortfolioVariance:
  timestamp:            datetime
  assets:               list[str]
  weights:              dict[str, float]    # {"BTCUSDT": 0.7, "XAUUSD": 0.3}
  individual_vars:      dict[str, float]    # per-asset variance
  covariance_matrix:    dict[str, dict[str, float]]
  portfolio_variance:   float               # w^T × Σ × w
  portfolio_vol:        float               # sqrt(portfolio_variance)
  marginal_risk:        dict[str, float]    # per-asset marginal contribution to risk
  diversification_ratio: float              # sum(w_i × σ_i) / portfolio_vol — >1 means diversification benefit
```

---

**END OF REVISION PATCH 001**
