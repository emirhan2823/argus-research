# ARGUS v2.5 Data Structures & Schemas

## 1. Canonical Contracts (Python Dataclasses / JSON Schemas)

These contracts define the immutable data structures passed between modules. All fields are mandatory unless marked Optional.

### 1.1 MarketSnapshot
Raw data received from the Exchange (BingX).
```python
@dataclass(frozen=True)
class MarketSnapshot:
    exchange: str          # "bingx"
    symbol: str            # "BTC/USDT:USDT"
    timestamp: int         # UTC Milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    bid: float             # Best Bid
    ask: float             # Best Ask
    funding_rate: float    # Current funding rate (futures only)
```

### 1.2 FeatureVector (The "Context")
Enriched data used by Oracle and Models.
```python
@dataclass(frozen=True)
class FeatureVector:
    timestamp: int
    symbol: str

    # Technicals
    rsi_14: float
    atr_14: float
    ema_50: float
    ema_200: float
    adx_14: float
    volume_zscore: float   # (vol - mean_20) / std_20

    # Context (Time Machine)
    news_score: float      # [-1.0 to 1.0] from FinBERT
    macro_signal: float    # [0.0 to 1.0] derived from VIX/DXY correlation
    whale_pulse: float     # [0.0 to 1.0] large trade imbalance ratio

    # Regime
    regime_label: str      # "TREND_UP", "TREND_DOWN", "CHOP", "VOLATILE"
```

### 1.3 Signal
Raw output from a specific Strategy (Darwin genome or Pattern logic).
```python
@dataclass(frozen=True)
class Signal:
    id: str                # UUID
    timestamp: int
    strategy_id: str       # "darwin_v2_gen_45_id_12"
    symbol: str
    direction: str         # "LONG" | "SHORT" | "FLAT"
    strength: float        # 0.0 to 1.0 (Raw confidence)

    # Strategy specific metadata
    stop_loss_price: float
    take_profit_price: float
    entry_zone_start: float
    entry_zone_end: float
```

### 1.4 SignalQualityScore (SQS)
The "Gatekeeper" score. Calculated by the SQS Engine.
```python
@dataclass(frozen=True)
class SignalQualityScore:
    signal_id: str
    total_score: float     # 0.0 to 1.0. (Threshold usually > 0.7)

    # Components
    regime_match: float    # 1.0 if signal direction matches regime
    structure_score: float # 0.0-1.0 (e.g., proximity to support/resistance)
    microstructure_score: float # 0.0-1.0 (Order book imbalance favorability)
    news_sentiment_score: float # 0.0-1.0 (1.0 = positive news for LONG)
    correlation_risk: float # 0.0-1.0 (1.0 = Low correlation risk)
    fee_expectancy: float  # Expected Return / (Fees + Slippage). > 1.0 is good.

    passed: bool           # True if total_score >= Threshold
```

### 1.5 TradeDecision
The final command sent to Executioner.
```python
@dataclass(frozen=True)
class TradeDecision:
    signal_id: str
    decision: str          # "EXECUTE" | "REJECT" | "WAIT"
    rejection_reason: Optional[str]

    # Sizing (HyperSizer output)
    size_usd: float        # Position size in Quote currency
    leverage: int          # 1x to 5x

    # Execution Parameters
    order_type: str        # "LIMIT" | "MARKET" | "TWAP"
    limit_price: Optional[float]
    time_in_force: str     # "GTC" | "IOC" | "FOK"
```

### 1.6 ExecutionPlan (Internal to Executioner)
How the Decision is broken down into orders.
```python
@dataclass(frozen=True)
class ExecutionPlan:
    decision_id: str
    slices: int            # Number of sub-orders (1 for small size)
    interval_ms: int       # Delay between slices
    limit_offset: float    # Price improvement target
```

---

## 2. SQLite Schema (Hot Storage)

Used for: Live state, recent history (last 30 days), active orders, ledger.
File: `data/live.db`

### 2.1 Table: assets
Static configuration for tradable symbols.
```sql
CREATE TABLE assets (
    symbol TEXT PRIMARY KEY,       -- "XAU/USDT:USDT"
    base_asset TEXT,               -- "XAU"
    quote_asset TEXT,              -- "USDT"
    exchange TEXT,                 -- "bingx"
    status TEXT,                   -- "ACTIVE" | "HALTED" | "ONLY_REDUCE"
    min_size REAL,
    tick_size REAL,
    max_leverage INT DEFAULT 5,
    is_favorite BOOLEAN DEFAULT 0
);
```

### 2.2 Table: signals
Log of all generated signals (passed or rejected).
```sql
CREATE TABLE signals (
    id TEXT PRIMARY KEY,
    timestamp INTEGER,             -- UTC Milliseconds
    symbol TEXT,
    strategy_id TEXT,
    direction TEXT,
    strength REAL,
    sqs_score REAL,
    sqs_passed BOOLEAN,
    decision TEXT,                 -- "EXECUTE" | "REJECT"
    FOREIGN KEY(symbol) REFERENCES assets(symbol)
);
CREATE INDEX idx_signals_ts ON signals(timestamp);
```

### 2.3 Table: trades
Completed or Active trades.
```sql
CREATE TABLE trades (
    id TEXT PRIMARY KEY,           -- Exchange Order ID or Internal UUID
    signal_id TEXT,
    symbol TEXT,
    side TEXT,                     -- "LONG" | "SHORT"
    status TEXT,                   -- "OPEN" | "CLOSED" | "CANCELED"

    entry_price REAL,
    entry_time INTEGER,
    entry_size REAL,

    exit_price REAL,
    exit_time INTEGER,

    pnl_realized REAL,
    fees_paid REAL,
    funding_paid REAL,

    max_drawdown_pct REAL,         -- Max adverse excursion during trade
    max_profit_pct REAL,           -- Max favorable excursion

    FOREIGN KEY(signal_id) REFERENCES signals(id)
);
CREATE INDEX idx_trades_status ON trades(status);
```

### 2.4 Table: ledger (Audit Trail)
Append-only log of critical system events. **Immutable.**
```sql
CREATE TABLE ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER,
    event_type TEXT,               -- "STARTUP", "ERROR", "TRADE_OPEN", "RISK_LOCK"
    severity TEXT,                 -- "INFO", "WARNING", "CRITICAL"
    component TEXT,                -- "Sentinel", "Executioner"
    message TEXT,
    json_details TEXT              -- Full context dump
);
```

---

## 3. Parquet Layout (Time Machine / Cold Storage)

Used for: Large historical datasets, Backtesting, Darwin Evolution.
Root: `data/time_machine/`

### 3.1 OHLCV Data
Partitioned by Symbol and Time (Month) to allow efficient query of specific assets over specific periods.
```text
data/time_machine/ohlcv/
  exchange=bingx/
    symbol=XAU_USDT/
      year=2023/
        month=01/
          data.parquet  (Columns: ts, open, high, low, close, vol)
        month=02/
          data.parquet
```

### 3.2 Feature Store (Context Vectors)
Aligned with OHLCV but contains calculated features. Recomputed daily/weekly.
```text
data/time_machine/features/
  exchange=bingx/
    symbol=XAU_USDT/
      year=2023/
        month=01/
          features.parquet (Columns: ts, rsi_14, news_score, regime_label...)
```

### 3.3 Signals Archive
Long-term storage of every signal ever generated, used for "Reflector" analysis.
```text
data/time_machine/signals/
  strategy=trend_following_v1/
    year=2023/
      month=01/
        signals.parquet (Columns: ts, symbol, direction, strength, sqs_score, outcome_pnl)
```

---

## 4. Reflector Post-Mortem Schema

Stored in SQLite (`reflector_results`) or small Parquet files.
Records the "Counterfactual" analysis.

```sql
CREATE TABLE reflector_results (
    trade_id TEXT PRIMARY KEY,
    actual_pnl REAL,

    -- Simulation Results (What if we did X?)
    sim_hold_1h_pnl REAL,          -- If we held for 1 more hour
    sim_no_sl_pnl REAL,            -- If we had no stop loss
    sim_tight_sl_pnl REAL,         -- If SL was 50% tighter

    classification TEXT,           -- "SKILL", "LUCK", "BAD_TIMING", "NEWS_EVENT"
    adjustment_factor REAL         -- Recommendation for future sizing (e.g., 0.9 downsize)
);
```
