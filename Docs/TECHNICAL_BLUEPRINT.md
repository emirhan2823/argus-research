# ARGUS Technical Blueprint — Static Architecture

**Version:** 2.0 (CAI Post-Mortem Upgrade)  
**Date:** 2026-02-15  
**Scope:** Complete module dependency map, data contracts, database schema, and new subsystem integration (Correlation Engine, Hyper-Precision Mode, Enhanced CHOP Alpha).  
**v2.0 Addendum:** CAI battle-tested pivots — Validation Protocol, Dynamic Execution, Whale-Momentum Fusion, Hyper-Precision 1m/3m timeframes.

---

## 0) ARCHITECTURAL TRUTH — What Actually Exists in Code

Before any design, this section anchors us to **implemented reality** (not plan aspirations).

### 0.1 — Implemented & Tested (can import today)

| Layer | Path | Key Classes | Status |
|-------|------|-------------|--------|
| Core Types | `src/core/types.py` | `FeatureVector` (60+ fields), `RegimeState`, `EngineSignal`, `Decision`, `Position`, `PortfolioState`, `TradeRecord` | LIVE |
| Core Config | `src/core/config.py` | `ArgusConfig` (root), 25+ nested Pydantic models | LIVE |
| Core Events | `src/core/events.py` | `EventBus`, `EventType` (30+ event types) | LIVE |
| v2.5 Contracts | `src/v25/contracts/` | 30+ frozen Pydantic models (Decimal-based) | LIVE |
| v2.5 DB | `src/v25/db/migrations.py` | 13 tables, 18+ indexes, atomic migration | LIVE |
| v2.5 Config | `src/v25/config/loader.py` | `V25Config`, `FeeModelConfig`, `AccelConfig` | LIVE |
| v2.5 Risk | `src/v25/risk/` | `accel_gates`, `stop_resize`, `caps` | LIVE |
| v2.5 Telemetry | `src/v25/telemetry/log_writer.py` | `log_decision()`, `log_sqs()`, `log_ledger_event()` | LIVE |
| Engines | `src/engines/` | Titan, Nautilus, Phoenix, Hermes, Hydra, Atlas overlay | LIVE |
| MDE | `src/mde/` | `RegimeRouter`, gates, sizing, signal_quality, execution_router | LIVE |
| Risk | `src/risk/` | `KillSwitch`, `PreTradeChecker`, `GrowthSizer` (Kelly/Optimal-f) | LIVE |
| Regime | `src/regime/` | `RuleBasedRegimeClassifier`, `RegimeConsensus`, `RegimeStateMachine` | LIVE |
| Execution | `src/execution/` | `Executor`, `StopLossManager`, `Reconciler`, `HermesPositionManager` | LIVE |
| Learning | `src/learning/` | `DarwinEngine` (GA, 18 genes), `Reflector` (shadow sim, 10 failure modes) | LIVE |
| Backtest | `src/backtest/` | `BacktestEngine`, `metrics`, `walk_forward`, `ml_data` (purged k-fold, triple-barrier) | LIVE |
| Data | `src/data/` | `DataFactory`, `SentinelValidator`, `LocalDataProvider` | LIVE |
| Portfolio | `src/portfolio/` | `PortfolioAllocator` | LIVE |
| Pipeline | `src/main.py` | `ArgusPipeline` (11-step), `DemoBroker` | LIVE |

### 0.2 — Plan-Only (NOT in code yet)

| Module | Plan Section | Notes |
|--------|-------------|-------|
| `src/v25/trainer/` | Phase 7 (Auto-RBI) | Scaffolded in prior session, not wired |
| `src/factory/` | Section 25 | Never created |
| `src/evolution/` | Section 26 | Never created |
| `src/daemon/` | Section 27 | Never created |
| `src/radar/` | Section 24 | Never created |
| `src/adapters/` | Section 23 | Never created |
| Correlation Engine | NEW requirement | Design in this document |

### 0.3 — YAML Config Files (Actual)

| File | Controls |
|------|----------|
| `config/base.yaml` | System, assets (crypto/equity/commodity/index), timeframes, exchanges |
| `config/risk.yaml` | Sizing, stops, drawdown, kill switch, growth phases, Darwin, fee model |
| `config/engines.yaml` | Titan/Nautilus/Phoenix/Hermes/Hydra/Atlas params, dual-speed accel |
| `config/regimes.yaml` | Regime thresholds, transitions, hysteresis, Hermes overrides |
| `config/telemetry.yaml` | SQLite path, heartbeat, Telegram, retention |

---

## CAI POST-MORTEM PIVOTS — v2.0 ARCHITECTURAL UPGRADES

### PIVOT 1: The Validation Protocol (Mathematical Integrity)

**Problem discovered in CAI:** Standard leverage-based sizing leads to catastrophic failure. When leverage is chosen FIRST and risk derived from it, position sizes blow out relative to actual stop-loss distances, destroying accounts.

**Root cause:** Treating leverage as an INPUT parameter rather than a DERIVED output.

**The formula that must be enforced EVERYWHERE:**

```
  notional_size = risk_usd / sl_pct

  WHERE:
    risk_usd = equity * risk_pct                    (e.g., $1000 * 0.015 = $15)
    sl_pct   = abs(entry_price - sl_price) / entry  (e.g., 2% stop = 0.02)
    notional = $15 / 0.02 = $750

  THEN leverage is DERIVED:
    leverage = notional / equity = $750 / $1000 = 0.75x

  NEVER the reverse. Leverage is an OUTPUT, not an INPUT.
```

**Current code analysis:**

`src/mde/sizing.py:46` already computes `position_size = risk / stop_distance` which IS this formula in fractional form. However, `SizingInput.leverage_mult` (line 21) acts as an independent input multiplier that can inflate risk beyond what the stop distance justifies. In `src/risk/sizing.py`, `GrowthSizingInput.leverage` (line 172) is also a free-standing input.

**Required architectural change:**

```python
# NEW: src/risk/validated_sizer.py — THE canonical sizing function

@dataclass(frozen=True)
class ValidatedSizingInput:
    equity: float               # current account equity
    risk_pct: float             # fraction of equity to risk (e.g., 0.015)
    entry_price: float          # planned entry price
    sl_price: float             # stop loss price (MUST exist before sizing)
    fee_round_trip_pct: float   # from FeeModel (e.g., 0.0012)

@dataclass(frozen=True)
class ValidatedSizingOutput:
    risk_usd: float             # equity * risk_pct
    sl_pct: float               # abs(entry - sl) / entry
    notional_usd: float         # risk_usd / sl_pct
    quantity: float             # notional / entry_price
    leverage: float             # notional / equity (DERIVED, never chosen)
    breakeven_r: float          # fee_cost / risk_usd (how much R just to cover fees)
    net_risk_usd: float         # risk_usd after fee reservation

def compute_validated_size(inp: ValidatedSizingInput) -> ValidatedSizingOutput:
    """THE sizing function. Leverage is always a RESULT.

    Invariants enforced:
      1. sl_price != entry_price (division by zero guard)
      2. leverage <= phase_max_leverage (capped, never amplified)
      3. breakeven_r < 0.3 (if fees eat >30% of risk, skip trade)
      4. quantity > exchange_min_lot (tradeable amount)
    """
    sl_pct = abs(inp.entry_price - inp.sl_price) / inp.entry_price
    assert sl_pct > 0, "SL must differ from entry"

    risk_usd = inp.equity * inp.risk_pct
    fee_cost = (risk_usd / sl_pct) * inp.fee_round_trip_pct  # fees on notional
    net_risk = risk_usd - fee_cost
    notional = net_risk / sl_pct    # FEE-ADJUSTED notional
    quantity = notional / inp.entry_price
    leverage = notional / inp.equity
    breakeven_r = fee_cost / risk_usd if risk_usd > 0 else 1.0

    return ValidatedSizingOutput(
        risk_usd=risk_usd,
        sl_pct=sl_pct,
        notional_usd=notional,
        quantity=quantity,
        leverage=leverage,       # DERIVED — never an input
        breakeven_r=breakeven_r,
        net_risk_usd=net_risk,
    )
```

**Integration plan:**
- `compute_validated_size()` replaces the final sizing step in the pipeline.
- Existing `compute_size()` in `src/mde/sizing.py` and `compute_growth_size()` in `src/risk/sizing.py` still compute `risk_pct`. But the final `notional → leverage` derivation passes through `compute_validated_size()`.
- The `leverage_mult` field becomes a *cap*, not a multiplier: `leverage = min(derived_leverage, phase_max_leverage)`.

**Anti-CAI-failure gate (new MDE gate):**
```python
# Gate 9 (NEW): Breakeven-R gate — added to src/mde/gates.py
# If breakeven_r > 0.30, the trade's expected value after fees is marginal.
# REJECT the trade.
def _check_breakeven_r(sizing: ValidatedSizingOutput) -> bool:
    return sizing.breakeven_r <= 0.30
```

---

### PIVOT 2: Correlation Trading Engine (Z-Score BTC vs Alts)

**CAI observation:** Sideways markets killed returns because static TP levels were unreachable. Correlation-gap mean-reversion is a regime-independent alpha source.

**Architecture:**

```
src/correlation/                          # NEW module
├── __init__.py
├── tracker.py          # CorrelationTracker: rolling corr, spread, cointegration
├── signals.py          # CorrelationSignalGenerator: Z-Score → signals
├── pairs_config.py     # Pair definitions, windows, thresholds
└── ou_estimator.py     # Ornstein-Uhlenbeck half-life estimation

src/engines/gemini/                       # NEW engine
├── __init__.py
└── engine.py           # GeminiEngine: consumes CorrelationSignal → EngineSignal
```

**BTC-vs-Alts Z-Score Decoupling Pipeline:**

```
                    ┌──────────────────────────────┐
                    │ Every cycle: receive closes   │
                    │ for BTC, ETH, SOL, AVAX, etc.│
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │ CorrelationTracker.update()    │
                    │                                │
                    │ For each pair (e.g. BTC/ETH):  │
                    │  1. rolling_corr(100 bars)      │
                    │  2. spread = log(P_a/P_b)       │
                    │  3. spread_zscore = (S-μ)/σ     │
                    │  4. half_life = OU_estimate(S)   │
                    │  5. cointegration = EG_test()    │
                    │  6. regime = classify_corr()     │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │ CorrelationSignalGenerator     │
                    │                                │
                    │ IF spread_zscore > entry_z:    │
                    │   AND half_life in [5, 100]:   │
                    │   AND cointegrated = True:     │
                    │   → Generate LONG laggard,     │
                    │     SHORT leader               │
                    │                                │
                    │ IF spread_zscore > stop_z:     │
                    │   → STRUCTURAL BREAK, no trade │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │ GeminiEngine                   │
                    │  → Convert to EngineSignal     │
                    │  → Feed to MDE gates + sizing  │
                    │  → Validated sizing applies    │
                    └──────────────────────────────┘
```

**Tracked Pairs (config/engines.yaml):**

```yaml
gemini:
  enabled: true
  regime_filter: [RANGING, TRENDING]
  pairs:
    - pair_id: "BTC-USDT__ETH-USDT"
      asset_a: "BTC-USDT"
      asset_b: "ETH-USDT"
      window_bars: 100
      min_correlation_history: 0.70
      entry_zscore: 2.0
      stop_zscore: 3.5
      target_zscore: 0.5
      max_position_pct: 0.05
    - pair_id: "BTC-USDT__SOL-USDT"
      asset_a: "BTC-USDT"
      asset_b: "SOL-USDT"
      window_bars: 100
      min_correlation_history: 0.65
      entry_zscore: 2.0
      stop_zscore: 3.5
      target_zscore: 0.5
      max_position_pct: 0.04
    - pair_id: "BTC-USDT__XAU-USD"
      asset_a: "BTC-USDT"
      asset_b: "XAU-USD"
      window_bars: 200
      min_correlation_history: 0.30
      entry_zscore: 2.5
      stop_zscore: 4.0
      target_zscore: 0.5
      max_position_pct: 0.03
    - pair_id: "ETH-USDT__SOL-USDT"
      asset_a: "ETH-USDT"
      asset_b: "SOL-USDT"
      window_bars: 80
      min_correlation_history: 0.60
      entry_zscore: 2.0
      stop_zscore: 3.5
      target_zscore: 0.5
      max_position_pct: 0.04
  max_simultaneous_pairs: 3
  min_half_life_bars: 5
  max_half_life_bars: 100
  cointegration_pvalue_max: 0.05
```

---

### PIVOT 3: Dynamic Execution & Trailing (The ROI Multiplier)

**CAI observation:** The ZEC +48.4% ROI case proved that static TP levels leave enormous profits on the table during strong trends. Conversely, static TPs in CHOP markets are frequently unreachable.

**Solution: 3-Stage Partial Take-Profit + ATR Trailing Stop**

```
NEW: src/execution/dynamic_exit.py

┌──────────────────────────────────────────────────┐
│         DYNAMIC EXIT STATE MACHINE                │
│                                                   │
│  Stage 0: ENTRY                                   │
│    Position opens. SL set. No TP set.             │
│    Trailing = OFF.                                │
│                                                   │
│  Stage 1: BREAKEVEN LOCK (at +0.5R)               │
│    Close 25% of position → secure fee recovery    │
│    Move SL to breakeven (entry + fees)            │
│    Trailing = OFF still                           │
│                                                   │
│  Stage 2: PROFIT CAPTURE (at +1.5R)               │
│    Close 25% more → 50% total closed             │
│    Engage ATR trailing stop on remainder:         │
│      trailing_sl = current_price - (ATR_14 × 2.0)│
│    Trailing only moves UP, never down             │
│                                                   │
│  Stage 3: TREND RIDER (at +3.0R)                  │
│    Close 25% more → 75% total closed             │
│    Tighten trailing: ATR_14 × 1.5                │
│    Remaining 25% rides to absolute trend end      │
│                                                   │
│  FINAL EXIT: Trailing stop hit on remaining 25%   │
│    OR regime flip to CRISIS → market close all    │
│    OR time_stop exceeded                          │
│                                                   │
│  REGIME-CONDITIONAL BEHAVIOR:                     │
│    TREND_STRONG: All 3 stages active, wide trail  │
│    TREND_WEAK:   Stage 1+2 only, tighter trail    │
│    CHOP:         Stage 1 only (exit at midpoint)  │
│    VOLATILE:     Stage 1+2, very tight trail      │
│    CRISIS:       Immediate market close            │
└──────────────────────────────────────────────────┘
```

**Data Contract:**

```python
# NEW: src/v25/contracts/exit_strategy.py

class ExitStage(str, Enum):
    ENTRY = "ENTRY"
    BREAKEVEN_LOCK = "BREAKEVEN_LOCK"
    PROFIT_CAPTURE = "PROFIT_CAPTURE"
    TREND_RIDER = "TREND_RIDER"
    CLOSED = "CLOSED"

class DynamicExitState(TimestampedModel):
    position_id: str
    symbol: str
    current_stage: ExitStage
    entry_price: PositiveDecimal
    current_price: PositiveDecimal
    atr_14: PositiveDecimal
    current_r: Decimal                    # (current - entry) / risk_per_unit
    trailing_sl: PositiveDecimal | None   # None until Stage 2
    trailing_atr_mult: Decimal            # starts 2.0, tightens to 1.5
    pct_closed: RatioDecimal              # 0.0 → 0.25 → 0.50 → 0.75 → 1.0
    partial_pnl_locked: Decimal           # cumulative PnL from partial closes
    stage_transitions: tuple[str, ...]    # audit trail
    regime_at_current: str
```

**Integration with existing exit modules:**

```
src/exit/stop_manager.py       ← EXTEND: read trailing_sl from DynamicExitState
src/exit/tp_manager.py         ← REPLACE static TP with stage-based partials
src/exit/hard_exits.py         ← UNCHANGED: regime flip still triggers
src/execution/executor.py      ← EXTEND: support partial close orders
```

---

### PIVOT 4: Hermes Intelligence Fusion — Whale Momentum SQS Boost

**CAI observation:** The 8B model (Hermes) was designed only for sentiment filtering. But whale flow data (exchange inflows/outflows) is a leading indicator for trend strength that should AMPLIFY signal quality, not just block bad trades.

**Current Hermes flow:**
```
NewsAnalysis → SentimentSnapshot → hermes_news_risk (SQS.C5) → gate signal
```

**Upgraded Hermes flow (bidirectional):**
```
┌──────────────────────────────────────────────────────────────┐
│                 HERMES v2: BIDIRECTIONAL                       │
│                                                               │
│  DEFENSIVE (existing):                                        │
│    Negative sentiment → hermes_news_risk LOW → SQS fails     │
│    Whale INFLOW (sell pressure) → reduce size modifier        │
│                                                               │
│  OFFENSIVE (NEW — Whale Momentum Boost):                      │
│    Whale OUTFLOW > $10M (24h) → exchange_drain_signal         │
│    Whale ACCUMULATION detected → accumulation_signal          │
│    Stablecoin mint > $100M → liquidity_injection_signal       │
│                                                               │
│    IF offensive_signal AND regime == TREND_STRONG:             │
│      → SQS.hermes_news_risk BOOSTED by +0.10 (capped at 1.0) │
│      → Size modifier increased to 1.2x                       │
│      → Accel engine gate S3 (min_sqs) effectively lowered     │
│                                                               │
│  SAFETY CONSTRAINT:                                           │
│    Offensive boost ONLY in TREND_STRONG                       │
│    Defensive veto overrides offensive in ALL regimes           │
│    Net hermes_score < -0.5 → offensive DISABLED               │
│    Max boost: +0.10 to C5, never exceed 1.0                   │
└──────────────────────────────────────────────────────────────┘
```

**New contract addition (extend `src/v25/contracts/intelligence.py`):**

```python
class WhaleMomentumSignal(TimestampedModel):
    """Aggregated whale flow momentum for trend amplification."""
    symbol: str = Field(min_length=1, max_length=64)
    net_flow_usd_24h: Decimal          # negative = outflow (bullish)
    exchange_reserve_change_pct: Decimal
    stablecoin_mint_usd_24h: NonNegativeDecimal
    accumulation_addresses: int = Field(default=0, ge=0)
    is_bullish_flow: bool              # net outflow + accumulation
    is_bearish_flow: bool              # net inflow + distribution
    momentum_score: SignedUnitDecimal  # -1.0 to +1.0
    sqs_boost: RatioDecimal            # 0.0 to 0.10 (max boost to C5)
    size_modifier: NonNegativeDecimal  # 1.0 to 1.2
    confidence: RatioDecimal
```

**Implementation file:**

```python
# NEW: src/engines/hermes/whale_momentum.py

def compute_whale_momentum(
    whale_alerts: list[WhaleAlert],      # from intelligence contract
    timeframe_hours: int = 24,
) -> WhaleMomentumSignal:
    """Aggregate whale alerts into a directional momentum signal.

    Logic:
      1. Sum all OUTFLOW amounts → exchange_drain
      2. Sum all INFLOW amounts → sell_pressure
      3. net_flow = inflow - outflow (negative = bullish)
      4. Check for ACCUMULATION pattern (repeated outflows to same wallets)
      5. Score: normalize net_flow against 30-day median

    SQS boost rules:
      - momentum_score > +0.5 AND is_bullish_flow → sqs_boost = 0.05
      - momentum_score > +0.8 AND is_bullish_flow → sqs_boost = 0.10
      - momentum_score < -0.5 → sqs_boost = 0.0 (no boost, defensive takes over)
    """

def apply_whale_boost_to_sqs(
    base_c5: float,            # hermes_news_risk from standard pipeline
    whale: WhaleMomentumSignal,
    regime: str,               # must be TREND_STRONG for boost
) -> float:
    """Apply whale momentum boost to SQS component C5.

    Rules:
      - Only boost in TREND_STRONG regime
      - base_c5 must already be >= 0.50 (don't boost garbage signals)
      - Max output: 1.0
      - Defensive override: if base_c5 < 0.30, whale boost is ZERO
    """
    if regime != "TREND_STRONG":
        return base_c5
    if base_c5 < 0.30:
        return base_c5  # defensive overrides offensive
    boosted = min(base_c5 + float(whale.sqs_boost), 1.0)
    return boosted
```

---

### PIVOT 5: Hyper-Precision Phase (1m/3m Timeframe Execution)

**Rationale:** The existing system uses 5m as the primary timeframe. For hyper-aggressive targets, 1m and 3m timeframes enable:
- Tighter entries (less slippage on limit orders)
- Faster partial TP execution (Stage 1 at +0.5R happens sooner)
- More granular trailing stop updates
- Better microstructure reads (OBI, trade flow)

**Architecture — NOT a new engine, but a new execution speed layer:**

```
NEW: src/execution/hyper_precision.py

┌────────────────────────────────────────────────────┐
│        HYPER-PRECISION EXECUTION LAYER              │
│                                                     │
│  WHEN: Signal generated on 5m/15m/1h timeframe     │
│  WHAT: Drop to 1m/3m for execution optimization    │
│                                                     │
│  1. ENTRY SNIPER (1m bars):                         │
│     - Wait for OBI > 0.60 on 1m                    │
│     - Place limit order at VWAP_1m band edge       │
│     - Timeout: 3 × 1m bars (3 minutes)             │
│     - Fallback: market order if timeout + urgency   │
│                                                     │
│  2. PARTIAL EXIT SNIPER (1m bars):                  │
│     - When DynamicExitState hits stage threshold    │
│     - Wait for OBI reversal on 1m (selling into     │
│       strength, buying into weakness)               │
│     - Place limit partial close                     │
│     - Timeout: 5 × 1m bars (5 minutes)             │
│                                                     │
│  3. TRAILING STOP UPDATE (3m bars):                 │
│     - Recalculate ATR on 3m for tighter trailing   │
│     - Update exchange-side SL every 3 minutes      │
│     - 3m ATR gives more granular trailing than 5m   │
│                                                     │
│  CRITICAL: Signal GENERATION stays on 5m+          │
│            Only EXECUTION drops to 1m/3m           │
│            This prevents signal noise on low TF     │
└────────────────────────────────────────────────────┘
```

**Config additions:**

```yaml
# config/base.yaml — ADD to timeframes section:
timeframes:
  primary: "1h"
  scalp: "15m"
  micro: "5m"
  confirmation: "4h"
  direction: "1d"
  # NEW — hyper-precision execution timeframes
  execution_entry: "1m"      # for entry sniping
  execution_trailing: "3m"   # for trailing stop updates

# config/engines.yaml — ADD:
hyper_precision:
  enabled: true
  entry_sniper:
    timeframe: "1m"
    min_obi: 0.60
    limit_timeout_bars: 3
    fallback_to_market: true
  partial_exit_sniper:
    timeframe: "1m"
    wait_for_obi_reversal: true
    timeout_bars: 5
  trailing_update:
    timeframe: "3m"
    update_interval_bars: 1      # every 3m bar
```

---

## 1) MODULE DEPENDENCY MATRIX (Updated v2.0)

### 1.1 — Data Flow Diagram (Existing + All Pivots)

```
                          ┌─────────────────────────────┐
                          │   EXTERNAL DATA SOURCES       │
                          │  BingX / Binance / Yahoo /    │
                          │  CoinGecko / Whale Alert      │
                          └──────────────┬────────────────┘
                                         │
                          ┌──────────────▼────────────────┐
                          │     src/data/data_factory.py   │
                          │  DataFactory + SentinelValidator│
                          └──────────────┬────────────────┘
                                         │
                            ┌────────────▼────────────┐
                            │  FeatureVector (60+ fld) │
                            └──┬──────────┬───────┬───┘
                               │          │       │
                 ┌─────────────▼──┐  ┌────▼─────┐ │
                 │ src/regime/     │  │ [NEW]    │ │
                 │ RegimeState     │  │ src/     │ │
                 │ Machine         │  │ correl./ │ │
                 └──────┬─────────┘  └────┬─────┘ │
                        │                 │       │
                 ┌──────▼─────────────────▼───────▼────────┐
                 │          src/mde/router.py                │
                 │  RegimeRouter → Engine Selection           │
                 │  + CorrelationSignal injection             │
                 └──────────────┬───────────────────────────┘
                                │
         ┌──────────────────────▼──────────────────────┐
         │              ENGINES (5 + 1 NEW)              │
         │  Titan│Nautilus│Phoenix│Hermes│Hydra│Gemini   │
         │  (Trend)(Chop)  (Carry) (Intel)(Scalp)(Corr)  │
         │                   │                            │
         │  [PIVOT 4] Hermes now also:                    │
         │  whale_momentum.py → SQS boost (offensive)     │
         └──────────────────────┬──────────────────────┘
                                │
                        ┌───────▼───────┐
                        │ EngineSignal   │
                        └───────┬───────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  src/mde/signal_quality.py   │
                 │  + src/mde/gates.py          │
                 │  + [PIVOT 1] Gate 9:         │
                 │    breakeven_r <= 0.30       │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  [PIVOT 1] VALIDATED SIZING   │
                 │  src/risk/validated_sizer.py  │
                 │                               │
                 │  notional = risk_usd / sl_pct │
                 │  leverage = DERIVED (output)   │
                 │  breakeven_r checked           │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  src/risk/pre_trade.py        │
                 │  PreTradeChecker (8 checks)   │
                 │  + correlation_with_book check │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  [PIVOT 5] HYPER-PRECISION    │
                 │  src/execution/               │
                 │  hyper_precision.py            │
                 │  (1m entry sniper, 3m trail)   │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  src/execution/executor.py    │
                 │  + [PIVOT 3] dynamic_exit.py  │
                 │  3-stage partial TP + ATR trail│
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │  src/v25/telemetry/           │
                 │  + src/v25/db/ (13 tables     │
                 │    + 6 NEW tables)             │
                 └──────────────────────────────┘
```

### 1.2 — Complete Module Dependency Table (v2.0)

| Module | Depends On | Feeds Into |
|--------|-----------|-----------|
| `src/data/data_factory.py` | external APIs, `src/core/types.py` | `src/main.py` pipeline |
| `src/data/sentinel/validator.py` | `src/core/types.py` | `src/main.py` pipeline |
| `src/regime/state_machine.py` | `src/regime/rule_based.py`, `src/regime/consensus.py` | `src/mde/router.py` |
| `src/engines/titan/engine.py` | `src/core/types.py` | `src/mde/router.py` |
| `src/engines/nautilus/engine.py` | `src/core/types.py` | `src/mde/router.py` |
| `src/engines/hydra/engine.py` | `src/core/types.py` | `src/mde/router.py` |
| `src/engines/hermes/engine.py` | `src/core/types.py`, `src/v25/contracts/intelligence.py` | `src/mde/router.py` |
| **[NEW] `src/engines/hermes/whale_momentum.py`** | `src/v25/contracts/intelligence.py` | `src/engines/hermes/engine.py`, SQS C5 computation |
| `src/engines/atlas/risk_overlay.py` | `src/core/types.py` | `src/mde/sizing.py` |
| **[NEW] `src/correlation/tracker.py`** | `src/core/types.py`, `src/v25/contracts/correlation.py` | `src/mde/router.py`, `src/risk/pre_trade.py` |
| **[NEW] `src/engines/gemini/engine.py`** | `src/correlation/tracker.py`, `src/correlation/signals.py` | `src/mde/router.py` |
| `src/mde/router.py` | all engines | `src/mde/gates.py` |
| `src/mde/gates.py` | `src/risk/kill_switch.py` | `src/risk/validated_sizer.py` |
| **[NEW] `src/risk/validated_sizer.py`** | `src/v25/contracts/fee.py`, `src/mde/sizing.py` | `src/risk/pre_trade.py` |
| `src/risk/pre_trade.py` | standalone | `src/execution/` |
| **[NEW] `src/execution/dynamic_exit.py`** | `src/v25/contracts/exit_strategy.py` | `src/execution/executor.py` |
| **[NEW] `src/execution/hyper_precision.py`** | `src/core/types.py`, `src/v25/contracts/fee.py` | `src/execution/executor.py` |
| `src/execution/executor.py` | `src/core/types.py` | `src/main.py` pipeline |

---

## 2) DATA CONTRACTS (Pydantic Models)

### 2.1 — Existing Contracts (Reference — DO NOT REDEFINE)

All live in `src/v25/contracts/`. They use `ArgusModel` base (frozen, strict, extra=forbid, NaN-rejection, Decimal precision).

| Contract | File | Key Fields |
|----------|------|-----------|
| `SQSScore` | `signal.py` | 6 components, total_score, passed |
| `ChopEdgeScore` | `signal.py` | 5 components, total_score, passed |
| `SignalTemplate` | `signal.py` | direction, confidence, entry/SL/TP prices, expected_r |
| `CorrelationMatrix` | `portfolio.py` | assets[], matrix{}, rolling_correlation, is_decorrelated (STUB) |
| `FeeModel` | `fee.py` | maker/taker/spread/slippage rates |
| `NewsAnalysis` | `intelligence.py` | sentiment, impact_score, category, urgency |
| `WhaleAlert` | `intelligence.py` | direction, amount_usd, exchange, confidence |
| `SentimentSnapshot` | `intelligence.py` | news/social/onchain/macro scores, composite_score |
| `RiskLimits` | `risk.py` | per-regime risk%, exposure caps, DD levels |
| `CircuitBreakerState` | `risk.py` | level (0-4), DD%, trading_enabled |
| `PositionSize` | `risk.py` | quantity, notional, leverage, all multipliers |

### 2.2 — NEW Contracts: Correlation Trading

**File:** `src/v25/contracts/correlation.py` (NEW) — same as v1.0 Blueprint.

Contains: `CorrelationRegime`, `PairTradeSide`, `CorrelationPair`, `CorrelationSignal`, `CorrelationHealth`.

### 2.3 — NEW Contract: Dynamic Exit State (PIVOT 3)

**File:** `src/v25/contracts/exit_strategy.py` (NEW)

Contains: `ExitStage` enum, `DynamicExitState` model (fields defined in Pivot 3 section above).

### 2.4 — NEW Contract: Whale Momentum Signal (PIVOT 4)

**File:** Extends `src/v25/contracts/intelligence.py` — add `WhaleMomentumSignal` model.

### 2.5 — NEW Contract: Validated Sizing Output (PIVOT 1)

**File:** `src/v25/contracts/validated_sizing.py` (NEW)

```python
class ValidatedSizing(TimestampedModel):
    symbol: str = Field(min_length=1, max_length=64)
    equity: PositiveDecimal
    risk_pct: RatioDecimal
    risk_usd: PositiveDecimal
    entry_price: PositiveDecimal
    sl_price: PositiveDecimal
    sl_pct: PositiveDecimal               # DERIVED: abs(entry-sl)/entry
    notional_usd: PositiveDecimal         # DERIVED: risk_usd / sl_pct
    quantity: PositiveDecimal             # DERIVED: notional / entry
    leverage: PositiveDecimal             # DERIVED: notional / equity
    leverage_capped: bool                 # True if leverage was capped to phase max
    breakeven_r: NonNegativeDecimal       # fee_cost / risk_usd
    fee_reserved_usd: NonNegativeDecimal  # fees deducted from risk budget
    net_risk_usd: PositiveDecimal         # risk after fee reservation
```

### 2.6 — Extended TemplateName Enum

```python
# ADD to TemplateName enum in src/v25/contracts/signal.py:
    CORR_MEAN_REVERSION = "CORR_MEAN_REVERSION"
    CORR_DECOUPLING_ARB = "CORR_DECOUPLING_ARB"
    CHOP_CORR_GAP = "CHOP_CORR_GAP"
    CHOP_MICRO_REVERSION = "CHOP_MICRO_REVERSION"
```

---

## 3) DATABASE SCHEMA

### 3.1 — Existing Tables (13 — DO NOT MODIFY)

| # | Table | Purpose |
|---|-------|---------|
| 1-13 | (same as v1.0 Blueprint) | See v1.0 |

### 3.2 — NEW Tables (add to `migrations.py`)

```sql
-- Table 14: correlation_logs (same as v1.0)
-- Table 15: correlation_signals (same as v1.0)
-- Table 16: pyramid_layers (same as v1.0)
-- Table 17: hermes_fusion_log (same as v1.0)
-- Table 18: precision_entries (same as v1.0)

-- Table 19: Dynamic exit state tracking (PIVOT 3)
CREATE TABLE IF NOT EXISTS dynamic_exit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    position_id TEXT NOT NULL,
    trade_id TEXT REFERENCES trades(trade_id),
    symbol TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN (
        'ENTRY','BREAKEVEN_LOCK','PROFIT_CAPTURE','TREND_RIDER','CLOSED'
    )),
    current_r REAL NOT NULL,
    pct_closed REAL NOT NULL,
    partial_pnl_locked REAL NOT NULL,
    trailing_sl REAL,
    trailing_atr_mult REAL,
    regime TEXT NOT NULL,
    trigger_reason TEXT NOT NULL
);

-- Table 20: Validated sizing audit log (PIVOT 1)
CREATE TABLE IF NOT EXISTS validated_sizing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    equity REAL NOT NULL,
    risk_pct REAL NOT NULL,
    risk_usd REAL NOT NULL,
    entry_price REAL NOT NULL,
    sl_price REAL NOT NULL,
    sl_pct REAL NOT NULL,
    notional_usd REAL NOT NULL,
    quantity REAL NOT NULL,
    leverage_derived REAL NOT NULL,
    leverage_capped INTEGER DEFAULT 0,
    breakeven_r REAL NOT NULL,
    fee_reserved REAL NOT NULL,
    passed_breakeven_gate INTEGER NOT NULL
);

-- Table 21: Whale momentum signals (PIVOT 4)
CREATE TABLE IF NOT EXISTS whale_momentum_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    net_flow_usd_24h REAL NOT NULL,
    exchange_reserve_change_pct REAL NOT NULL,
    stablecoin_mint_usd_24h REAL NOT NULL DEFAULT 0,
    is_bullish_flow INTEGER NOT NULL,
    is_bearish_flow INTEGER NOT NULL,
    momentum_score REAL NOT NULL,
    sqs_boost REAL NOT NULL,
    size_modifier REAL NOT NULL
);
```

### 3.3 — NEW Indexes (all tables)

```sql
-- v1.0 indexes (9) + new:
CREATE INDEX IF NOT EXISTS idx_corr_logs_pair ON correlation_logs(pair_id);
CREATE INDEX IF NOT EXISTS idx_corr_logs_time ON correlation_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_corr_logs_regime ON correlation_logs(regime);
CREATE INDEX IF NOT EXISTS idx_corr_signals_pair ON correlation_signals(pair_id);
CREATE INDEX IF NOT EXISTS idx_corr_signals_outcome ON correlation_signals(outcome);
CREATE INDEX IF NOT EXISTS idx_pyramid_parent ON pyramid_layers(parent_trade_id);
CREATE INDEX IF NOT EXISTS idx_hermes_fusion_time ON hermes_fusion_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_hermes_fusion_symbol ON hermes_fusion_log(symbol);
CREATE INDEX IF NOT EXISTS idx_precision_trade ON precision_entries(trade_id);
-- NEW v2.0:
CREATE INDEX IF NOT EXISTS idx_dynamic_exit_pos ON dynamic_exit_log(position_id);
CREATE INDEX IF NOT EXISTS idx_dynamic_exit_stage ON dynamic_exit_log(stage);
CREATE INDEX IF NOT EXISTS idx_val_sizing_time ON validated_sizing_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_val_sizing_symbol ON validated_sizing_log(symbol);
CREATE INDEX IF NOT EXISTS idx_whale_momentum_time ON whale_momentum_log(timestamp);
```

---

## 4) FEE MODEL INTEGRATION (Mandatory — Enhanced by Pivot 1)

### Current Fee Model

From `src/v25/contracts/fee.py`:
```
FeeModel:
  maker_fee_pct: 0.0002 (0.02%)
  taker_fee_pct: 0.0005 (0.05%)
  spread_estimate_pct: 0.0003 (0.03%)
  slippage_base_pct: 0.0002 (0.02%)
  backtest_cost_mult: 2.0
```

### Pivot 1 Enhancement: Fee-Adjusted Notional

The `compute_validated_size()` function now **deducts estimated round-trip fees from risk_usd BEFORE computing notional**. This means:

```
Traditional:   notional = risk_usd / sl_pct  (fees ignored in sizing)
Validated:     notional = (risk_usd - fee_cost) / sl_pct  (fees pre-deducted)

Where: fee_cost = (risk_usd / sl_pct) * fee_round_trip_pct
       This is circular, so we solve:
       notional = risk_usd / (sl_pct + fee_round_trip_pct)
```

This ensures that the actual risk-on-the-table (including fees) never exceeds `risk_usd`.

### High-Frequency Fee Impact (Pivot 5 context)

```
At 25 trades/day with hyper-precision (mostly maker via limit sniping):
  Daily fee drag: 25 × 2 × 0.02% = 1.0% (round-trip maker)

At 25 trades/day with taker fallback (50% limit fill rate):
  Daily fee drag: 25 × (0.02% + 0.05%) / 2 × 2 = 1.75%

Breakeven-R gate ensures no trade where fees > 30% of risk.
  At 1.5% risk per trade, max acceptable fee = 0.45% notional.
  BingX maker round-trip = 0.04% → well within bounds.
  BingX taker round-trip = 0.10% → still within bounds.
```

---

## 5) VERIFICATION MATRIX (Updated v2.0)

| Component | Verification Command | Expected |
|-----------|---------------------|----------|
| Contracts compile | `python -c "from src.v25.contracts.correlation import CorrelationPair"` | No error |
| Validated sizer | `python -c "from src.risk.validated_sizer import compute_validated_size"` | No error |
| Dynamic exit | `python -c "from src.v25.contracts.exit_strategy import DynamicExitState"` | No error |
| Whale momentum | `python -c "from src.engines.hermes.whale_momentum import compute_whale_momentum"` | No error |
| DB migration | `python -c "from src.v25.db.migrations import run_v25_migrations; run_v25_migrations(':memory:')"` | 21 tables created |
| Breakeven-R gate | `python -m pytest tests/mde/test_breakeven_gate.py -v` | Tests pass |
| Validated sizing math | `python -m pytest tests/risk/test_validated_sizer.py -v` | Tests pass |
| Dynamic exit FSM | `python -m pytest tests/execution/test_dynamic_exit.py -v` | Tests pass |
| Gemini engine | `python -m pytest tests/engines/test_gemini.py -v` | Tests pass |
| Full pipeline | `python src/main.py --mode paper --assets BTC-USDT` | No crash |

---

**End of Technical Blueprint v2.0**
