# ARGUS v2.5 — SYSTEM SPECIFICATION

**Status:** AUTHORITATIVE SPEC — Implementation-Ready  
**Date:** 2026-02-13  
**Supersedes:** CONSTITUTION_V2.md for all v2.5 components  
**Principle:** Basit + Sağlam + Hız Potansiyelli  
**Priority:** Capital Safety > Robustness > Scale > Profit  

---

## 1. FULL SYSTEM MAP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARGUS v2.5 — DUAL-SPEED HEDGE FUND SYSTEM               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 0: DATA PIPELINE                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Binance  │  │ Bybit    │  │CoinGecko │  │ Hermes   │  │ XAU Feed │    │
│  │ WS+REST  │  │ REST     │  │ REST     │  │ News/LLM │  │ (Ph2)    │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └──────────────┴──────────────┴──────────────┴────────────┘          │
│                           │                                                │
│                  ┌────────▼─────────┐                                      │
│                  │    SENTINEL      │  Data Quality Gate [0.0–1.0]         │
│                  └────────┬─────────┘                                      │
│                  ┌────────▼─────────┐                                      │
│                  │ MarketSnapshot   │  Assembles FeatureVector (50 flds)   │
│                  └────────┬─────────┘                                      │
│                           │                                                │
│  LAYER 1: REGIME DETECTION                                                 │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐                     │
│  │ Rule-Based │  │ Volatility   │  │ Microstructure │                     │
│  │(ADX/Hurst) │  │ Classifier   │  │ Classifier     │                     │
│  └──────┬─────┘  └──────┬───────┘  └──────┬─────────┘                     │
│         └───────────────┼──────────────────┘                               │
│                  ┌──────▼───────┐                                           │
│                  │  CONSENSUS   │ → RegimeState                            │
│                  │  (3-of-4)    │   {TREND, CHOP, VOLATILE, CRISIS}        │
│                  └──────┬───────┘                                           │
│                         │                                                  │
│  LAYER 2: SIGNAL QUALITY SYSTEM (SQS)                 ◄── NEW in v2.5     │
│  ┌─────────────────────────────────────────────────┐                       │
│  │  Score [0.0–1.0] composite:                     │                       │
│  │  regime_consistency + trend_structure +          │                       │
│  │  microstructure + fee_adj_expectancy +           │                       │
│  │  hermes_news_risk                               │                       │
│  │                                                 │                       │
│  │  GATE: SQS >= threshold → pass                  │                       │
│  │        SQS <  threshold → REJECT (log + cfact)  │                       │
│  └──────────┬──────────────────────────────────────┘                       │
│             │                                                              │
│  LAYER 3: DUAL-SPEED CAPITAL ENGINE                   ◄── NEW in v2.5     │
│  ┌────────────────────────┐  ┌─────────────────────────┐                  │
│  │     CORE ENGINE        │  │  ACCELERATION ENGINE     │                  │
│  │  80% capital            │  │  20% capital              │                  │
│  │  target: 3–5%/mo       │  │  STRONG_TREND only        │                  │
│  │  leverage: 1.0–2.0x    │  │  alignment >= 95%         │                  │
│  │  all regimes            │  │  SQS >= 0.85              │                  │
│  │  always active          │  │  leverage: up to 3.0x     │                  │
│  │                        │  │  auto-disabled in CHOP     │                  │
│  │  Engines: TITAN,       │  │  CANNOT override risk      │                  │
│  │  NAUTILUS, PHOENIX     │  │  Engine: TITAN only        │                  │
│  └───────────┬────────────┘  └──────────┬──────────────┘                  │
│              └──────────────┬───────────┘                                  │
│                             │                                              │
│  LAYER 4: RISK SAFETY LAYER (RSL)                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Global Veto Power — overrides everything                           │   │
│  │  • Equity Floor (hard_floor_pct × peak_equity)                     │   │
│  │  • Max DD < 12% absolute kill                                       │   │
│  │  • DailyLossCap (-2.5%)                                             │   │
│  │  • Per-trade risk cap (3%)                                           │   │
│  │  • 5-level Kill Switch FSM                                           │   │
│  │  • Core + Accel share SAME risk pool                                │   │
│  └──────────┬──────────────────────────────────────────────────────────┘   │
│             │                                                              │
│  LAYER 5: EXECUTION                                                        │
│  Order Router → 4 Urgency Levels → Exchange-Side SL (MANDATORY) →         │
│  Reconciler                                                                │
│             │                                                              │
│  LAYER 6: TELEMETRY + FEEDBACK                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Trade    │  │ Edge     │  │Reflector │  │Experiment│                  │
│  │ Logger   │  │ Health   │  │(Bounded) │  │ Manager  │                  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                  │
│                                                                             │
│  LAYER 7: EVOLUTION (OFFLINE)                          ◄── NEW in v2.5     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                                │
│  │ Darwin   │  │HyperSizer│  │ Time     │                                │
│  │ (GA Opt) │  │(Adaptive)│  │ Machine  │                                │
│  └──────────┘  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow (Canonical Path)

```
Candle Close
  → Binance WS/REST → Raw OHLCV + OB + Funding + OI
  → Sentinel validates → data_quality_score
  → Snapshot Builder → MarketSnapshot (frozen) + FeatureVector (50 fields)
  → Regime Detector → RegimeState {TREND|CHOP|VOLATILE|CRISIS}
  → SQS Gate → SignalQualityScore [0.0–1.0]
     ├─ PASS (>= threshold) → Engine Portfolio
     └─ FAIL (< threshold) → CounterfactualLog + HOLD
  → Engine Selection (regime routes to lead engine)
  → ATLAS risk overlay → risk_multiplier [0.0–1.5]
  → Capital Router:
     ├─ Core Engine (80%) → always active
     └─ Accel Engine (20%) → only if STRONG_TREND + alignment>=95% + SQS>=0.85
  → RSL (8 pre-trade checks + Kill Switch) → RiskVerdict
     ├─ APPROVED → Execution Engine
     └─ REJECTED → CounterfactualLog
  → Order Router → Exchange → Fill → SL Placement (MANDATORY)
  → Telemetry → TradeRecord + LedgerEvent
  → Edge Health Monitor → Reflector → bounded AdjustmentVector
```

### Phase Architecture

```
Phase 1 (Month 1–9):
  Asset: BTC only (highest liquidity)
  Goal:  Prove edge, stable compounding
  Accel: Inactive (architecture present, not activated)
  XAU:   Architecture stub only

Phase 2 (Month 10+):
  Asset: BTC + XAU
  Goal:  Dynamic allocation, decorrelation benefit
  Accel: Active when conditions met
  Multi: Full dual-asset regime detection
```

---

## 2. CANONICAL DATA CONTRACTS

All contracts use `pydantic v2` with `frozen=True, strict=True, extra="forbid"`.  
No NaN may propagate past Layer 0.

### 2.1 MarketSnapshot

```
MarketSnapshot:
  timestamp:         datetime          # UTC candle close time
  symbol:            str               # "BTCUSDT" | "XAUUSD"
  timeframe:         str               # "1h" | "4h" | "1d"
  open:              float             # > 0
  high:              float             # >= open
  low:               float             # <= open
  close:             float             # > 0
  volume:            float             # >= 0
  quote_volume:      float             # >= 0
  trades_count:      int               # >= 0
  funding_rate:      Optional[float]   # None for non-perp
  open_interest:     Optional[float]   # None if unavailable
  mark_price:        Optional[float]   # futures mark price
  orderbook_bids_5:  list[tuple[float, float]]  # top 5 [price, qty]
  orderbook_asks_5:  list[tuple[float, float]]  # top 5 [price, qty]
  data_quality_score: float            # [0.0–1.0] from Sentinel
  source:            str               # "binance" | "bybit"
```

### 2.2 FeatureVector

Inherits all 50 fields from Constitution v2.0 Section 5.1 — no changes.  
(Volatility 6 + Trend 6 + Momentum 5 + Volume 5 + Microstructure 5 + CryptoNative 7 + CrossAsset 4 + Statistical 4 + ML 8)

### 2.3 RegimeState

```
RegimeState:
  regime:              str             # "TREND" | "CHOP" | "VOLATILE" | "CRISIS"
  sub_regime:          Optional[str]   # "STRONG_TREND" | "WEAK_TREND" | null
  confidence:          float           # [0.0–1.0]
  stability:           float           # [0.0–1.0]
  direction:           Optional[int]   # +1 (bull) / -1 (bear) / None
  pending_transition:  Optional[str]   # target regime if in confirmation
  candles_in_regime:   int             # >= 0
  rule_regime:         str             # raw output from rule-based classifier
  ml_regime:           str             # raw output from ML classifier
  chop_midpoint:       Optional[float] # midpoint price in CHOP (no-trade zone center)
  timestamp:           datetime
```

**CHANGE from v2.0:** `RANGING` → `CHOP`. Added `sub_regime` and `chop_midpoint`.

### 2.4 Signal

```
Signal:
  engine:              str             # "TITAN" | "NAUTILUS" | "PHOENIX"
  sub_strategy:        str             # "trend_follow" | "breakout" | "bb_reversion" etc.
  bias:                str             # "long" | "short"
  confidence:          float           # [0.0–1.0]
  stop_distance:       float           # (0.0–0.05]
  take_profit_distance: float          # > 0
  expected_return:     float           # before fees
  atr:                 float           # ATR(14) at signal time
  regime_at_signal:    str             # regime when signal was generated
  timestamp:           datetime
```

### 2.5 SignalQualityScore

```
SignalQualityScore:
  total_score:              float      # [0.0–1.0]  weighted composite
  regime_consistency:       float      # [0.0–1.0]  weight: 0.25
  trend_range_structure:    float      # [0.0–1.0]  weight: 0.20
  microstructure_quality:   float      # [0.0–1.0]  weight: 0.20
  fee_adjusted_expectancy:  float      # [0.0–1.0]  weight: 0.20
  hermes_news_risk:         float      # [0.0–1.0]  weight: 0.15
  passed:                   bool       # total_score >= threshold
  threshold_used:           float      # dynamic threshold
  reason_if_failed:         Optional[str]
  timestamp:                datetime
```

### 2.6 ConfidenceState

```
ConfidenceState:
  alignment_score:     float           # [0.0–1.0]  multi-TF agreement
  regime_confidence:   float           # [0.0–1.0]  from RegimeState
  signal_confidence:   float           # [0.0–1.0]  from Signal
  sqs_score:           float           # [0.0–1.0]  from SQS
  atlas_multiplier:    float           # [0.0–1.5]  from ATLAS overlay
  composite:           float           # [0.0–1.0]  final blended confidence
  accel_eligible:      bool            # true if all accel conditions met
  timestamp:           datetime
```

### 2.7 TradeDecision

```
TradeDecision:
  action:              str             # "long"|"short"|"hold"|"close_all"|"reduce"
  capital_engine:      str             # "core" | "accel"
  position_size_pct:   float           # [0.0–0.15] of total equity
  leverage:            float           # [1.0–3.0]
  stop_loss_pct:       float           # [0.01–0.05]
  take_profit_pct:     float           # > 0
  confidence:          float           # [0.0–1.0]
  engine:              Optional[str]   # which engine generated
  sub_strategy:        Optional[str]   # which sub-strategy
  reason:              str             # human-readable
  sqs_at_decision:     float           # SQS score at decision time
  regime_at_decision:  str
  timestamp:           datetime
```

### 2.8 SizingDecision

```
SizingDecision:
  raw_risk_pct:        float           # before any multipliers
  atlas_mult:          float
  sentinel_mult:       float
  regime_conf_mult:    float
  dd_mult:             float
  rsl_mult:            float
  equity_curve_mult:   float           # 1.0 if above MA(20d), 0.5 if below
  final_risk_pct:      float           # clamped [0.005–0.03]
  position_size_pct:   float           # final_risk_pct / stop_distance, clamped [0.0–0.15]
  leverage:            float           # [1.0–3.0]
  capital_engine:      str             # "core" | "accel"
  kelly_fraction:      Optional[float] # None until 500+ trades
  timestamp:           datetime
```

### 2.9 ExecutionPlan

```
ExecutionPlan:
  order_type:          str             # "market"|"limit"|"aggressive_limit"|"passive_limit"
  urgency:             str             # "EMERGENCY"|"HIGH"|"NORMAL"|"LOW"
  side:                str             # "buy"|"sell"
  symbol:              str
  quantity:            float
  price:               Optional[float] # None for market orders
  sl_price:            float           # MANDATORY
  tp_price:            Optional[float]
  timeout_ms:          int             # order timeout
  max_slippage_pct:    float           # max acceptable slippage
  timestamp:           datetime
```

### 2.10 PositionState

```
PositionState:
  position_id:         str             # UUID
  symbol:              str
  side:                str             # "long" | "short"
  capital_engine:      str             # "core" | "accel"
  size:                float
  entry_price:         float
  current_price:       float
  unrealized_pnl:      float
  unrealized_pnl_pct:  float
  sl_price:            float
  tp_price:            Optional[float]
  trailing_sl:         Optional[float]
  entry_time:          datetime
  duration_hours:      float
  exchange_sl_order_id: str            # MUST exist
  engine:              str
  sub_strategy:        str
  regime_at_entry:     str
  sqs_at_entry:        float
  confidence_at_entry: float
```

### 2.11 LedgerEvent

```
LedgerEvent:
  event_id:            str             # UUID
  event_type:          str             # "trade_open"|"trade_close"|"fee"|"funding"|
                                       # "rebalance"|"sl_hit"|"tp_hit"|"liquidation"|
                                       # "kill_switch_close"|"manual_close"
  symbol:              str
  capital_engine:      str             # "core" | "accel"
  amount:              float           # signed: + for credit, - for debit
  balance_after:       float
  equity_after:        float
  position_id:         Optional[str]
  metadata:            dict            # flexible payload per event_type
  timestamp:           datetime
```

### 2.12 RiskVerdict (unchanged from v2.0)

```
RiskVerdict:
  approved:            bool
  reason:              str
  adjusted_decision:   Optional[TradeDecision]
  risk_level:          int             # [0–4] kill switch level
```

### 2.13 TradeRecord (extended from v2.0)

```
TradeRecord:
  trade_id:            str
  symbol:              str
  side:                str
  capital_engine:      str             # NEW: "core" | "accel"
  entry_time:          datetime
  exit_time:           datetime
  entry_price:         float
  exit_price:          float
  size:                float
  pnl:                 float
  pnl_pct:             float
  fees:                float
  slippage:            float
  net_pnl_pct:         float
  regime_at_entry:     str
  regime_at_exit:      str
  engine:              str
  sub_strategy:        str
  confidence_at_entry: float
  sqs_at_entry:        float           # NEW
  stop_distance:       float
  duration_hours:      float
  features_at_entry:   dict
  reason_entry:        str
  reason_exit:         str
```

---

*Continued in ARGUS_V25_SPEC_PART2.md*
