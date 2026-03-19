# ARGUS CONSTITUTION v2.0

**Status:** AUTHORITATIVE — Single Source of Truth  
**Created:** 2026-02-10  
**Author:** Chief Quant Architect (Opus)  
**Supersedes:** All previous architectural documents, including FUTURE_VISION.md Sections 0-32  
**Rule:** If ANY other document contradicts this Constitution, THIS DOCUMENT WINS.

---

## Table of Contents

1. [System Identity & Scope](#1-system-identity--scope)
2. [Operating Modes](#2-operating-modes)
3. [One-Page Architecture (32A)](#3-one-page-architecture-32a)
4. [Module Boundaries & File Tree (32B)](#4-module-boundaries--file-tree-32b)
5. [Data Contracts](#5-data-contracts)
6. [Decision Pipeline (32C)](#6-decision-pipeline-32c)
7. [Regime State Machine (32D)](#7-regime-state-machine-32d)
8. [Kill Switch FSM (32E)](#8-kill-switch-fsm-32e)
9. [Telemetry Schemas (32F)](#9-telemetry-schemas-32f)
10. [Config Contracts (32G)](#10-config-contracts-32g)
11. [Test Matrix (32H)](#11-test-matrix-32h)
12. [Implementation Phases (32I)](#12-implementation-phases-32i)
13. [Mathematical Foundations](#13-mathematical-foundations)
14. [Removal & Deprecation Criteria](#14-removal--deprecation-criteria)
15. [Priority Hierarchy](#15-priority-hierarchy)

---

## 1. System Identity & Scope

```
Name:           ARGUS v2.0
Type:           Multi-regime algorithmic trading system
Deployment:     Windows laptop (i7-11800H, 32GB RAM, RTX A3000M 6GB)
Runtime:        24/7 autonomous with human oversight
Capital:        $100 initial, scaling over 4 years
Language:       Python 3.11+
Framework:      asyncio + ccxt + pandas + LightGBM + PyTorch (research only)
```

### Priority Hierarchy (Non-Negotiable)

```
Capital Safety > Robustness > Scale > Profit
```

Every architectural decision in this document is governed by this ordering. If a feature increases profit but reduces safety, it is rejected.

---

## 2. Operating Modes

ARGUS operates in two distinct modes, sharing common infrastructure but differing in decision-making.

### 2.1 CRYPTO MODE (Year 1 — Active)

| Property | Value |
|----------|-------|
| **Decision style** | Regime-based ROUTING (not voting) |
| **Engines** | TITAN (trend), NAUTILUS (mean-rev), PHOENIX (carry) |
| **Overlays** | ATLAS (risk governor), SENTINEL (data quality) |
| **Regime states** | 4: TRENDING, RANGING, VOLATILE, CRISIS |
| **Markets** | Binance Futures (primary), Bybit (secondary) |
| **Pairs (v2.0)** | BTCUSDT, ETHUSDT only |
| **Timeframe** | 1h primary, 4h confirmation, 1d direction |
| **Sizing** | Fixed fractional, 2% base risk |

**Why routing, not voting:** The market rewards conviction, not compromise. Averaging a strong sell with a weak buy produces noise. One engine leads per regime. Atlas modifies size. RSL approves or kills. Command chain, not committee.

### 2.2 STOCKS MODE (Year 2+ — Planned)

| Property | Value |
|----------|-------|
| **Decision style** | Bounded VOTING COUNCIL |
| **Engines** | Technical, Fundamental, Macro, Sentiment (genuinely different data domains) |
| **Markets** | Alpaca/IBKR (US equities), IS Yatirim API (BIST) |
| **Pairs** | SPY, QQQ, select tech stocks; XU100, THYAO, ASELS |
| **Timeframe** | 1d primary (stocks are slower) |
| **Sizing** | Fixed fractional, 1.5% base risk (lower due to leverage constraints) |

**Why voting for stocks:** Unlike crypto where all engines consume the same price data, stock engines can access genuinely independent data domains: price/TA, financial statements, macroeconomic indicators, and news sentiment. True independence justifies voting.

**Council rules:**
- Each engine casts a vote: LONG (+1), NEUTRAL (0), SHORT (-1), weighted by confidence
- Minimum 3-of-4 directional agreement required to act
- Risk gates (RSL, Sentinel) remain identical to Crypto Mode
- ATLAS overlay applies macro-level multiplier

### 2.3 Shared Infrastructure (Both Modes)

| Component | Shared? | Notes |
|-----------|---------|-------|
| SENTINEL (data quality) | Yes | Different checks per asset class |
| RSL (risk safety layer) | Yes | Same 5-level kill switch |
| Telemetry | Yes | Same event schemas, different sources |
| Pydantic contracts | Yes | Base models shared, asset-specific extensions |
| Config system | Yes | YAML per mode, merged with base |
| Kill switch | Yes | Same FSM, same thresholds |
| Execution layer | No | Different exchange adapters per mode |

---

## 3. One-Page Architecture (32A)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARGUS ALL-WEATHER FUND MANAGEMENT SYSTEM                  │
│                          Constitution v2.0                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 0: DATA                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐                 │
│  │ Binance  │  │ Bybit    │  │CoinGecko │  │CryptoPanic │                 │
│  │ WS+REST  │  │ REST     │  │ REST     │  │ REST       │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬─────┘                 │
│       └──────────────┴──────────────┴──────────────┘                        │
│                           │                                                  │
│                  ┌────────▼─────────┐                                        │
│                  │    SENTINEL      │  Data Quality Gate (score 0.0-1.0)     │
│                  └────────┬─────────┘                                        │
│                  ┌────────▼─────────┐                                        │
│                  │ SNAPSHOT BUILDER │  50 Features + FeatureVector           │
│                  └────────┬─────────┘                                        │
│                           │                                                  │
│  LAYER 1: REGIME DETECTION                                                   │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐                       │
│  │ Rule-Based │  │ Volatility   │  │ Microstructure │                       │
│  │ (ADX/Hurst)│  │ Classifier   │  │ Classifier     │                       │
│  └──────┬─────┘  └──────┬───────┘  └──────┬─────────┘                       │
│         └───────────────┼──────────────────┘                                 │
│                  ┌──────▼───────┐                                             │
│                  │  CONSENSUS   │  → RegimeState (TRENDING|RANGING|          │
│                  │  (3-of-4)    │    VOLATILE|CRISIS)                         │
│                  └──────┬───────┘                                             │
│                         │                                                    │
│  LAYER 2: ENGINE PORTFOLIO                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                                  │
│  │  TITAN   │  │ NAUTILUS │  │ PHOENIX  │                                  │
│  │ Trend/Mom│  │ Mean-Rev │  │Carry/Basi│                                  │
│  │ TRENDING │  │ RANGING  │  │ ALL-CRISI│                                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                                  │
│       └──────────────┼─────────────┘                                         │
│              ┌───────▼───────┐                                               │
│              │    ATLAS      │  Risk Multiplier [0.0, 1.5]                   │
│              └───────┬───────┘                                               │
│                      │                                                       │
│  LAYER 3: MDE (ROUTING)                                                      │
│  Gate 0: Sentinel → Gate 1: Crisis → Gate 2: RSL → Gate 3: Signal →        │
│  Gate 4: Confidence → Gate 5: Net Return → Gate 6: R:R →                    │
│  SIZING (fixed fractional) → Decision                                        │
│                      │                                                       │
│  LAYER 4: RISK (RSL)                                                         │
│  8 Pre-Trade Checks → Kill Switch (5 levels) → RiskVerdict                  │
│                      │                                                       │
│  LAYER 5: EXECUTION                                                          │
│  Order Router → 4 Urgency Levels → Exchange-Side SL (MANDATORY) →           │
│  Reconciler                                                                  │
│                      │                                                       │
│  LAYER 6: TELEMETRY                                                          │
│  Trade Logger → Feature Drift → Performance Attribution → Decay Detector    │
│                      │                                                       │
│  LAYER 7: OPS + INTERFACE                                                    │
│  Supervisor → Dashboard → Telegram Bot → Health Endpoints                    │
│                                                                             │
│  RESEARCH NODE (OFFLINE — never in live path)                                │
│  GPU Training → Walk-Forward → Hyperopt → Model Registry                    │
└─────────────────────────────────────────────────────────────────────────────┘

KEY INVARIANT: Data flows DOWN through layers. No layer may call upward.
Exception: Kill Switch (Layer 4) can halt Execution (Layer 5) directly.
```

---

## 4. Module Boundaries & File Tree (32B)

### 4.1 Authoritative Directory Structure

```
argus-terminal/
├── pyproject.toml                     # Python 3.11+, uv/pip
├── requirements.txt                   # Pinned production dependencies
├── requirements-research.txt          # GPU/ML dependencies (research only)
├── .env.example
├── Makefile                           # lint, test, type-check shortcuts
│
├── config/
│   ├── base.yaml                      # Shared defaults
│   ├── production.yaml                # Live trading overrides
│   ├── paper.yaml                     # Paper trading overrides
│   ├── backtest.yaml                  # Backtest overrides
│   ├── regimes.yaml                   # Regime thresholds
│   ├── engines.yaml                   # Per-engine parameters
│   ├── risk.yaml                      # RSL thresholds, kill switch triggers
│   └── telemetry.yaml                 # Event types, destinations
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                          # SHARED KERNEL (no business logic)
│   │   ├── types.py                   # All pydantic v2 models (frozen, strict)
│   │   ├── config.py                  # YAML loader, typed config objects
│   │   ├── events.py                  # EventBus (pub/sub), 17 event types
│   │   ├── clock.py                   # Unified clock (live=real, backtest=sim)
│   │   ├── exceptions.py              # Custom exceptions
│   │   └── constants.py               # Magic numbers with docstrings
│   │
│   ├── data/                          # LAYER 0: DATA PIPELINE
│   │   ├── ingest/
│   │   │   ├── binance_ws.py          # WebSocket: OHLCV, mark price, funding, OB
│   │   │   ├── binance_rest.py        # REST fallback: OI, liquidations, historical
│   │   │   ├── bybit_rest.py          # Cross-validation source
│   │   │   ├── coingecko.py           # BTC dominance, total market cap
│   │   │   └── fear_greed.py          # CryptoPanic fear/greed
│   │   ├── sentinel/
│   │   │   ├── validator.py           # 6 health checks, data_quality_score
│   │   │   └── anomaly.py             # Statistical anomaly flags
│   │   ├── features/
│   │   │   ├── technical.py           # Volatility(6) + Trend(6) + Momentum(5)
│   │   │   ├── volume.py              # Volume(5)
│   │   │   ├── microstructure.py      # Microstructure(5)
│   │   │   ├── crypto_native.py       # Crypto-Native(7)
│   │   │   ├── cross_asset.py         # Cross-Asset(4)
│   │   │   ├── statistical.py         # Statistical(4)
│   │   │   └── ml_features.py         # ML Output(8) — wraps model inference
│   │   ├── store/
│   │   │   ├── parquet_store.py       # Warm storage: partitioned by month
│   │   │   └── sqlite_store.py        # Trade logs, decision logs, immutable
│   │   └── snapshot.py                # Assembles MarketSnapshot + FeatureVector
│   │
│   ├── regime/                        # LAYER 1: REGIME DETECTION
│   │   ├── rule_based.py              # ADX + Hurst + ATR ratio + price/MA
│   │   ├── volatility_classifier.py   # Realized vol vs median
│   │   ├── microstructure_cls.py      # Spread + depth + flow regime hints
│   │   ├── consensus.py               # 3-of-4 vote, confirmation window
│   │   └── state_machine.py           # Full state machine (Section 7)
│   │
│   ├── engines/                       # LAYER 2: ENGINE PORTFOLIO
│   │   ├── base.py                    # AbstractEngine protocol
│   │   ├── titan/
│   │   │   ├── engine.py              # TitanEngine(AbstractEngine)
│   │   │   ├── trend_follow.py        # EMA cross + ADX + ATR trailing
│   │   │   └── breakout.py            # Donchian breakout + volume
│   │   ├── nautilus/
│   │   │   ├── engine.py              # NautilusEngine(AbstractEngine)
│   │   │   ├── bb_reversion.py        # Bollinger Band reversion + RSI
│   │   │   └── funding_reversion.py   # Funding rate mean-reversion
│   │   ├── phoenix/
│   │   │   ├── engine.py              # PhoenixEngine(AbstractEngine)
│   │   │   ├── funding_harvest.py     # Funding rate carry
│   │   │   └── basis_trade.py         # Spot-perp basis arbitrage
│   │   └── atlas/
│   │       └── risk_overlay.py        # Macro signals → risk_multiplier [0.0, 1.5]
│   │
│   ├── mde/                           # LAYER 3: META-DECISION ENGINE
│   │   ├── router.py                  # Regime → lead engine selection
│   │   ├── gates.py                   # 7 sequential gates (Gate 0-6)
│   │   └── sizing.py                  # Fixed fractional position sizing
│   │
│   ├── risk/                          # LAYER 4: RISK SAFETY LAYER (RSL)
│   │   ├── rsl.py                     # RSL controller: level management
│   │   ├── pre_trade.py               # 8 pre-trade checks
│   │   ├── drawdown.py                # DD tracking, peak equity, MA(20d)
│   │   ├── kill_switch.py             # 5-level kill switch FSM (Section 8)
│   │   └── cooldown.py                # Post-loss cooldown logic
│   │
│   ├── execution/                     # LAYER 5: EXECUTION
│   │   ├── executor.py                # Decision → exchange orders
│   │   ├── order_router.py            # Urgency-based order type selection
│   │   ├── sl_manager.py              # Exchange-side SL placement + verify
│   │   └── reconciler.py              # Fill verification, position state
│   │
│   ├── telemetry/                     # LAYER 6: TELEMETRY
│   │   ├── trade_logger.py            # TradeRecord persistence
│   │   ├── event_logger.py            # All telemetry events
│   │   ├── attribution.py             # Per-engine P&L attribution
│   │   ├── drift_detector.py          # Feature distribution drift
│   │   └── decay_detector.py          # Strategy performance decay
│   │
│   ├── ops/                           # LAYER 7: OPS
│   │   ├── supervisor.py              # Watchdog, heartbeat, restart
│   │   ├── health.py                  # Health check HTTP endpoint
│   │   └── alerts.py                  # Alert routing (Telegram, log)
│   │
│   ├── interface/                     # LAYER 7: USER INTERFACE
│   │   ├── telegram_bot.py            # /status, /stop, /pnl, /regime
│   │   └── dashboard.py               # Streamlit (optional, Phase 3+)
│   │
│   ├── ml/                            # RESEARCH NODE (offline)
│   │   ├── chronos/
│   │   │   ├── predictor.py           # Inference wrapper
│   │   │   └── fine_tune.py           # LoRA fine-tuning
│   │   ├── lgbm_model.py              # LightGBM direction classifier
│   │   ├── meta_labeler.py            # Triple-barrier meta-labeling
│   │   ├── model_registry.py          # Artifact versioning
│   │   └── training/
│   │       ├── walk_forward.py        # Walk-forward CV
│   │       ├── feature_eng.py         # Feature engineering
│   │       └── hyperopt.py            # Optuna hyperparameter search
│   │
│   ├── backtest/                      # BACKTEST ENGINE
│   │   ├── backtester.py              # Event-driven backtester
│   │   ├── walk_forward.py            # Walk-forward harness
│   │   ├── monte_carlo.py             # Monte Carlo permutation
│   │   ├── fee_model.py               # Realistic fee + slippage
│   │   └── regime_stress.py           # Per-regime stress testing
│   │
│   └── main.py                        # Entry point, mode selection
│
├── tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── unit/                          # Per-module unit tests
│   ├── integration/                   # Cross-module integration
│   └── stress/                        # Crash, regime flip scenarios
│
├── scripts/
│   ├── run_live.py
│   ├── run_paper.py
│   ├── run_backtest.py
│   ├── verify_gpu.py
│   ├── train_models.py
│   └── promote_model.py
│
├── data/
│   ├── ohlcv/                         # Parquet files
│   ├── models/                        # Trained model artifacts
│   ├── backtest_results/
│   └── trade_logs/
│
└── Docs/
    ├── CONSTITUTION_V2.md             # THIS DOCUMENT
    ├── FUTURE_VISION.md               # ARCHIVED — historical reference
    ├── FUTURE_VISION_REVIEW.md        # Section-by-section review
    ├── YEAR2_PLUS_EXECUTION_PLAN.md   # Sprint C/D/E plan
    └── CODEX_YEAR2_PROMPT.md          # Codex implementation prompt
```

### 4.2 Module Boundary Contracts

| Module | Inputs | Outputs | Key Invariant |
|--------|--------|---------|---------------|
| `data.ingest` | Exchange APIs | Raw OHLCV, OB, funding | Reconnect within 30s on failure |
| `data.sentinel` | Raw data | `data_quality_score: float` | Score < 0.4 halts all trading |
| `data.features` | Raw data | `FeatureVector` (50 fields) | All features < 2000ms |
| `data.snapshot` | Features + OB | `MarketSnapshot` | Immutable once created |
| `regime` | `FeatureVector` | `RegimeState` | Transition requires confirmation |
| `engines.titan` | Snapshot + Regime | `Optional[EngineSignal]` | Only in TRENDING |
| `engines.nautilus` | Snapshot + Regime | `Optional[EngineSignal]` | Only in RANGING |
| `engines.phoenix` | Snapshot + Regime | `Optional[EngineSignal]` | All except CRISIS |
| `engines.atlas` | Snapshot + Regime | `risk_multiplier: float` | Output in [0.0, 1.5] |
| `mde` | Signals + Regime + RSL | `Decision` | One lead engine per regime |
| `risk` | Decision + Portfolio | `RiskVerdict` | Can ONLY reject/reduce, never amplify |
| `execution` | Approved Decision | `ExecutionResult` | Exchange SL MUST exist before confirm |
| `telemetry` | All layer events | Persisted events | Every decision logged, no exceptions |

---

## 5. Data Contracts

All data objects use **pydantic v2** with `frozen=True` and `strict=True`. No mutable state. No NaN propagation — any NaN triggers rejection + log.

### 5.1 Core Types

```python
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class ArgusModel(BaseModel):
    """Base for all ARGUS data objects."""
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

class FeatureVector(ArgusModel):
    """Immutable. Computed once per candle close. All 50 values populated."""
    timestamp: datetime
    symbol: str

    # Volatility (6)
    atr_14: float
    atr_14_pct: float              # ATR(14) / close
    atr_ratio_5_20: float          # ATR(5) / ATR(20)
    realized_vol_20d: float
    parkinson_vol: float
    bb_width: float

    # Trend (6)
    adx_14: float
    price_vs_ma200: float          # (close - MA200) / MA200
    ema_21_vs_55: float            # (EMA21 - EMA55) / EMA55
    lr_slope_20: float
    supertrend_dir: int            # +1 / -1
    aroon_osc: float               # -100 to +100

    # Momentum (5)
    rsi_14: float
    bb_pct_b: float
    roc_10: float
    willr_14: float
    cci_20: float

    # Volume (5)
    volume_ratio: float            # volume / SMA(volume, 20)
    obv_slope_10: float
    vwap_dev_pct: float
    cmf_20: float
    volume_delta: float

    # Microstructure (5)
    spread_pct: float
    orderbook_imbalance: float
    trade_flow_imbalance: float
    depth_ratio: float
    large_trade_ratio: float

    # Crypto-Native (7)
    funding_rate: float
    funding_pctile_30d: float
    oi_change_4h_pct: float
    oi_change_24h_pct: float
    liquidation_est: float
    long_short_ratio: float
    basis_pct: float

    # Cross-Asset (4)
    btc_dominance_delta_24h: float
    btc_eth_corr_30d: float
    total_mcap_momentum: float
    stablecoin_flow: float

    # Statistical (4)
    return_autocorr_20: float
    hurst_exponent: float
    entropy_50: float
    frac_diff_price: float

    # ML Output (8) — None if models not active
    chronos_forecast_1h: Optional[float] = None
    chronos_confidence_width: Optional[float] = None
    lgbm_direction: Optional[int] = None
    lgbm_confidence: Optional[float] = None
    meta_label_score: Optional[float] = None
    regime_prob_trending: Optional[float] = None
    regime_prob_ranging: Optional[float] = None
    regime_prob_volatile: Optional[float] = None


class RegimeState(ArgusModel):
    regime: str                    # "TRENDING" | "RANGING" | "VOLATILE" | "CRISIS"
    confidence: float = Field(ge=0.0, le=1.0)
    stability: float = Field(ge=0.0, le=1.0)
    direction: Optional[int] = None  # +1 (bull) / -1 (bear) / None
    pending_transition: Optional[str] = None
    candles_in_regime: int = Field(ge=0)
    rule_regime: str
    ml_regime: str
    timestamp: datetime


class EngineSignal(ArgusModel):
    engine: str                    # "TITAN" | "NAUTILUS" | "PHOENIX"
    sub_strategy: str
    bias: str                      # "long" | "short"
    confidence: float = Field(ge=0.0, le=1.0)
    stop_distance: float = Field(gt=0.0, le=0.05)
    expected_return: float
    atr: float


class Decision(ArgusModel):
    action: str                    # "long" | "short" | "hold" | "close_all" | "reduce"
    position_size: float = Field(ge=0.0, le=0.15)
    leverage: float = Field(ge=1.0, le=3.0)
    stop_loss: float = Field(ge=0.0, le=0.05)
    take_profit: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    engine: Optional[str] = None
    reason: str
    timestamp: datetime


class RiskVerdict(ArgusModel):
    approved: bool
    reason: str
    adjusted_decision: Optional[Decision] = None
    risk_level: int = Field(ge=0, le=4)


class ExecutionResult(ArgusModel):
    success: bool
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None
    slippage: Optional[float] = None
    fees: Optional[float] = None
    sl_order_id: Optional[str] = None
    reason: str
    timestamp: datetime


class Position(ArgusModel):
    symbol: str
    side: str                      # "long" | "short"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sl_price: float
    tp_price: Optional[float] = None
    entry_time: datetime
    duration_hours: float
    exchange_sl_order_id: str      # MUST exist


class PortfolioState(ArgusModel):
    total_equity: float
    available_balance: float
    positions: list[Position]
    has_positions: bool
    daily_pnl: float
    daily_pnl_pct: float
    drawdown: float
    peak_equity: float
    trades_today: int
    consecutive_losses: int
    equity_ma_20d: float
    timestamp: datetime


class TradeRecord(ArgusModel):
    trade_id: str
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fees: float
    slippage: float
    net_pnl_pct: float
    regime_at_entry: str
    regime_at_exit: str
    engine: str
    sub_strategy: str
    confidence_at_entry: float
    stop_distance: float
    duration_hours: float
    features_at_entry: dict
    reason_entry: str
    reason_exit: str               # "stop_loss" | "take_profit" | "signal_reversal" | "kill_switch"
```

### 5.2 NaN Policy

```
RULE: No NaN may propagate past Layer 0 (Data).

If any feature is NaN:
  1. Log: {timestamp, feature_name, source, reason}
  2. Action depends on feature tier:
     - Tier 1 (core 25): HALT pipeline for this candle. Use last valid snapshot.
     - Tier 2 (derived 15): Set to None. Reduce sentinel score by 0.1.
     - Tier 3 (structural 10): Set to None. No penalty.
  3. If >5 Tier 1 features are NaN: sentinel_score = 0.0 → HALT all trading.
```

### 5.3 Data Flow Contract

```
MarketSnapshot → FeatureVector → Sentinel validates
FeatureVector → RegimeDetector → RegimeState
(FeatureVector, RegimeState) → Engine → Optional[EngineSignal]
(RegimeState, signals, portfolio, risk) → MDE → Decision
(Decision, PortfolioState) → RSL → RiskVerdict
Decision (approved) → ExecutionEngine → ExecutionResult
(Decision, ExecutionResult, RegimeState, FeatureVector) → Telemetry → TradeRecord
```

---

## 6. Decision Pipeline (32C)

Every trading decision follows this exact 10-step pipeline. No shortcuts, no bypasses.

### Step 1: Data Acquisition (Layer 0)
- **Trigger:** New 1h candle close
- **Sources:** Binance WS (OHLCV, mark price, funding, OB L2), Binance REST (OI, liquidations), Bybit REST (cross-validation), CoinGecko (BTC.D, total mcap), CryptoPanic (fear/greed)
- **Output:** Raw data buffers
- **Latency budget:** < 500ms

### Step 2: Sentinel Validation (Layer 0)
- **6 checks:** Data staleness, price anomaly, spread blowout, exchange latency, OB depth collapse, funding flash spike
- **Output:** `data_quality_score` (0.0-1.0)
- **Decision:** >= 0.7 proceed | 0.4-0.7 reduce confidence 30% | < 0.4 HALT | < 0.2 EMERGENCY close all
- **Latency budget:** < 100ms

### Step 3: Snapshot Build (Layer 0)
- **Compute:** 50 features (FeatureVector)
- **Assemble:** MarketSnapshot (frozen, immutable)
- **Latency budget:** < 2000ms

### Step 4: Regime Detection (Layer 1)
- **Classifiers:** Rule-based, Volatility, Microstructure, (future) ML
- **Consensus:** 3-of-4 for TRENDING/RANGING. Any 1 for VOLATILE/CRISIS.
- **State machine:** Apply hysteresis, confirmation window, transition rules (Section 7)
- **Output:** RegimeState (frozen)
- **Latency budget:** < 200ms

### Step 5: Engine Signal Generation (Layer 2)
- **ATLAS** computes `risk_multiplier` [0.0, 1.5]
- **Route** to lead engine: TRENDING→TITAN, RANGING→NAUTILUS, VOLATILE→PHOENIX, CRISIS→None
- **Lead engine** generates signal with MIN_CONFIDENCE = 0.55
- **PHOENIX** always runs as fallback (except CRISIS)
- **Output:** `Optional[EngineSignal]`
- **Latency budget:** < 500ms per engine

### Step 6: MDE Routing + Gates (Layer 3)

7 sequential gates (ALL must pass):

| Gate | Check | Fail Action |
|------|-------|-------------|
| 0 | `sentinel_score < 0.4` | HOLD ("Data quality critical") |
| 1 | `regime == CRISIS` | CLOSE_ALL or HOLD |
| 2 | `rsl_level >= 3` | HOLD; `>= 2` → only PHOENIX |
| 3 | `signal is None` | HOLD ("No valid signal") |
| 4 | `confidence < 0.55` | HOLD ("Low confidence") |
| 5 | `net_expected_return < 0.001` | HOLD ("Insufficient edge") |
| 6 | `reward_risk_ratio < 1.5` | HOLD ("Bad R:R") |

**Sizing (all gates passed):**
```
risk_per_trade = 0.02 × atlas_mult × sentinel × regime_conf × dd_mult × rsl_mult
risk_per_trade = clamp(risk_per_trade, 0.005, 0.03)
position_size  = risk_per_trade / stop_distance
position_size  = clamp(position_size, 0.0, 0.15)
```

- **Output:** Decision (frozen)
- **Latency budget:** < 100ms

### Step 7: Risk Verification (Layer 4)

8 pre-trade checks (ALL must pass):

| # | Check | Limit |
|---|-------|-------|
| 1 | Position size | <= 0.15 |
| 2 | Leverage | <= 2.0 (Year 1) |
| 3 | Trades today | < 15 |
| 4 | Funding settlement proximity | Not within 15min |
| 5 | Weekend limit | Position size × 0.5 on weekends |
| 6 | Correlation with existing positions | < 0.6 |
| 7 | Stop loss exists | > 0 |
| 8 | Stop loss reasonable | <= 0.05 |

Kill switch adjustment:
- Level 0: Full go
- Level 1: Size × 0.75
- Level 2: Size × 0.40, only PHOENIX
- Level 3+: Reject

- **Output:** RiskVerdict
- **Latency budget:** < 50ms

### Step 8: Execution (Layer 5)

| Urgency | When | Order Type | Timeout |
|---------|------|-----------|---------|
| EMERGENCY | Kill switch | Market | Immediate |
| HIGH | Confidence > 0.8 | Aggressive limit | 30s → market |
| NORMAL | Standard | Limit at mid | 60s → cancel |
| LOW | Carry trade | Passive limit | 5min → cancel |

**MANDATORY:** Place exchange-side SL immediately on fill. SL MUST be confirmed before proceeding. If SL placement fails → close position immediately.

- **Output:** ExecutionResult
- **Latency budget:** < 5s total

### Step 9: Telemetry + Audit (Layer 6)
- Log all events from Steps 1-8
- All events include: timestamp, run_id, inputs_hash (SHA256 of snapshot)

### Step 10: Post-Trade Evaluation (Layer 6, async)
- Update PortfolioState, RSL level, consecutive loss counter
- Attribution: which engine/strategy generated this P&L
- Feature drift check, decay check
- Daily close → generate daily_report event

**Total Pipeline Latency:** < 10 seconds from candle close to order placed.

---

## 7. Regime State Machine (32D)

### 7.1 States

| State | Lead Engine | Entry Criteria | Behavior |
|-------|------------|----------------|----------|
| **TRENDING** | TITAN | ADX>25, price aligned with MA(50) 20+ bars | Full directional trading |
| **RANGING** | NAUTILUS | ADX<20, Hurst<0.45, BB(20,2) 20+ bars | Mean-reversion only |
| **VOLATILE** | PHOENIX | ATR(5)/ATR(20)>1.8 OR vol>2x 60d median | Carry/basis only, reduced size |
| **CRISIS** | None | Drop>8%/24h OR vol>3x 60d OR liquidation cascade | Close all, no new trades |

### 7.2 Transition Rules

| From → To | Trigger | Confirmation | Min Candles in Current |
|-----------|---------|-------------|----------------------|
| TRENDING → RANGING | ADX < 20 AND Hurst < 0.45 | 3 candles | 6 |
| TRENDING → VOLATILE | ATR ratio > 1.8 | 2 candles | 0 (safety) |
| TRENDING → CRISIS | Crisis trigger | IMMEDIATE | 0 (emergency) |
| RANGING → TRENDING | ADX > 25 AND directional alignment | 3 candles | 6 |
| RANGING → VOLATILE | ATR ratio > 1.8 | 2 candles | 0 (safety) |
| RANGING → CRISIS | Crisis trigger | IMMEDIATE | 0 (emergency) |
| VOLATILE → TRENDING | ADX > 25 AND ATR ratio < 1.5 | 5 candles | 4 |
| VOLATILE → RANGING | ADX < 20 AND ATR ratio < 1.5 AND Hurst < 0.45 | 5 candles | 4 |
| VOLATILE → CRISIS | Crisis trigger | IMMEDIATE | 0 (emergency) |
| CRISIS → VOLATILE | Crisis eased, vol still elevated | 12 candles | 0 |
| CRISIS → TRENDING | **NOT ALLOWED** — must pass through VOLATILE | — | — |
| CRISIS → RANGING | **NOT ALLOWED** — must pass through VOLATILE | — | — |

### 7.3 Crisis Detection (Instant, No Delay)

Any ONE of these triggers CRISIS immediately:
1. Price drop > 8% in 24h
2. Realized vol > 3x 60-day median
3. Liquidation estimate > 99th percentile
4. Orderbook depth < 30% of normal

### 7.4 Recovery from CRISIS (Gradual)

```
Phase 1 (CRISIS):
  - All positions closed. No new trades. Monitor only.
  - Minimum 12h (12 candles on 1h)

Phase 2 (VOLATILE, post-crisis):
  - PHOENIX only. Position sizes at 25% of normal.
  - ATLAS multiplier capped at 0.5.
  - Minimum 4h. If crisis re-triggers → back to Phase 1.

Phase 3 (Normal):
  - Full engine routing.
  - Gradual size increase: candles 1-4 = 50%, 5-12 = 75%, 13+ = 100%
```

### 7.5 Confirmation Window Mechanics

```python
on each candle:
    if transition_condition_met:
        if pending_transition is None:
            pending_transition = target_regime
            confirmation_counter = 1
        elif pending_transition == target_regime:
            confirmation_counter += 1
            if confirmation_counter >= required_confirmations:
                execute_transition()
        else:
            pending_transition = target_regime
            confirmation_counter = 1
    else:
        pending_transition = None
        confirmation_counter = 0
```

---

## 8. Kill Switch FSM (32E)

### 8.1 Five Levels

```
LEVEL 0: NORMAL
  ├── All systems go
  ├── Full position sizing
  └── All engines active

LEVEL 1: CAUTION
  ├── Trigger: DD > 2% OR daily loss > 1%
  ├── Position sizes → 75%
  ├── Max leverage → 1.5x
  ├── Alert: Telegram (INFO)
  └── Recovery: DD < 1.5% for 24h → NORMAL

LEVEL 2: DEFENSIVE
  ├── Trigger: DD > 4% OR daily loss > 1.5% OR 3 consecutive losses
  ├── Position sizes → 40%
  ├── No new positions (except PHOENIX carry)
  ├── Max leverage → 1.0x
  ├── Alert: Telegram (URGENT)
  └── Recovery: DD < 3% for 48h AND no loss streak → CAUTION

LEVEL 3: HALT
  ├── Trigger: DD > 6% OR daily loss > 2.5% OR CRISIS + positions
  ├── ALL positions closed at market
  ├── System halted 24h MINIMUM
  ├── Owner must manually restart
  ├── Alert: ALL channels (CRITICAL)
  └── Recovery: Manual restart + post-mortem required → DEFENSIVE

LEVEL 4: LOCKDOWN
  ├── Trigger: DD > 10% (should NEVER reach this)
  ├── System halted INDEFINITELY
  ├── No automated restart possible
  ├── Full strategy audit required
  ├── Alert: ALL channels (EMERGENCY)
  └── Recovery: Full audit + manual restart → HALT
```

### 8.2 Transition Rules

| From | To | Trigger | Auto? |
|------|----|---------|-------|
| NORMAL → CAUTION | DD > 2% OR daily_loss > 1% | Yes |
| CAUTION → DEFENSIVE | DD > 4% OR daily_loss > 1.5% OR consec_losses >= 3 | Yes |
| DEFENSIVE → HALT | DD > 6% OR daily_loss > 2.5% | Yes |
| HALT → LOCKDOWN | DD > 10% | Yes |
| CAUTION → NORMAL | DD < 1.5% for 24h continuous | Yes |
| DEFENSIVE → CAUTION | DD < 3% for 48h AND consec_losses < 2 | Yes |
| HALT → DEFENSIVE | Manual restart + post-mortem documented | Manual |
| LOCKDOWN → HALT | Full audit documented + manual restart | Manual |

### 8.3 Key Invariants

1. **Escalation is automatic and immediate.** No delay, no confirmation.
2. **De-escalation requires sustained improvement.** Time gates prevent premature return.
3. **Level 3+ requires human intervention.** The system cannot restart itself.
4. **Kill switch can ONLY reduce risk, never increase it.**
5. **Kill switch state persists across restarts.** Stored in SQLite, not memory.

### 8.4 State Machine Implementation

```python
class KillSwitchLevel(IntEnum):
    NORMAL = 0
    CAUTION = 1
    DEFENSIVE = 2
    HALT = 3
    LOCKDOWN = 4

@dataclass
class KillSwitchState:
    level: KillSwitchLevel
    entered_at: datetime
    reason: str
    dd_at_entry: float
    last_escalation: datetime
    last_de_escalation: Optional[datetime]

ESCALATION_RULES = {
    (0, 1): {"dd_threshold": 0.02, "daily_loss_threshold": 0.01},
    (1, 2): {"dd_threshold": 0.04, "daily_loss_threshold": 0.015, "consec_losses": 3},
    (2, 3): {"dd_threshold": 0.06, "daily_loss_threshold": 0.025},
    (3, 4): {"dd_threshold": 0.10},
}

DE_ESCALATION_RULES = {
    (1, 0): {"dd_below": 0.015, "sustained_hours": 24},
    (2, 1): {"dd_below": 0.03, "sustained_hours": 48, "max_consec_losses": 1},
    (3, 2): {"manual": True, "requires_postmortem": True},
    (4, 3): {"manual": True, "requires_audit": True},
}
```

### 8.5 Removal Criteria

The kill switch is NEVER removed. It is a permanent, non-negotiable safety system.

---

## 9. Telemetry Schemas (32F)

### 9.1 Event Types

All events inherit from a base schema:

```python
class TelemetryEvent(ArgusModel):
    event_type: str
    timestamp: datetime
    run_id: str
    inputs_hash: Optional[str] = None  # SHA256 of snapshot that triggered this
```

### 9.2 Event Catalog

| Event Type | Trigger | Required Fields | Storage |
|------------|---------|----------------|---------|
| `candle_close` | New candle | symbol, timeframe, ohlcv | Parquet |
| `sentinel_check` | Every pipeline cycle | score, checks_passed, checks_failed, details | SQLite |
| `features_ready` | Feature computation done | symbol, feature_count, compute_ms, nan_count | SQLite |
| `regime_snapshot` | Every candle | regime, confidence, stability, direction, pending | SQLite |
| `regime_changed` | Regime transition | from_regime, to_regime, confirmation_candles, trigger | SQLite |
| `signal_generated` | Engine produces signal | engine, sub_strategy, bias, confidence, stop, expected_return | SQLite |
| `signal_rejected` | Engine gate fails | engine, reason, features_snapshot | SQLite |
| `decision_made` | MDE output | action, position_size, engine, reason, gate_results | SQLite |
| `risk_check` | RSL verdict | approved, reason, risk_level, adjusted_size | SQLite |
| `order_submitted` | Order to exchange | order_type, side, size, price, urgency | SQLite |
| `order_filled` | Fill confirmed | order_id, fill_price, fill_qty, slippage, fees | SQLite |
| `order_rejected` | Exchange rejects | order_id, reason, exchange_error | SQLite |
| `sl_placed` | SL confirmed | order_id, sl_price, sl_order_id | SQLite |
| `sl_failed` | SL placement fails | reason, emergency_action_taken | SQLite |
| `position_opened` | New position | symbol, side, size, entry_price, sl_price | SQLite |
| `position_closed` | Position closed | symbol, side, pnl, pnl_pct, reason_exit, duration | SQLite |
| `kill_switch_change` | RSL level change | from_level, to_level, trigger, dd_current | SQLite |
| `heartbeat` | Every 60s | uptime_s, memory_mb, cpu_pct, positions_count, dd | SQLite |
| `alert` | Any alert condition | severity, message, channel | SQLite + Telegram |
| `daily_report` | 00:00 UTC daily | pnl, trades, regime_distribution, risk_level | SQLite + Telegram |
| `error` | Any exception | error_type, message, traceback, component | SQLite |

### 9.3 Retention Policy

| Storage | Retention | Purpose |
|---------|-----------|---------|
| Parquet (OHLCV) | Indefinite | Backtesting |
| SQLite (decisions, trades) | Indefinite | Audit trail |
| SQLite (heartbeats) | 90 days | Ops monitoring |
| SQLite (features) | 180 days | Feature drift analysis |

### 9.4 Rejection Logging

Every rejected signal or decision MUST be logged with:
- Timestamp
- Gate that rejected
- Full feature snapshot at rejection time
- Reason string
- What would have happened (theoretical P&L tracked for 24h post-rejection)

This enables "what-if" analysis: "How much money did our risk gates save us (or cost us)?"

---

## 10. Config Contracts (32G)

All configuration is YAML-based. No magic numbers in code — every tunable parameter lives in config.

### 10.1 `config/base.yaml`

```yaml
system:
  name: "argus"
  version: "2.0.0"
  mode: "paper"                     # paper | live | backtest
  log_level: "INFO"

symbols:
  - "BTCUSDT"
  - "ETHUSDT"

timeframes:
  primary: "1h"
  confirmation: "4h"
  direction: "1d"

exchanges:
  primary: "binance"
  secondary: "bybit"
```

### 10.2 `config/regimes.yaml`

```yaml
regime:
  states: ["TRENDING", "RANGING", "VOLATILE", "CRISIS"]
  default: "RANGING"                # Conservative default

  thresholds:
    trending:
      adx_min: 25
      alignment_candles: 20
    ranging:
      adx_max: 20
      hurst_max: 0.45
      bb_period: 20
    volatile:
      atr_ratio_min: 1.8
      vol_multiple: 2.0            # vs 60d median
    crisis:
      price_drop_24h: -0.08
      vol_multiple: 3.0
      depth_collapse: 0.30

  confirmation:
    trending_to_ranging: 3         # candles
    ranging_to_trending: 3
    to_volatile: 2
    to_crisis: 0                   # instant
    crisis_to_volatile: 12

  hysteresis:
    min_candles_before_transition: 6
    crisis_exempt: true
    volatile_to_normal_min: 4
```

### 10.3 `config/engines.yaml`

```yaml
engines:
  titan:
    active_regimes: ["TRENDING"]
    min_adx: 25
    min_confidence: 0.55
    max_concurrent: 2

    trend_follow:
      ema_fast: 21
      ema_slow: 55
      atr_trail_mult: 2.5
      min_volume_ratio: 1.0

    breakout:
      donchian_period: 20
      volume_spike: 1.5
      atr_filter: 0.005
      confirmation_candles: 2

  nautilus:
    active_regimes: ["RANGING"]
    max_adx: 22
    min_confidence: 0.55

    bb_reversion:
      period: 20
      std: 2.0
      entry_threshold: 0.05
      rsi_oversold: 30
      rsi_overbought: 70
      stop_mult: 1.0
      target: "mid"

    funding_reversion:
      extreme_pctile: 90
      extreme_neg_pctile: 10
      hold_periods: 8
      stop_pct: 0.03

  phoenix:
    active_regimes: ["TRENDING", "RANGING", "VOLATILE"]
    min_confidence: 0.60

    funding_harvest:
      entry_pctile: 95
      confirmation_periods: 2
      exit_pctile: 60
      stop_pct: 0.025

    basis_trade:
      entry_basis_pct: 0.003
      exit_basis_pct: 0.001
      stop_pct: 0.005
      max_duration_hours: 72

  atlas:
    risk_on_mult: [1.0, 1.5]
    risk_neutral_mult: [0.7, 1.0]
    risk_off_mult: [0.2, 0.5]
    crisis_mult: 0.0
```

### 10.4 `config/risk.yaml`

```yaml
risk:
  sizing:
    base_risk_pct: 0.02
    min_risk_pct: 0.005
    max_risk_pct: 0.03
    max_position_size: 0.15
    max_leverage: 2.0

  stop_loss:
    min_stop: 0.01
    max_stop: 0.05
    multipliers:
      titan_trend_follow: 2.5
      titan_breakout: 2.0
      nautilus_bb_reversion: 1.0
      nautilus_funding: 3.0
      phoenix_funding: 2.5
      phoenix_basis: 3.0

  drawdown:
    dd_caution: 0.02
    dd_defensive: 0.04
    dd_halt: 0.06
    dd_lockdown: 0.10
    dd_multipliers:
      below_2pct: 1.0
      below_4pct: 0.5
      below_6pct: 0.25
      above_6pct: 0.0

  daily_limits:
    soft_cap: -0.015
    hard_cap: -0.025
    max_trades: 15

  kill_switch:
    levels: [0, 1, 2, 3, 4]
    size_multipliers: [1.0, 0.75, 0.40, 0.0, 0.0]
    de_escalation_hours:
      caution_to_normal: 24
      defensive_to_caution: 48

  guards:
    correlation_max: 0.6
    funding_settlement_blackout_min: 15
    weekend_size_mult: 0.5
    consecutive_loss_cooldown: 3
    equity_curve_ma_period: 20
    single_trade_max_loss: 0.03
```

### 10.5 `config/telemetry.yaml`

```yaml
telemetry:
  sqlite_path: "data/trade_logs/argus.db"
  heartbeat_interval_s: 60

  alerts:
    telegram:
      enabled: true
      levels: ["URGENT", "CRITICAL", "EMERGENCY"]
    log:
      enabled: true
      levels: ["INFO", "URGENT", "CRITICAL", "EMERGENCY"]

  retention:
    heartbeat_days: 90
    features_days: 180
    decisions: "indefinite"
    trades: "indefinite"
```

### 10.6 Config Versioning

Every configuration change is tracked:
- Config files are hashed (SHA256) at startup
- Hash stored with every trade record
- Config changes require restart (no hot-reload for safety)
- Previous configs archived in `data/config_history/`

---

## 11. Test Matrix (32H)

### 11.1 Unit Tests (Per Module)

| Module | Test File | Key Test Cases | Min Coverage |
|--------|-----------|---------------|-------------|
| `core/types.py` | `test_types.py` | Frozen immutability, field validation, NaN rejection, edge values | 95% |
| `data/sentinel` | `test_sentinel.py` | All 6 checks individually, score calculation, threshold actions | 95% |
| `data/features` | `test_features.py` | Each of 50 features vs known values (golden test), NaN handling | 90% |
| `regime/rule_based` | `test_regime.py` | Each regime classification, boundary values, ambiguous cases | 95% |
| `regime/state_machine` | `test_state_machine.py` | All valid transitions, blocked transitions, confirmation windows, hysteresis | 98% |
| `engines/titan` | `test_titan.py` | Signal generation in TRENDING, silence in other regimes, sub-strategy selection | 90% |
| `engines/nautilus` | `test_nautilus.py` | Signal generation in RANGING, BB reversion, funding reversion | 90% |
| `engines/phoenix` | `test_phoenix.py` | Signal in all non-CRISIS regimes, funding harvest, basis trade | 90% |
| `engines/atlas` | `test_atlas.py` | Risk multiplier ranges, RISK_ON/OFF/CRISIS outputs | 90% |
| `mde/gates` | `test_mde.py` | All 7 gates individually, gate ordering, sizing math | 95% |
| `mde/sizing` | `test_sizing.py` | Fixed fractional formula, clamp bounds, edge cases | 98% |
| `risk/rsl` | `test_rsl.py` | All 5 levels, escalation triggers, de-escalation conditions | 98% |
| `risk/kill_switch` | `test_kill_switch.py` | All transitions, persistence across restart, manual override | 98% |
| `risk/pre_trade` | `test_pre_trade.py` | All 8 checks, pass/fail combinations | 95% |
| `execution/sl_manager` | `test_sl_manager.py` | SL placement, SL failure → close position | 95% |

### 11.2 Integration Tests

| Test | Scope | Description | Pass Criteria |
|------|-------|-------------|--------------|
| `test_pipeline.py` | Full pipeline | Mock data → Decision | All 10 steps execute, latency < 10s |
| `test_execution.py` | Execution | Mock exchange, order lifecycle | Order placed, SL confirmed, reconciled |
| `test_telemetry.py` | Telemetry | Pipeline run → event verification | All expected events logged with correct schema |
| `test_regime_engine.py` | Regime → Engine | Regime change → correct engine activates | TRENDING → TITAN fires, RANGING → NAUTILUS fires |
| `test_risk_pipeline.py` | MDE → RSL | Decision → risk check → adjusted/approved | Kill switch correctly modifies sizing |

### 11.3 Stress Tests

| Test | Scenario | Pass Criteria |
|------|----------|--------------|
| `test_crash_scenario.py` | 15% drop in 6h | CRISIS detected, all positions closed, system halts |
| `test_regime_flapping.py` | ADX oscillates around 25 for 48h | No more than 2 regime transitions in 48h |
| `test_data_outage.py` | Binance WS dies for 5min | Sentinel score drops, system halts new trades, recovers |
| `test_consecutive_losses.py` | 5 losses in a row | Kill switch escalates correctly through levels |
| `test_max_drawdown.py` | DD reaches 6% | HALT level triggered, all positions closed |
| `test_nan_propagation.py` | NaN injected in features | NaN never reaches engine or MDE layer |
| `test_sl_failure.py` | Exchange rejects SL order | Position immediately closed, alert sent |

### 11.4 Backtest Validation

| Test | Description | Pass Criteria |
|------|-------------|--------------|
| Walk-forward (5-fold) | Time-series split, train/test on each fold | OOS Sharpe > 0 on >= 4 of 5 folds |
| Monte Carlo (1000 permutations) | Shuffle trade order | 95th percentile MaxDD < 2x mean MaxDD |
| Regime stress | Per-regime performance | No regime shows MaxDD > 10% |
| Cost sensitivity | Vary costs from 0.5x to 3x estimated | System stays profitable at 2x costs |
| Synthetic CRISIS | Inject 2020-style crash into 2024 data | System enters CRISIS, preserves >90% capital |

---

## 12. Implementation Phases (32I)

### Phase 1: Foundation (Month 1-2, ~120h)

| Sprint | Deliverable | Hours | Gate |
|--------|------------|-------|------|
| 1.1 | Project scaffold, config system, core types | 10 | `pytest tests/unit/test_types.py` passes |
| 1.2 | Binance WS connector + REST fallback | 16 | Live data streaming, auto-reconnect |
| 1.3 | Funding + OI + cross-validation ingest | 8 | All data sources polled correctly |
| 1.4 | Parquet store + SQLite store | 6 | Read/write verified |
| 1.5 | 37 Tier 1+2 features | 20 | Golden tests pass vs known values |
| 1.6 | Sentinel (6 checks) | 8 | Score correctly computed |
| 1.7 | Regime Detector (rule-based) | 12 | >70% accuracy on 2y BTC labeled data |
| 1.8 | Regime state machine | 8 | All transitions tested |
| 1.9 | RSL v2.0 (5 levels) + pre-trade checks | 12 | Stress tests pass |
| 1.10 | Backtest engine + walk-forward | 20 | Can replay historical data |

**Phase 1 Gate:** System can stream data, compute features, detect regime, manage risk, run backtests. Cannot trade yet.

### Phase 2: First Engine — TITAN (Month 3-4, ~100h)

| Sprint | Deliverable | Hours | Gate |
|--------|------------|-------|------|
| 2.1 | TITAN: trend follow sub-strategy | 15 | Signals correct on historical data |
| 2.2 | TITAN: breakout sub-strategy | 15 | Signals correct on historical data |
| 2.3 | MDE v2.0 (single-engine routing) | 10 | Routes to TITAN in TRENDING |
| 2.4 | Execution engine + SL manager | 15 | Paper trades execute correctly |
| 2.5 | TITAN backtesting (walk-forward, Monte Carlo) | 20 | Passes validation suite |
| 2.6 | TITAN paper trading (30 days minimum) | 25 | Paper Sharpe > 0.8, DD < 5% |

**Phase 2 Gate:** One engine live in paper trading, profitable, validated.

### Phase 3: Second Engine — NAUTILUS (Month 5-6, ~80h)

| Sprint | Deliverable | Hours | Gate |
|--------|------------|-------|------|
| 3.1 | NAUTILUS: BB reversion | 12 | Signals correct in RANGING |
| 3.2 | NAUTILUS: funding rate reversion | 12 | Signals correct when funding extreme |
| 3.3 | MDE dual-engine routing | 8 | Correct engine per regime |
| 3.4 | NAUTILUS backtesting | 18 | Passes validation suite |
| 3.5 | Dual-engine paper trading (30 days) | 15 | Combined Sharpe > 1.0 |
| 3.6 | Telegram bot + basic alerts | 15 | Remote monitoring works |

**Phase 3 Gate:** Two engines, regime-gated, paper-traded, remotely monitored.

### Phase 4: ML + Third Engine — PHOENIX (Month 7-9, ~120h)

| Sprint | Deliverable | Hours | Gate |
|--------|------------|-------|------|
| 4.1 | LightGBM direction model + triple-barrier labels | 30 | OOS accuracy > 55% |
| 4.2 | Chronos-Bolt integration | 25 | MAPE < 5% on 1h forecasts |
| 4.3 | PHOENIX: funding harvest + basis trade | 20 | Profitable in backtest |
| 4.4 | ATLAS overlay | 15 | Risk adjustment working |
| 4.5 | Full system paper trade (30 days) | 30 | System Sharpe > 1.0, DD < 4% |

**Phase 4 Gate:** Full system (3 engines, 2 overlays, ML) paper-trade ready.

### Phase 5: Live Deployment (Month 10-12, ~80h)

| Sprint | Deliverable | Hours | Gate |
|--------|------------|-------|------|
| 5.1 | Micro-live: $10-$20 real capital | 20 | No bugs, execution quality OK |
| 5.2 | Gradual scale: $20 → $50 → $100 | 20 | Live Sharpe > 0.6, DD < 5% |
| 5.3 | LEL v2.0: performance tracking, decay detection | 20 | Self-monitoring works |
| 5.4 | Hardening: edge cases, documentation | 20 | Production-ready |

**Phase 5 Gate:** Live trading with real capital, proven track record, production-grade monitoring.

### Total Timeline

| Phase | Duration | Hours | Milestone |
|-------|----------|-------|-----------|
| Foundation | Month 1-2 | 120h | Infrastructure + Regime + Risk |
| TITAN | Month 3-4 | 100h | First profitable engine |
| NAUTILUS | Month 5-6 | 80h | Two-engine system |
| ML + PHOENIX | Month 7-9 | 120h | Full ML-enhanced system |
| Live | Month 10-12 | 80h | Real money trading |
| **TOTAL** | **12 months** | **500h** | **Production-grade system** |

**Pace:** ~10 hours/week. Sustainable. No burnout. No shortcuts.

---

## 13. Mathematical Foundations

### 13.1 Position Sizing (Fixed Fractional)

```
position_size = risk_per_trade / stop_distance

risk_per_trade = base_risk × atlas_mult × sentinel × regime_conf × dd_mult × rsl_mult

  base_risk     = 0.02 (2% of equity)
  atlas_mult    = [0.0, 1.5]
  sentinel      = [0.0, 1.0]
  regime_conf   = [0.0, 1.0]
  dd_mult       = {DD<2%: 1.0, DD<4%: 0.5, DD<6%: 0.25, DD>6%: 0.0}
  rsl_mult      = {L0: 1.0, L1: 0.5, L2+: 0.0 for new trades}

  risk_per_trade ∈ [0.005, 0.03]  (clamped)
  position_size  ∈ [0.0, 0.15]   (clamped)
  stop_distance  ∈ [0.01, 0.05]  (clamped)
```

**Why NOT Kelly:** Kelly requires accurate win_rate and avg_win/avg_loss estimates. With < 500 trades, estimation error is ±5-8%. Half-Kelly on garbage inputs is still garbage. Transition to Kelly ONLY after 500+ trades with SE < 3%.

### 13.2 Stop Loss Multipliers

| Engine / Strategy | ATR Multiplier | Rationale |
|-------------------|---------------|-----------|
| TITAN trend_follow | 2.5 | Trending → wider stops to avoid noise |
| TITAN breakout | 2.0 | Breakout → tighter, momentum should carry |
| NAUTILUS bb_reversion | 1.0 | Mean-rev → tight stops, wrong if range breaks |
| NAUTILUS funding | 3.0 | Funding → wide, carry trades need room |
| PHOENIX funding | 2.5 | Carry → wide |
| PHOENIX basis | 3.0 | Basis → widest, convergence takes time |

```
stop_distance = max(ATR(14) × multiplier, 0.01)
stop_distance = min(stop_distance, 0.05)
```

### 13.3 Regime Thresholds (Justified)

| Threshold | Value | Justification |
|-----------|-------|---------------|
| ADX trending | 25 | Wilder's standard. BTC 2020-2025: ADX>25 captures 85%+ of major moves. |
| ADX ranging | 20 | Below 20, mean-reversion outperforms trend-following 2:1 in BTC backtests. |
| ATR ratio volatile | 1.8 | >95th percentile of ATR(5)/ATR(20) distribution in BTC. |
| Hurst ranging | 0.45 | H=0.5 is random walk. H<0.5 is mean-reverting. 0.45 gives buffer. |
| Crisis: -8%/24h | 8% | BTC drops >8%/24h ~10-15 times/year. Captures crashes without false alarms. |
| Confirmation candles | 3 | Balances speed vs accuracy. 3h delay acceptable for 1h TF. |
| Funding extreme | 95th %ile | 5% of time. These are extreme crowding events with highest mean-rev edge. |

### 13.4 Risk Thresholds (Justified)

| Threshold | Value | Justification |
|-----------|-------|---------------|
| Daily soft cap | -1.5% | Conservative. -2% is institutional standard; tighter at low AUM. |
| Daily hard cap | -2.5% | Emergency. Something is wrong or market is extreme. |
| DD kill switch | -6% | -6% requires +6.4% to recover. -10% requires +11.1%. Keep recovery manageable. |
| Max position | 15% | 2 pairs max 30% exposure. Even with 2x stop failure, max loss = 1.5% portfolio. |
| Max leverage | 2.0 | With 6% DD kill and 2x leverage, 3% adverse move = 6% loss = kill switch. Maximum safe leverage. |
| Cooldown losses | 3 | 3 × 2% risk = -6% → exactly at kill switch. Cooldown prevents reaching it. |
| Equity MA | 20d | 1-month MA. Below it = drawdown phase. Reducing size here prevents deeper DD. |

### 13.5 Transaction Cost Model

```
estimated_round_trip = base_fee + spread + slippage
  base_fee  = 0.0008  (0.08% maker+taker)
  spread    = 0.0003  (0.03% typical)
  slippage  = 0.0002  (0.02% estimated)
  TOTAL     ≈ 0.0013  (0.13%)

Rule: No signal with net_expected_return < 0.001 (0.1%) passes Gate 5.
This ensures every trade has positive expected value after costs.
```

---

## 14. Removal & Deprecation Criteria

Every component in this system has explicit criteria for when it should be removed.

### 14.1 Engine Removal

An engine should be removed if:
1. Rolling 90-day OOS Sharpe < 0 for 3 consecutive months, AND
2. Root cause is identified (not just bad luck), AND
3. No parameter adjustment resolves the issue (tested in backtest)

An engine should NOT be removed if:
- It underperforms in the current regime but the regime just changed
- It has < 100 trades (insufficient sample)

### 14.2 Feature Removal

A feature should be removed from FeatureVector if:
1. Rolling 6-month IC < 0.02, AND
2. No engine uses it as a primary signal input

Feature court is held monthly. Features below IC threshold are flagged. Two consecutive monthly flags → removed.

### 14.3 Overlay Removal

- **ATLAS:** Remove only if macro indicators show zero predictive power over 6+ months (IC of risk_multiplier vs future drawdown < 0.01)
- **SENTINEL:** Never remove. Data quality monitoring is permanent.

### 14.4 ML Model Removal

An ML model should be disabled if:
1. Rolling 30-day accuracy < 52% (barely above random), OR
2. Model has not been retrained in > 90 days, OR
3. Feature distribution has shifted > 2 standard deviations from training distribution

Disabled models fall back to rules-only operation.

### 14.5 Evolution Rules

```
- No parameter change without 90d OOS evidence
- No new feature without IC > 0.02 for 6+ months OOS
- No new engine without 6 months of paper trading
- No removal without 3+ months of underperformance AND identified root cause
- All changes paper-traded for 30d before live deployment
- DEFAULT BEHAVIOR: CHANGE NOTHING. Burden of proof on the proposed change.
```

---

## 15. Priority Hierarchy

This section exists to resolve any ambiguity in the Constitution.

### 15.1 Decision Priority

```
1. Capital Safety      — Never risk ruin. Survive first.
2. Robustness          — Work across regimes. No single point of failure.
3. Scale               — Handle growing capital without breaking.
4. Profit              — Make money. This is last, not first.
```

### 15.2 Document Priority

```
1. This Constitution (CONSTITUTION_V2.md)
2. Config YAML files (specific parameters)
3. Code comments (implementation notes)
4. FUTURE_VISION.md (historical reference only)
```

### 15.3 Architecture Principles

1. **Fewer components, deeper execution.** 3 deep engines > 5 shallow ones.
2. **Regime routes, not votes.** One engine leads per regime (crypto mode).
3. **Risk can only reduce, never amplify.** No component can override kill switch.
4. **Every decision is logged.** No exceptions. No shortcuts.
5. **NaN never propagates.** Caught at Layer 0 or pipeline halts.
6. **Exchange-side SL is mandatory.** No position exists without an exchange SL.
7. **Data flows downward.** No layer calls upward.
8. **Default is conservative.** Ambiguous regime defaults to RANGING (smaller positions).
9. **Build less. Validate more. Trade small. Survive first.**

---

## Document History

| Version | Date | Change |
|---------|------|--------|
| v2.0 | 2026-02-10 | Initial Constitution, consolidating FUTURE_VISION.md Sections 27-32 + new 32E-32I |

---

**END OF CONSTITUTION**
