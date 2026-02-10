# ARGUS v2.0 — MEGA IMPLEMENTATION PROMPT

You are building ARGUS v2.0, a **multi-asset, multi-regime algorithmic hedge fund system**. This is NOT just a crypto bot — it is a modular hedge fund engine that trades crypto (via BingX/Binance), NASDAQ/SP500 stocks as CFD futures (via BingX), commodities like gold/silver (via BingX), and provides analysis-only advisory for assets without API execution (e.g. BIST stocks via traditional brokerages).

This prompt contains EVERYTHING you need. Do not read any other file unless explicitly told to.

**Working directory:** The repo root is `argus-terminal/`. There is an existing `argus_py/` directory with v1.0 code. **DO NOT MODIFY `argus_py/`.** Build all v2.0 code in a new `src/` directory. The `src/` directory may already partially exist from a prior session — check first, preserve any working code, and continue from where it left off.

**Who codes what:**
- **Opus (you):** Implement Phase 1 (core foundation) directly. Update this mega prompt with the changes below.
- **Codex agents:** Will implement Phases 2-10 based on this prompt. Write this prompt so Codex can work autonomously.

---

## FOUNDER NOTES DELTA (2026-02-10, MUST APPLY)

This section is a hard delta from founder/operator notes. If any later section conflicts, this delta wins.

1. **Hedge fund scope must be preserved for non-crypto assets.**
   - NASDAQ/SP500 stocks and commodities are first-class citizens in architecture.
   - Do not design a crypto-only pipeline that cannot scale to multi-asset.

2. **Execution must support API-unavailable brokers via advisory mode.**
   - If auto execution is not available, pipeline still runs full analysis and emits actionable advisory output.
   - Advisory output must include:
     - direction
     - entry price or entry zone
     - SL/TP (multi-level TP when possible)
     - conditional alerts (e.g. "if price reaches X, consider partial sell")

3. **HERMES is mandatory and critical for crypto.**
   - HERMES is not only entry blocking.
   - HERMES must manage open positions:
     - close position on critical negative news
     - adjust SL/TP on high-impact news
   - HERMES actions must be telemetry-visible and audit-logged.

4. **Chronos + quant factors are part of roadmap, with anti-bloat constraints.**
   - Chronos integration stays in ML layer.
   - Quant/factor logic should be feature-layer or scoring-layer first, not a separate heavyweight engine unless justified by measurable edge.

5. **Backtest Lab must be institutional-grade.**
   - Per-asset backtests + portfolio-level simulations are both required.
   - Portfolio tests must evaluate allocation/budget behavior across assets.
   - Backtest outputs must be ML-ready (quality-controlled datasets, labeling, CV discipline).

6. **BingX multi-asset reality is a design input, not an afterthought.**
   - System must support multi-asset long/short via BingX where available.
   - BIST can remain advisory-only when API is unavailable.
   - Keep architecture modular so execution backends can be swapped without rewriting core logic.

7. **Reference repositories are mandatory learning sources.**
   - Use existing public reference repos to extract proven patterns.
   - If current set is insufficient, add more references and document what was borrowed conceptually.

8. **Implementation ownership split is fixed.**
   - Opus implements only Phase 1 directly and keeps prompt/spec quality high.
   - Codex implements Phases 2-10 incrementally from this prompt.

---

## SYSTEM OVERVIEW

```
Name:           ARGUS v2.0
Type:           Multi-asset algorithmic hedge fund
Language:       Python 3.11+
Stack:          pydantic v2, asyncio, ccxt, pandas/numpy, LightGBM, SQLite, Parquet, YAML
Priority:       Capital Safety > Robustness > Scale > Profit
```

**Architecture in one sentence:** Market data flows through SENTINEL (quality gate) → HERMES (news/sentiment overlay) → 50+ features → 4-state REGIME detector → regime ROUTES to 1 of 4 engines (TITAN/NAUTILUS/PHOENIX/HERMES) → 7 gates filter the signal → fixed-fractional SIZING → 5-level KILL SWITCH approves → EXECUTION (auto or advisory) with mandatory exchange-side stop loss → TELEMETRY logs everything.

**Key decisions:**
- 4 engines: TITAN (trend), NAUTILUS (mean-rev), PHOENIX (carry/basis), HERMES (news/sentiment)
- 2 overlays: ATLAS (risk multiplier), SENTINEL (data quality)
- 4 regimes: TRENDING, RANGING, VOLATILE, CRISIS
- Routing, NOT voting: one engine leads per regime (HERMES can override ANY regime)
- Fixed fractional sizing (2% base risk), NOT Kelly
- 5-level kill switch: NORMAL → CAUTION → DEFENSIVE → HALT → LOCKDOWN
- Exchange-side SL is MANDATORY on every auto-executed position
- ML layer: Amazon Chronos (time-series forecasting) + LightGBM (classification)

---

## CRITICAL ARCHITECTURE PRINCIPLES

### Multi-Asset Modular Design

The system is a **hedge fund**, not a crypto-only bot. Every module MUST be asset-class agnostic at the interface level. Asset-specific logic lives in adapters only.

**Asset classes and execution modes:**

| Asset Class | Exchange | Execution Mode | Long/Short | Examples |
|-------------|----------|---------------|------------|---------|
| Crypto Spot/Futures | BingX, Binance | AUTO (API) | Yes | BTCUSDT, ETHUSDT, SOLUSDT |
| US Stocks (CFD) | BingX | AUTO (API) | Yes (futures) | AAPL, TSLA, NVDA, MSFT, AMZN |
| Commodities (CFD) | BingX | AUTO (API) | Yes (futures) | XAUUSD (gold), XAGUSD (silver) |
| Index CFDs | BingX | AUTO (API) | Yes (futures) | NAS100, SPX500 |
| BIST Stocks | Traditional broker | ADVISORY ONLY | Manual | THYAO, ASELS, SISE |

**Advisory mode** means: the system runs full analysis pipeline (features, regime, engine signal, sizing) but instead of executing, it sends a Telegram alert to the human operator with:
- Signal direction (long/short)
- Suggested entry price / entry zone
- Stop loss price
- Take profit target(s) — multiple levels
- Position size recommendation
- Confidence score and reasoning
- "If price reaches X, consider selling" type conditional alerts

The human operator manually executes on the broker platform.

### BingX as Primary Multi-Asset Exchange

BingX provides NASDAQ, SP500, gold, silver, and major stocks as **perpetual futures (CFDs)** with API access. This means ARGUS can be a real hedge fund covering:
- Crypto perpetual futures
- Stock index CFDs (NAS100, SPX500)
- Individual stock CFDs (AAPL, TSLA, etc.)
- Commodity CFDs (XAUUSD, XAGUSD)

All through a single exchange API. The existing `argus_py/exchange/bingx.py` has a partial BingX adapter — use it as reference but build clean in `src/`.

### Modular Interfaces (CRITICAL)

Every component must use `asset_class: str` field in its data models. The FeatureVector, EngineSignal, Decision, etc. must carry `asset_class` so the pipeline knows which adapter/feature-set/execution-mode to use.

```
asset_class values: "crypto" | "us_equity" | "commodity" | "index" | "bist"
execution_mode values: "auto" | "advisory"
```

---

## HERMES ENGINE — News/Sentiment (NEW)

### Overview

HERMES is a **news-driven sentiment engine** that uses LLM (via Ollama locally or Groq API) to analyze crypto and financial news in real-time. In crypto trading, news is the single most impactful factor — a Binance delisting, SEC action, or hack can move markets 20%+ in minutes.

**HERMES is NOT just an overlay — it is a full engine with veto power AND position management authority.**

### Capabilities

1. **Pre-trade gate:** Can BLOCK new entries if negative news detected
2. **Position management:** Can CLOSE existing positions or ADJUST TP/SL based on breaking news
3. **Signal generation:** Can independently generate trade signals based on sentiment extremes
4. **Crisis detection:** Feeds into regime detector — breaking negative news can trigger CRISIS regime instantly

### Architecture (`src/engines/hermes/`)

```
src/engines/hermes/
├── __init__.py
├── engine.py          # Main HermesEngine class
├── feed_reader.py     # RSS/API news fetcher (crypto + finance)
├── sentiment.py       # LLM-based sentiment scoring
├── position_manager.py # Manages open positions based on news
└── alerts.py          # Advisory alert formatter
```

### Feed Sources
- Crypto: CoinDesk, CoinTelegraph, The Block, Decrypt RSS feeds
- Stocks: Yahoo Finance, Reuters, Bloomberg RSS
- Regulatory: SEC EDGAR filings RSS, CFTC announcements
- Social: Twitter/X API (if available), Reddit sentiment

### Sentiment Scoring
```python
class NewsSentiment(ArgusModel):
    headline: str
    source: str
    asset_class: str
    affected_symbols: list[str]
    sentiment_score: float  # -100 to +100
    confidence: float       # 0.0 to 1.0
    urgency: str           # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    action: str            # "NONE" | "BLOCK_ENTRY" | "CLOSE_POSITION" | "ADJUST_SL" | "ADJUST_TP" | "ALERT_ONLY"
    reasoning: str
    timestamp: datetime
```

### HERMES Decision Authority

| Urgency | Sentiment Score | Action on New Trades | Action on Open Positions |
|---------|----------------|---------------------|------------------------|
| CRITICAL | < -70 | BLOCK ALL | CLOSE immediately |
| HIGH | < -50 | BLOCK affected symbols | TIGHTEN SL to breakeven |
| MEDIUM | < -30 | Reduce confidence by 40% | ALERT operator |
| LOW | < -15 | Reduce confidence by 15% | No action |
| MEDIUM | > +30 | Boost confidence by 10% | WIDEN TP |
| HIGH | > +50 | Generate BUY signal | TRAIL TP higher |

### Position Management (CRITICAL NEW FEATURE)

When HERMES detects significant news about an asset where we hold an open position:

1. **Negative breaking news (urgency=CRITICAL):** IMMEDIATELY close position via market order
2. **Negative news (urgency=HIGH):** Move SL to breakeven or small profit, alert operator
3. **Positive news on existing long:** Consider trailing TP higher, alert operator
4. **Regulatory news:** Always escalate to CRITICAL regardless of score

The `position_manager.py` subscribes to `POSITION_OPENED` events and maintains a watchlist of symbols with open positions. When news arrives for those symbols, it acts.

### Integration with Pipeline

HERMES runs in PARALLEL with the main pipeline (not sequential). It has its own async loop:
1. Fetch news every 60s (configurable)
2. Score each article via LLM
3. If actionable → publish event (HERMES_ALERT, HERMES_BLOCK, HERMES_CLOSE)
4. MDE gates check HERMES status before allowing trades
5. Position manager acts on open positions independently

### LLM Backend

Use Ollama (local, `llama3.1:8b` default) for low-latency scoring. Fallback to Groq API for higher quality when needed. The existing `argus_py/models/hermes/hermes_c.py` has a working Ollama integration — reference it but build clean.

---

## AMAZON CHRONOS INTEGRATION (ML Layer)

### Overview

Amazon Chronos is a pre-trained time-series forecasting model. It provides zero-shot forecasting without training on your specific data. This gives us a strong ML baseline.

**Installation:**
```bash
pip install git+https://github.com/amazon-science/chronos-forecasting.git
```

### Integration (`src/ml/chronos/`)

```python
from chronos import ChronosPipeline

pipeline = ChronosPipeline.from_pretrained("amazon/chronos-bolt-base")
# Feed it OHLCV close prices → get 1h/4h/1d forecasts
```

### Usage in Feature Vector

Chronos outputs are already in the FeatureVector as Optional fields:
- `chronos_forecast_1h`: Median forecast for next 1h candle
- `chronos_confidence_width`: 90th - 10th percentile range (uncertainty)

### Quant Engine Consideration

Beyond Chronos and LightGBM, a pure **quant/factor engine** is NOT added as a separate engine to avoid bloat. Instead, quant factors (momentum, value, quality, volatility) are embedded as features in the FeatureVector. The existing 50 features already include quant-style metrics (hurst_exponent, return_autocorr, entropy, frac_diff_price). If more quant factors are needed later, they go into the feature layer, not as a new engine.

---

## REFERENCE REPOSITORIES

**IMPORTANT:** Do not reinvent the wheel. The following public open-source repositories have been analyzed and specific patterns should be extracted and adapted:

| Repository | GitHub | Use For | Priority |
|-----------|--------|---------|----------|
| **Microsoft Qlib** | microsoft/qlib | Alpha factor pipeline, LightGBM integration, walk-forward validation, DataHandler caching | P0 |
| **Freqtrade** | freqtrade/freqtrade | Indicator library cross-validation, HyperOpt/Optuna param optimization, data format (Parquet), pairlist management | P0 |
| **Jesse** | jesse-ai/jesse | Event-driven architecture patterns, backtest mode loop, walk-forward window management | P1 |
| **Hudson & Thames mlfinlab** | hudson-and-thames/mlfinlab | Fractional differentiation, meta-labeling, purged k-fold CV, structural breaks | P0 |
| **Amazon Chronos** | amazon-science/chronos-forecasting | Zero-shot time-series forecasting integration | P1 |
| **PyPortfolioOpt** | robertmartin8/PyPortfolioOpt | Portfolio-level optimization, risk parity, HRP (hierarchical risk parity) | P1 |
| **Backtrader** | mementum/backtrader | Backtest engine patterns, cerebro architecture | P2 |
| **FinRL** | AI4Finance-LLC/FinRL | Reinforcement learning patterns for future enhancement | P2 |
| **Zipline-reloaded** | zipline-reloaded/zipline-reloaded | Pipeline API, factor model patterns | P2 |
| **Vectorbt** | polakowo/vectorbt | Vectorized backtesting, indicator combinations | P1 |

### Specific Patterns to Extract

**From Qlib:**
- `qlib/contrib/model/gbdt.py` → LightGBM integration pattern for alpha prediction
- `qlib/data/` → 2-level cache (memory + disk) for fast data access
- `qlib/workflow/` → Walk-forward rolling window backtest

**From Freqtrade:**
- `freqtrade/vendor/qtpylib/indicators.py` → Indicator implementations for cross-validation
- `freqtrade/optimize/` → Optuna-based parameter optimization
- `freqtrade/data/converter.py` → Parquet data format (10x speed vs JSON)
- `freqtrade/freqai/` → ML model integration into trading strategy

**From mlfinlab:**
- Fractional differentiation of price series (our `frac_diff_price` feature)
- Meta-labeling for trade filtering
- Purged k-fold cross-validation (prevents lookahead bias)

**From Jesse:**
- `jesse/modes/backtest_mode.py` → Clean backtest loop architecture
- `jesse/services/candle.py` → Candle management patterns

If additional public repos would improve the system, feel free to research and integrate patterns. All referenced repos are public/open-source.

---

## PHASE 1: CORE FOUNDATION

**Start here. Create these files first.**

**NOTE:** Some Phase 1 files may already exist from a prior session. Check `src/core/` first. If files exist and are correct, skip them. If partial, complete them.

### 1A: Directory scaffold

```bash
mkdir -p src/core src/data/ingest src/data/sentinel src/data/features src/data/store
mkdir -p src/regime src/engines/titan src/engines/nautilus src/engines/phoenix src/engines/atlas src/engines/hermes
mkdir -p src/mde src/risk src/execution src/telemetry src/ops src/interface
mkdir -p src/ml/chronos src/ml/training src/backtest src/backtest/lab
mkdir -p src/portfolio
mkdir -p config tests/unit tests/integration tests/stress scripts
mkdir -p data/ohlcv data/models data/backtest_results data/trade_logs data/news_cache
touch src/__init__.py src/core/__init__.py src/data/__init__.py src/data/ingest/__init__.py
touch src/data/sentinel/__init__.py src/data/features/__init__.py src/data/store/__init__.py
touch src/regime/__init__.py src/engines/__init__.py src/engines/titan/__init__.py
touch src/engines/nautilus/__init__.py src/engines/phoenix/__init__.py src/engines/atlas/__init__.py
touch src/engines/hermes/__init__.py
touch src/mde/__init__.py src/risk/__init__.py src/execution/__init__.py
touch src/telemetry/__init__.py src/ops/__init__.py src/interface/__init__.py
touch src/ml/__init__.py src/ml/chronos/__init__.py src/ml/training/__init__.py
touch src/backtest/__init__.py src/backtest/lab/__init__.py src/portfolio/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/stress/__init__.py
```

### 1B: `src/core/types.py` — ALL pydantic v2 models

Implement these EXACTLY. Every model is frozen, strict, extra=forbid. Add a `model_validator` that rejects NaN on any non-Optional float field.

**IMPORTANT:** All models carry `asset_class` where relevant for multi-asset support.

```python
from __future__ import annotations
import math
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from typing import Optional


class ArgusModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    @model_validator(mode="after")
    def _reject_nan(self) -> "ArgusModel":
        for field_name, field_info in self.model_fields.items():
            val = getattr(self, field_name)
            if isinstance(val, float) and math.isnan(val):
                # Allow NaN only for Optional fields that default to None
                if field_info.default is not None:
                    raise ValueError(f"NaN not allowed for field '{field_name}'")
        return self


class FeatureVector(ArgusModel):
    timestamp: datetime
    symbol: str
    asset_class: str  # "crypto" | "us_equity" | "commodity" | "index" | "bist"
    # Volatility (6)
    atr_14: float
    atr_14_pct: float
    atr_ratio_5_20: float
    realized_vol_20d: float
    parkinson_vol: float
    bb_width: float
    # Trend (6)
    adx_14: float
    price_vs_ma200: float
    ema_21_vs_55: float
    lr_slope_20: float
    supertrend_dir: int  # +1 / -1
    aroon_osc: float
    # Momentum (5)
    rsi_14: float
    bb_pct_b: float
    roc_10: float
    willr_14: float
    cci_20: float
    # Volume (5)
    volume_ratio: float
    obv_slope_10: float
    vwap_dev_pct: float
    cmf_20: float
    volume_delta: float
    # Microstructure (5) — Some may be None for non-crypto assets
    spread_pct: float
    orderbook_imbalance: Optional[float] = None
    trade_flow_imbalance: Optional[float] = None
    depth_ratio: Optional[float] = None
    large_trade_ratio: Optional[float] = None
    # Crypto-Native (7) — ALL Optional, None for non-crypto
    funding_rate: Optional[float] = None
    funding_pctile_30d: Optional[float] = None
    oi_change_4h_pct: Optional[float] = None
    oi_change_24h_pct: Optional[float] = None
    liquidation_est: Optional[float] = None
    long_short_ratio: Optional[float] = None
    basis_pct: Optional[float] = None
    # Cross-Asset (4)
    btc_dominance_delta_24h: Optional[float] = None
    btc_eth_corr_30d: Optional[float] = None
    total_mcap_momentum: Optional[float] = None
    stablecoin_flow: Optional[float] = None
    # Statistical (4)
    return_autocorr_20: float
    hurst_exponent: float
    entropy_50: float
    frac_diff_price: float
    # Sentiment (NEW — from HERMES)
    hermes_sentiment_score: Optional[float] = None   # -100 to +100
    hermes_sentiment_confidence: Optional[float] = None
    hermes_urgency: Optional[str] = None  # "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
    # ML Output (8) — None if not active
    chronos_forecast_1h: Optional[float] = None
    chronos_confidence_width: Optional[float] = None
    lgbm_direction: Optional[int] = None
    lgbm_confidence: Optional[float] = None
    meta_label_score: Optional[float] = None
    regime_prob_trending: Optional[float] = None
    regime_prob_ranging: Optional[float] = None
    regime_prob_volatile: Optional[float] = None


class RegimeState(ArgusModel):
    regime: str  # "TRENDING" | "RANGING" | "VOLATILE" | "CRISIS"
    confidence: float = Field(ge=0.0, le=1.0)
    stability: float = Field(ge=0.0, le=1.0)
    direction: Optional[int] = None  # +1 / -1 / None
    pending_transition: Optional[str] = None
    candles_in_regime: int = Field(ge=0)
    rule_regime: str
    ml_regime: str
    hermes_override: Optional[str] = None  # If HERMES forced regime change
    timestamp: datetime


class EngineSignal(ArgusModel):
    engine: str  # "TITAN" | "NAUTILUS" | "PHOENIX" | "HERMES"
    sub_strategy: str
    asset_class: str
    symbol: str
    bias: str  # "long" | "short"
    confidence: float = Field(ge=0.0, le=1.0)
    stop_distance: float = Field(gt=0.0, le=0.10)  # Wider for stocks
    expected_return: float
    atr: float


class Decision(ArgusModel):
    action: str  # "long" | "short" | "hold" | "close_all" | "reduce" | "adjust_sl" | "adjust_tp"
    asset_class: str
    symbol: str
    execution_mode: str  # "auto" | "advisory"
    position_size: float = Field(ge=0.0, le=0.15)
    leverage: float = Field(ge=1.0, le=3.0)
    stop_loss: float = Field(ge=0.0, le=0.10)  # Wider for stocks
    take_profit: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    engine: Optional[str] = None
    reason: str
    # Advisory fields (for human operator)
    suggested_entry_price: Optional[float] = None
    suggested_entry_zone: Optional[tuple[float, float]] = None  # (low, high)
    tp_levels: Optional[list[float]] = None  # Multiple TP targets
    conditional_alerts: Optional[list[str]] = None  # "If price reaches X, do Y"
    timestamp: datetime


class NewsSentiment(ArgusModel):
    """HERMES news sentiment output."""
    headline: str
    source: str
    asset_class: str
    affected_symbols: list[str]
    sentiment_score: float = Field(ge=-100.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    action: str   # "NONE" | "BLOCK_ENTRY" | "CLOSE_POSITION" | "ADJUST_SL" | "ADJUST_TP" | "ALERT_ONLY"
    reasoning: str
    timestamp: datetime


class RiskVerdict(ArgusModel):
    approved: bool
    reason: str
    adjusted_decision: Optional[Decision] = None
    risk_level: int = Field(ge=0, le=4)


class ExecutionResult(ArgusModel):
    success: bool
    execution_mode: str  # "auto" | "advisory"
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None
    slippage: Optional[float] = None
    fees: Optional[float] = None
    sl_order_id: Optional[str] = None
    advisory_message: Optional[str] = None  # For advisory mode
    reason: str
    timestamp: datetime


class Position(ArgusModel):
    symbol: str
    asset_class: str
    side: str  # "long" | "short"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sl_price: float
    tp_price: Optional[float] = None
    entry_time: datetime
    duration_hours: float
    exchange_sl_order_id: str  # MUST exist for auto mode
    execution_mode: str  # "auto" | "advisory"


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
    # Multi-asset allocation
    allocation_crypto_pct: float
    allocation_equity_pct: float
    allocation_commodity_pct: float
    allocation_cash_pct: float
    timestamp: datetime


class TradeRecord(ArgusModel):
    trade_id: str
    symbol: str
    asset_class: str
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
    reason_exit: str
    execution_mode: str  # "auto" | "advisory"


class TelemetryEvent(ArgusModel):
    event_type: str
    timestamp: datetime
    run_id: str
    inputs_hash: Optional[str] = None
```

### 1C: `src/core/events.py` — EventBus

```python
from typing import Callable, Any
from enum import Enum

class EventType(str, Enum):
    CANDLE_CLOSE = "candle_close"
    SENTINEL_CHECK = "sentinel_check"
    FEATURES_READY = "features_ready"
    REGIME_SNAPSHOT = "regime_snapshot"
    REGIME_CHANGED = "regime_changed"
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_REJECTED = "signal_rejected"
    DECISION_MADE = "decision_made"
    RISK_CHECK = "risk_check"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    SL_PLACED = "sl_placed"
    SL_FAILED = "sl_failed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    KILL_SWITCH_CHANGE = "kill_switch_change"
    HEARTBEAT = "heartbeat"
    ALERT = "alert"
    DAILY_REPORT = "daily_report"
    ERROR = "error"
    # HERMES events (NEW)
    HERMES_NEWS_RECEIVED = "hermes_news_received"
    HERMES_ALERT = "hermes_alert"
    HERMES_BLOCK = "hermes_block"
    HERMES_CLOSE_POSITION = "hermes_close_position"
    HERMES_ADJUST_SL = "hermes_adjust_sl"
    HERMES_ADJUST_TP = "hermes_adjust_tp"
    # Advisory events (NEW)
    ADVISORY_SIGNAL = "advisory_signal"
    ADVISORY_UPDATE = "advisory_update"

class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(callback)

    def publish(self, event_type: EventType, data: Any) -> None:
        key = event_type.value
        for callback in self._subscribers.get(key, []):
            callback(data)
```

### 1D: `src/core/config.py` — YAML config loader

Load from `config/` directory. Merge base.yaml with mode-specific yaml. Return typed objects. Implement this with pydantic models for each config section.

### 1E: `src/core/exceptions.py`

```python
class ArgusError(Exception): ...
class DataStaleError(ArgusError): ...
class SentinelHaltError(ArgusError): ...
class KillSwitchActiveError(ArgusError): ...
class NaNPropagationError(ArgusError): ...
class SLPlacementFailedError(ArgusError): ...
class ReconciliationError(ArgusError): ...
class HermesBlockError(ArgusError): ...  # HERMES blocked the trade
class AdvisoryOnlyError(ArgusError): ...  # Asset is advisory-only, no auto-execution
```

### 1F: `src/core/clock.py`

Unified clock. In live mode returns `datetime.utcnow()`. In backtest mode returns simulated time that advances per candle.

### 1G: `src/core/constants.py`

Named constants. No magic numbers anywhere in codebase. Include asset class constants, execution mode constants, and HERMES urgency levels.

### 1H: Config YAML files

Create these in `config/`:

**`config/base.yaml`:**
```yaml
system:
  name: "argus"
  version: "2.0.0"
  mode: "paper"
  log_level: "INFO"

asset_classes:
  crypto:
    enabled: true
    execution_mode: "auto"
    exchange: "bingx"
    symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
  us_equity:
    enabled: true
    execution_mode: "auto"  # via BingX CFDs
    exchange: "bingx"
    symbols: ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META"]
  commodity:
    enabled: true
    execution_mode: "auto"  # via BingX CFDs
    exchange: "bingx"
    symbols: ["XAUUSD", "XAGUSD"]
  index:
    enabled: true
    execution_mode: "auto"  # via BingX CFDs
    exchange: "bingx"
    symbols: ["NAS100", "SPX500"]
  bist:
    enabled: false
    execution_mode: "advisory"
    exchange: null
    symbols: ["THYAO", "ASELS", "SISE"]

timeframes:
  primary: "1h"
  confirmation: "4h"
  direction: "1d"

exchanges:
  primary: "bingx"
  fallback: "binance"
```

**`config/regimes.yaml`:**
```yaml
regime:
  states: ["TRENDING", "RANGING", "VOLATILE", "CRISIS"]
  default: "RANGING"
  thresholds:
    trending: { adx_min: 25, alignment_candles: 20 }
    ranging: { adx_max: 20, hurst_max: 0.45, bb_period: 20 }
    volatile: { atr_ratio_min: 1.8, vol_multiple: 2.0 }
    crisis: { price_drop_24h: -0.08, vol_multiple: 3.0, depth_collapse: 0.30 }
  confirmation:
    trending_to_ranging: 3
    ranging_to_trending: 3
    to_volatile: 2
    to_crisis: 0
    crisis_to_volatile: 12
  hysteresis:
    min_candles_before_transition: 6
    crisis_exempt: true
    volatile_to_normal_min: 4
  hermes_overrides:
    critical_news_forces_crisis: true
    negative_news_blocks_entry_threshold: -50
```

**`config/engines.yaml`:**
```yaml
engines:
  titan:
    active_regimes: ["TRENDING"]
    min_adx: 25
    min_confidence: 0.55
    max_concurrent: 2
    trend_follow: { ema_fast: 21, ema_slow: 55, atr_trail_mult: 2.5, min_volume_ratio: 1.0 }
    breakout: { donchian_period: 20, volume_spike: 1.5, atr_filter: 0.005, confirmation_candles: 2 }
  nautilus:
    active_regimes: ["RANGING"]
    max_adx: 22
    min_confidence: 0.55
    bb_reversion: { period: 20, std: 2.0, entry_threshold: 0.05, rsi_oversold: 30, rsi_overbought: 70, stop_mult: 1.0, target: "mid" }
    funding_reversion: { extreme_pctile: 90, extreme_neg_pctile: 10, hold_periods: 8, stop_pct: 0.03 }
  phoenix:
    active_regimes: ["TRENDING", "RANGING", "VOLATILE"]
    min_confidence: 0.60
    funding_harvest: { entry_pctile: 95, confirmation_periods: 2, exit_pctile: 60, stop_pct: 0.025 }
    basis_trade: { entry_basis_pct: 0.003, exit_basis_pct: 0.001, stop_pct: 0.005, max_duration_hours: 72 }
  hermes:
    active_regimes: ["TRENDING", "RANGING", "VOLATILE", "CRISIS"]  # Always active
    min_confidence: 0.65
    news_fetch_interval_s: 60
    llm_backend: "ollama"  # "ollama" | "groq"
    ollama_url: "http://127.0.0.1:11434/api/generate"
    ollama_model: "llama3.1:8b"
    groq_model: "llama-3.3-70b-versatile"
    position_management:
      critical_news_close_immediately: true
      high_news_tighten_sl: true
      positive_news_trail_tp: true
    feeds:
      crypto: ["coindesk", "cointelegraph", "theblock", "decrypt"]
      finance: ["yahoo_finance", "reuters"]
      regulatory: ["sec_edgar"]
  atlas:
    risk_on_mult: [1.0, 1.5]
    risk_neutral_mult: [0.7, 1.0]
    risk_off_mult: [0.2, 0.5]
    crisis_mult: 0.0
```

**`config/risk.yaml`:**
```yaml
risk:
  sizing: { base_risk_pct: 0.02, min_risk_pct: 0.005, max_risk_pct: 0.03, max_position_size: 0.15, max_leverage: 2.0 }
  stop_loss:
    min_stop: 0.01
    max_stop: 0.05
    stock_max_stop: 0.08  # Stocks need wider stops
    multipliers: { titan_trend_follow: 2.5, titan_breakout: 2.0, nautilus_bb_reversion: 1.0, nautilus_funding: 3.0, phoenix_funding: 2.5, phoenix_basis: 3.0 }
  drawdown:
    dd_caution: 0.02
    dd_defensive: 0.04
    dd_halt: 0.06
    dd_lockdown: 0.10
    dd_multipliers: { below_2pct: 1.0, below_4pct: 0.5, below_6pct: 0.25, above_6pct: 0.0 }
  daily_limits: { soft_cap: -0.015, hard_cap: -0.025, max_trades: 15 }
  kill_switch:
    levels: [0, 1, 2, 3, 4]
    size_multipliers: [1.0, 0.75, 0.40, 0.0, 0.0]
    de_escalation_hours: { caution_to_normal: 24, defensive_to_caution: 48 }
  guards: { correlation_max: 0.6, funding_settlement_blackout_min: 15, weekend_size_mult: 0.5, consecutive_loss_cooldown: 3, equity_curve_ma_period: 20, single_trade_max_loss: 0.03 }
  portfolio_allocation:
    max_crypto_pct: 0.50
    max_equity_pct: 0.40
    max_commodity_pct: 0.20
    min_cash_pct: 0.10
```

**`config/telemetry.yaml`:**
```yaml
telemetry:
  sqlite_path: "data/trade_logs/argus.db"
  heartbeat_interval_s: 60
  alerts:
    telegram: { enabled: true, levels: ["URGENT", "CRITICAL", "EMERGENCY"] }
    log: { enabled: true, levels: ["INFO", "URGENT", "CRITICAL", "EMERGENCY"] }
  retention: { heartbeat_days: 90, features_days: 180, decisions: "indefinite", trades: "indefinite" }
  advisory:
    telegram_chat_id: null  # Set in secrets
    alert_format: "detailed"  # "brief" | "detailed"
    include_charts: false
```

### 1I: `tests/unit/test_types.py`

Write tests for:
- FeatureVector creation with all fields (crypto asset with all fields)
- FeatureVector creation for non-crypto (us_equity with crypto-native fields as None)
- FeatureVector rejects NaN in non-Optional fields
- Decision rejects leverage > 3.0
- Decision rejects position_size > 0.15
- EngineSignal rejects stop_distance > 0.10
- All models are frozen (raises on attribute assignment)
- RegimeState rejects confidence > 1.0
- RiskVerdict rejects risk_level > 4
- NewsSentiment validation (score bounds, urgency values)
- Decision with advisory fields populated
- PortfolioState with allocation percentages

### Phase 1 Gate
```bash
pytest tests/unit/test_types.py -v
```

---

## PHASE 2: DATA LAYER

### Sentinel (`src/data/sentinel/validator.py`)

6 checks (asset-class aware):
1. Data staleness: any source > 2x expected interval
2. Price anomaly: price move > 3 sigma without volume confirmation
3. Spread blowout: spread > 5x normal
4. Exchange latency: response time > 2s
5. Orderbook depth: depth < 30% normal within 5% of mid (crypto only)
6. Funding flash spike: funding > 10x normal (crypto only)

For non-crypto assets, checks 5 and 6 are skipped, and score is out of 4 checks instead of 6.

Score = checks_passed / total_applicable_checks. Thresholds:
- >= 0.7 → proceed
- 0.4-0.7 → proceed but reduce engine confidence by 30%
- < 0.4 → HALT (no new trades)
- < 0.2 → EMERGENCY (close all positions)

### Features (`src/data/features/`)

Features split across files, with asset-class awareness:
- `technical.py`: Volatility(6) + Trend(6) + Momentum(5) = 17 — ALL asset classes
- `volume.py`: Volume(5) — ALL asset classes
- `microstructure.py`: Microstructure(5) — crypto fully, stocks partially
- `crypto_native.py`: Crypto-Native(7) — crypto ONLY, returns None for others
- `cross_asset.py`: Cross-Asset(4) — crypto primarily, optional for others
- `statistical.py`: Statistical(4) — ALL asset classes
- `sentiment.py`: HERMES sentiment(3) — ALL asset classes (NEW)
- `ml_features.py`: ML Output(8) — ALL asset classes (Chronos + LightGBM)

Use `pandas_ta` library for indicator computation. Cross-validate against freqtrade indicator implementations where applicable.

### NaN Policy
- Tier 1 NaN (core 17 technical features) → HALT pipeline, use last valid snapshot
- Tier 2 NaN (derived features) → Set to None, reduce sentinel score by 0.1
- Tier 3 NaN (crypto-native for non-crypto, ML outputs) → Set to None, no penalty
- If >5 Tier 1 NaN → sentinel_score = 0.0 → HALT all trading

### Phase 2 Gate
```bash
pytest tests/unit/test_sentinel.py tests/unit/test_features.py -v
```

---

## PHASE 3: REGIME DETECTION

### Rule-Based Classifier (`src/regime/rule_based.py`)

Priority order (first match wins):
1. **CRISIS** (instant, any 1 trigger): price_drop_24h < -8% OR vol > 3x 60d OR liquidation > 99th pctile OR depth < 30% OR **HERMES critical negative news**
2. **VOLATILE**: ATR(5)/ATR(20) > 1.8 OR vol > 2x 60d median
3. **TRENDING**: ADX > 25 AND directional alignment with MA(50) 20+ bars
4. **RANGING**: ADX < 20 AND Hurst < 0.45
5. **Default**: RANGING (conservative)

Note: HERMES critical news (urgency=CRITICAL, score < -70) immediately triggers CRISIS.

### State Machine (`src/regime/state_machine.py`)

Transition rules same as before. Additionally:
- HERMES can force CRISIS → transition is IMMEDIATE, no confirmation needed
- HERMES CRISIS recovery follows same 12-candle confirmation

### Consensus (`src/regime/consensus.py`)
- 3-of-4 classifiers must agree for TRENDING/RANGING
- Any 1 classifier sufficient for VOLATILE/CRISIS (safety bias)
- HERMES alone sufficient for CRISIS (news override)

### Phase 3 Gate
```bash
pytest tests/unit/test_regime.py tests/unit/test_state_machine.py -v
```

---

## PHASE 4: ENGINES

### Base (`src/engines/base.py`)
```python
from typing import Protocol, Optional
from src.core.types import EngineSignal, RegimeState, FeatureVector

class AbstractEngine(Protocol):
    def generate_signal(self, regime: RegimeState, features: FeatureVector) -> Optional[EngineSignal]: ...
```

### TITAN (`src/engines/titan/engine.py`)
- ONLY active in TRENDING regime AND adx_14 >= 25
- Works for ALL asset classes (crypto, stocks, commodities, indices)
- Sub-strategies: trend_follow (EMA 21/55 cross + ADX + ATR trailing) and breakout (Donchian 20 + volume spike 1.5x)
- Pick strongest sub-strategy, MIN_CONFIDENCE = 0.55
- Stop: trend_follow = 2.5x ATR, breakout = 2.0x ATR

### NAUTILUS (`src/engines/nautilus/engine.py`)
- ONLY active in RANGING regime AND adx_14 <= 22
- Works for ALL asset classes
- Sub-strategies: bb_reversion (BB(20,2) + RSI) and funding_reversion (funding > 90th pctile, crypto ONLY)
- Stop: bb_reversion = 1.0x ATR, funding = 3.0x ATR

### PHOENIX (`src/engines/phoenix/engine.py`)
- Active in TRENDING, RANGING, VOLATILE. NOT in CRISIS.
- Crypto-focused sub-strategies: funding_harvest and basis_trade
- For non-crypto: only available if a carry-like opportunity exists (interest rate differential, etc.)
- Stop: funding = 2.5x ATR, basis = 3.0x ATR

### HERMES (`src/engines/hermes/engine.py`) — NEW
- Active in ALL regimes including CRISIS
- Can generate independent signals based on news sentiment extremes
- Subscribes to news feed, scores headlines via LLM
- **Position management:** Monitors open positions and acts on breaking news
  - CRITICAL negative → close position immediately
  - HIGH negative → tighten SL to breakeven
  - Positive news on existing position → consider trailing TP
  - Regulatory news → always escalate to CRITICAL
- Publishes HERMES events to EventBus for MDE gates to consume

### ATLAS (`src/engines/atlas/risk_overlay.py`)
- NOT an engine. A risk multiplier overlay.
- Input: BTC dominance, total mcap momentum, stablecoin flows (crypto). VIX, yield curve (stocks).
- Output: risk_multiplier in [0.0, 1.5]
- RISK_ON: 1.0-1.5, RISK_NEUTRAL: 0.7-1.0, RISK_OFF: 0.2-0.5, CRISIS: 0.0

### Phase 4 Gate
```bash
pytest tests/unit/test_titan.py tests/unit/test_nautilus.py tests/unit/test_phoenix.py tests/unit/test_hermes.py tests/unit/test_atlas.py -v
```

---

## PHASE 5: MDE + RISK

### Router (`src/mde/router.py`)
```python
REGIME_TO_ENGINE = {
    "TRENDING": "TITAN",
    "RANGING": "NAUTILUS",
    "VOLATILE": "PHOENIX",
    "CRISIS": None,
}
```
- CRISIS: close_all if positions, hold otherwise
- If lead engine returns None → try PHOENIX as fallback
- HERMES can override any engine's signal (veto or boost)

### Gates (`src/mde/gates.py`)
8 sequential gates, ALL must pass:
0. sentinel_score < 0.4 → HOLD
1. regime == CRISIS → CLOSE_ALL or HOLD
2. **hermes_block active → HOLD** (NEW — HERMES gate)
3. rsl_level >= 3 → HOLD; >= 2 → only PHOENIX
4. signal is None → HOLD
5. confidence < 0.55 → HOLD
6. net_expected_return < 0.001 → HOLD
7. reward_risk_ratio < 1.5 → HOLD

Every rejection logged with: gate_number, reason, features_snapshot.

### Execution Mode Router (`src/mde/execution_router.py`) — NEW
```python
def get_execution_mode(asset_class: str, config: dict) -> str:
    """Returns 'auto' or 'advisory' based on asset class config."""
    return config["asset_classes"][asset_class]["execution_mode"]
```

For advisory mode, instead of executing, format a detailed Telegram message with entry/SL/TP.

### Sizing (`src/mde/sizing.py`)
```
risk_per_trade = 0.02 × atlas_mult × sentinel × regime_conf × dd_mult × rsl_mult × hermes_mult
risk_per_trade = clamp(0.005, 0.03)
position_size = risk_per_trade / stop_distance
position_size = clamp(0.0, 0.15)

dd_mult = {DD<2%: 1.0, DD<4%: 0.5, DD<6%: 0.25, DD>6%: 0.0}
rsl_mult = {L0: 1.0, L1: 0.5, L2+: 0.0}
hermes_mult = {neutral: 1.0, mild_negative: 0.85, negative: 0.60, critical: 0.0}
```

### Portfolio-Level Allocation (`src/portfolio/allocator.py`) — NEW
- Max 50% in crypto, max 40% in equities, max 20% in commodities, min 10% cash
- Cross-asset correlation check before new positions
- Total portfolio heat (sum of risk across all positions) < 10%

### Kill Switch (`src/risk/kill_switch.py`)

Same 5-level FSM. State persists in SQLite. Now also triggered by HERMES:
- HERMES critical news on portfolio-wide assets → immediate escalation to HALT

### Pre-Trade Checks (`src/risk/pre_trade.py`)
9 checks, ALL must pass:
1. position_size <= 0.15
2. leverage <= 2.0
3. trades_today < 15
4. not within 15min of funding settlement (crypto only)
5. weekend → size × 0.5 (crypto only, stocks closed anyway)
6. correlation with existing positions < 0.6
7. stop_loss > 0
8. stop_loss <= max_stop for asset class
9. **portfolio allocation within limits** (NEW)

### Phase 5 Gate
```bash
pytest tests/unit/test_mde.py tests/unit/test_sizing.py tests/unit/test_rsl.py tests/unit/test_kill_switch.py tests/unit/test_pre_trade.py tests/unit/test_allocator.py -v
```

---

## PHASE 6: EXECUTION

### Executor (`src/execution/executor.py`)

Dual-mode executor:

**Auto mode** (crypto, BingX stocks/commodities):
4 urgency levels:

| Urgency | When | Order Type | Timeout |
|---------|------|-----------|---------|
| EMERGENCY | Kill switch / HERMES critical | Market | Immediate |
| HIGH | Confidence > 0.8 | Aggressive limit | 30s → market |
| NORMAL | Standard | Limit at mid | 60s → cancel |
| LOW | Carry trade | Passive limit | 5min → cancel |

**Advisory mode** (BIST, any non-API asset):
- Format detailed alert message
- Send via Telegram with: signal, entry zone, SL, TP levels, size, confidence, reasoning
- Log as advisory trade in telemetry
- Track manual execution status (operator confirms via Telegram)

### SL Manager (`src/execution/sl_manager.py`)
- After fill: IMMEDIATELY place exchange-side SL (auto mode only)
- SL MUST be confirmed before proceeding
- If SL placement fails → close position immediately + emit SL_FAILED alert
- For advisory mode: include SL in alert message, track operator compliance

### HERMES Position Manager (`src/execution/hermes_position_manager.py`) — NEW
- Subscribes to HERMES events
- Maintains watchlist of symbols with open positions
- On HERMES_CLOSE_POSITION: immediately close via market order
- On HERMES_ADJUST_SL: modify exchange SL order
- On HERMES_ADJUST_TP: modify exchange TP order (if exists) or set new one
- For advisory positions: send Telegram update with recommended action

### Reconciler (`src/execution/reconciler.py`)
- Compare local state vs exchange state every 60s
- Flag and log any discrepancy
- Auto-correct if difference is minor, alert if major

### Phase 6 Gate
```bash
pytest tests/unit/test_sl_manager.py tests/unit/test_hermes_position_manager.py tests/integration/test_execution.py -v
```

---

## PHASE 7: TELEMETRY

### Event Logger (`src/telemetry/event_logger.py`)
Log these 29 event types to SQLite:
candle_close, sentinel_check, features_ready, regime_snapshot, regime_changed, signal_generated, signal_rejected, decision_made, risk_check, order_submitted, order_filled, order_rejected, sl_placed, sl_failed, position_opened, position_closed, kill_switch_change, heartbeat, alert, daily_report, error, hermes_news_received, hermes_alert, hermes_block, hermes_close_position, hermes_adjust_sl, hermes_adjust_tp, advisory_signal, advisory_update

Every event includes: timestamp, run_id, inputs_hash, asset_class.
Every rejection includes: full features_snapshot + reason.

### Phase 7 Gate
```bash
pytest tests/integration/test_telemetry.py -v
```

---

## PHASE 8: BACKTEST LAB (NEW — Major Addition)

### Overview

A professional-grade backtest lab that supports:
1. **Per-asset backtesting:** Test each asset independently
2. **Portfolio-level backtesting:** Test the full hedge fund allocation strategy
3. **Walk-forward validation:** Rolling train/test windows (pattern from Jesse)
4. **ML training data generation:** Produce clean, labeled datasets for model training
5. **Cross-validation:** Purged k-fold CV to prevent lookahead bias (from mlfinlab)

### Architecture (`src/backtest/`)

```
src/backtest/
├── __init__.py
├── engine.py           # Main backtest loop (jesse-inspired)
├── data_manager.py     # Historical data fetching, caching, validation
├── lab/
│   ├── __init__.py
│   ├── asset_tester.py     # Per-asset backtest runner
│   ├── portfolio_tester.py # Full portfolio simulation
│   ├── walk_forward.py     # Walk-forward window manager (jesse pattern)
│   └── report.py           # Backtest report generator
├── ml_data/
│   ├── __init__.py
│   ├── labeler.py          # Triple barrier labeling (mlfinlab)
│   ├── feature_store.py    # Clean feature snapshots for ML training
│   └── splitter.py         # Purged k-fold CV splits
└── metrics.py              # Sharpe, Sortino, Calmar, max DD, win rate, etc.
```

### Per-Asset Backtester
- Run the full pipeline (features → regime → engine → gates → sizing → execution sim) for a single asset
- Track: PnL, drawdown, win rate, Sharpe, Sortino, Calmar, avg trade duration
- Compare against buy-and-hold benchmark

### Portfolio-Level Backtester
- Simulate the full hedge fund: multiple assets, allocation limits, correlation checks
- Track: total fund PnL, allocation over time, max drawdown, cash usage
- Answer: "How does the fund perform as a whole? How does allocation change over time?"

### ML Data Quality
- All backtest data stored in Parquet (10x faster than JSON, pattern from freqtrade)
- Feature snapshots labeled with future returns (1h, 4h, 1d, 1w)
- Triple barrier labeling: TP hit, SL hit, or time expired
- No lookahead bias — features computed ONLY from data available at decision time
- Purged k-fold cross-validation for model evaluation

### Walk-Forward Validation
```
Window 1: Train [0, 1000], Test [1000, 1200]
Window 2: Train [200, 1200], Test [1200, 1400]
Window 3: Train [400, 1400], Test [1400, 1600]
...
```
- Expanding or rolling windows (configurable)
- Each window: train LightGBM, evaluate on test, record metrics
- Final: aggregate metrics across all windows

### Phase 8 Gate
```bash
pytest tests/unit/test_backtest.py tests/integration/test_backtest_lab.py -v
```

---

## PHASE 9: ML PIPELINE

### Amazon Chronos Integration (`src/ml/chronos/`)
```python
from chronos import ChronosPipeline

class ChronosForecaster:
    def __init__(self, model_name: str = "amazon/chronos-bolt-base"):
        self.pipeline = ChronosPipeline.from_pretrained(model_name)

    def forecast(self, price_series: list[float], horizon: int = 1) -> dict:
        """Returns median forecast and confidence width."""
        # Feed close prices, get quantile forecasts
        ...
```

### LightGBM Training (`src/ml/training/`)
- Train on walk-forward windows from backtest lab
- Features: all 50+ from FeatureVector
- Target: triple-barrier label (1 = profit, 0 = loss, -1 = SL hit)
- Output: lgbm_direction, lgbm_confidence → fed back into FeatureVector

### Meta-Labeling (from mlfinlab)
- First model predicts direction
- Meta-label model predicts whether the first model's prediction will be profitable
- Only take trades where both models agree

### Phase 9 Gate
```bash
pytest tests/unit/test_chronos.py tests/unit/test_lgbm.py tests/integration/test_ml_pipeline.py -v
```

---

## PHASE 10: MAIN PIPELINE

### `src/main.py` — 11-step pipeline

```
Step 1: Data Acquisition — per asset class (< 500ms)
Step 2: Sentinel Validation — asset-class aware (< 100ms)
Step 3: HERMES News Check — parallel async (< 2000ms)
Step 4: Snapshot Build — 50+ features (< 2000ms)
Step 5: Regime Detection — includes HERMES override (< 200ms)
Step 6: Engine Signal Generation — route to correct engine (< 500ms)
Step 7: MDE Routing + 8 Gates — includes HERMES gate (< 100ms)
Step 8: Risk Verification + Kill Switch + Portfolio Allocation (< 50ms)
Step 9: Execution + SL — auto or advisory based on asset class (< 5000ms)
Step 10: Telemetry — log everything including HERMES events
Step 11: Post-Trade Evaluation + HERMES position monitoring (async)

TOTAL: < 10 seconds from candle close to order placed.
```

Entry point: `python src/main.py --mode paper|live|backtest --assets crypto,us_equity,commodity`

### Stress Tests

`tests/stress/test_crash_scenario.py`: Inject 15% drop → verify CRISIS detected, positions closed, system halts
`tests/stress/test_regime_flapping.py`: ADX oscillates around 25 → verify max 2 transitions in 48h
`tests/stress/test_nan_propagation.py`: Inject NaN → verify caught at Layer 0
`tests/stress/test_hermes_critical_news.py`: Inject critical negative news → verify positions closed, CRISIS triggered
`tests/stress/test_multi_asset_correlation.py`: High correlation across assets → verify allocation limits enforced
`tests/stress/test_advisory_mode.py`: BIST signal → verify no execution, only Telegram alert sent

### Phase 10 Gate
```bash
pytest tests/ -v --tb=short
```

---

## RULES

1. **DO NOT modify `argus_py/`.** All code in `src/`.
2. **All models: pydantic v2, frozen=True, strict=True.**
3. **No magic numbers.** Everything from config YAML.
4. **No NaN propagation past Layer 0.**
5. **Every decision logged. No exceptions.**
6. **Exchange-side SL mandatory on every AUTO-executed position.**
7. **Run `pytest` after EACH phase. Do not proceed if tests fail.**
8. **Priority: Capital Safety > Robustness > Scale > Profit.**
9. **Multi-asset: every interface must be asset-class agnostic.** Asset-specific logic in adapters only.
10. **HERMES has veto and position management authority.** It can block entries AND close/adjust existing positions.
11. **Advisory mode for non-API assets:** Full analysis, Telegram alerts with entry/SL/TP, no auto-execution.
12. **Reference repos:** Study freqtrade, qlib, jesse, mlfinlab patterns. Don't reinvent the wheel.
13. **Data quality:** All backtest/training data in Parquet. No lookahead bias. Purged k-fold CV for ML.

## FINAL VERIFICATION

```bash
pytest tests/ -v --tb=short
mypy src/ --strict
ruff check src/
grep -r "from argus_py" src/ && echo "FAIL" || echo "PASS: no argus_py imports"
```

**START WITH PHASE 1. Check if `src/` exists from prior session. Complete any missing Phase 1 files, write tests, make them pass. Then proceed to Phase 2.**
