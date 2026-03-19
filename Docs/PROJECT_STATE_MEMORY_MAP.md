# ARGUS Project State & Memory Map — Dynamic Development Guide

**Version:** 2.0 (CAI Post-Mortem Upgrade)  
**Date:** 2026-02-16  
**Purpose:** Prevent context drift during multi-session coding. This is the living "Source of Truth" for implementation order, invariant rules, and interface contracts.  
**v2.0 Addendum:** Incorporates CAI battle-tested pivots — Validated Sizing Protocol, Dynamic 3-Stage Exit, Whale-Momentum Fusion, Hyper-Precision 1m/3m execution.

---

## 0) CODEBASE REALITY SNAPSHOT (as of 2026-02-15)

### What EXISTS and WORKS (import-safe)

```
src/
├── core/                        # STABLE — DO NOT REFACTOR
│   ├── types.py                 # FeatureVector (60+ fields), all core models
│   ├── config.py                # ArgusConfig root + 25 nested models
│   ├── events.py                # EventBus + 30 EventTypes
│   ├── constants.py             # Regime/Engine/KillSwitch constants
│   ├── clock.py                 # Live/backtest clock
│   ├── exceptions.py            # 8 exception types
│   ├── protocols.py             # ILeverageProvider, IPriceForecaster
│   └── hardware.py              # GPU/platform detection
│
├── v25/                         # STABLE — extend only
│   ├── contracts/               # 30+ frozen Pydantic models (Decimal)
│   │   ├── base.py              # ArgusModel, TimestampedModel, AuditLog
│   │   ├── market.py            # OHLCV, Orderbook, Ticker, FundingRate
│   │   ├── signal.py            # SQSScore, ChopEdgeScore, SignalTemplate
│   │   ├── trade.py             # OrderRequest, ExecutionFill, Position, TradeRecord
│   │   ├── risk.py              # RiskLimits, PositionSize, CircuitBreakerState
│   │   ├── intelligence.py      # NewsAnalysis, WhaleAlert, SentimentSnapshot
│   │   ├── portfolio.py         # CorrelationMatrix (STUB), PortfolioVariance
│   │   ├── fee.py               # FeeModel
│   │   ├── ledger.py            # LedgerEvent
│   │   ├── position.py          # PositionState
│   │   ├── decision.py          # TradeDecision, SizingDecision, ExecutionPlan
│   │   └── regime.py            # RegimeState (v2.5)
│   ├── config/loader.py         # V25Config, FeeModelConfig, AccelConfig
│   ├── db/migrations.py         # 13 tables, 18 indexes
│   ├── db/connection.py         # SQLite WAL connection
│   ├── risk/                    # accel_gates, stop_resize, caps
│   ├── telemetry/log_writer.py  # log_decision, log_sqs, log_ledger_event
│   └── bootstrap.py             # Public API facade
│
├── engines/                     # STABLE — extend with new engines
│   ├── base.py                  # AbstractEngine Protocol
│   ├── titan/engine.py          # TRENDING: trend_follow + breakout
│   ├── nautilus/engine.py       # RANGING: bb_reversion + funding_reversion
│   ├── phoenix/engine.py        # Non-CRISIS: funding_harvest + basis_trade
│   ├── hermes/engine.py         # ALL: sentiment-driven, blocking
│   ├── hydra/engine.py          # RANGING: scalping (LIMIT orders)
│   └── atlas/risk_overlay.py    # Risk multiplier overlay
│
├── mde/                         # STABLE — extend with new routes
│   ├── router.py                # RegimeRouter: regime → engine dispatch
│   ├── gates.py                 # 8 sequential gates
│   ├── sizing.py                # Multiplicative risk model
│   ├── signal_quality.py        # 6-factor signal assessment
│   └── execution_router.py      # Execution mode from config
│
├── risk/                        # STABLE
│   ├── kill_switch.py           # 5-level persistent kill switch
│   ├── pre_trade.py             # 8 pre-trade checks (incl correlation)
│   └── sizing.py                # GrowthSizer, Kelly, correlation_dampening
│
├── regime/                      # STABLE
│   ├── rule_based.py            # RuleBasedRegimeClassifier
│   ├── consensus.py             # Multi-voter consensus
│   └── state_machine.py         # FSM with hysteresis + Hermes override
│
├── execution/                   # STABLE
│   ├── executor.py              # Auto/advisory dual-mode
│   ├── sl_manager.py            # SL enforcement with fallback
│   ├── reconciler.py            # Local vs exchange reconciliation
│   └── hermes_position_manager.py
│
├── learning/                    # STABLE
│   ├── darwin.py                # GA engine (18 genes, BLX-alpha crossover)
│   └── reflector.py             # 10 failure modes, shadow simulation
│
├── backtest/                    # STABLE
│   ├── engine.py                # BacktestEngine (fee + slippage)
│   ├── metrics.py               # sharpe, sortino, calmar, max_dd, win_rate
│   ├── data_manager.py          # Parquet/CSV data loading
│   ├── lab/                     # walk_forward, asset_tester, portfolio_tester, report
│   └── ml_data/                 # purged_kfold, triple_barrier, feature_store
│
├── data/                        # STABLE
│   ├── data_factory.py          # DataFactory (parquet replay + exchange)
│   └── sentinel/validator.py    # 6 data quality checks
│
├── portfolio/                   # STABLE
│   └── allocator.py             # PortfolioAllocator
│
├── main.py                      # ArgusPipeline (11-step), DemoBroker
│
├── v25/trainer/                 # SCAFFOLDED (from Auto-RBI session)
│   └── (empty scaffolds)
│
config/
├── base.yaml                    # System + assets + timeframes
├── risk.yaml                    # Sizing + stops + DD + kill switch + fees
├── engines.yaml                 # 5 engines + Atlas + dual-speed
├── regimes.yaml                 # 4 regimes + transitions + hysteresis
└── telemetry.yaml               # SQLite + heartbeat + Telegram
```

### What does NOT exist yet (plan-only)

| Planned Module | Plan Section | Status |
|---------------|-------------|--------|
| `src/correlation/` | NEW (Blueprint v1.0) | **DONE** (Phase A) |
| `src/engines/gemini/` | NEW (Blueprint v1.0) | **DONE** (Phase B) |
| `src/v25/contracts/correlation.py` | NEW (Blueprint v1.0) | **DONE** (Phase A) |
| `src/risk/validated_sizer.py` | NEW (CAI Pivot 1) | **DONE** (Phase G) |
| `src/v25/contracts/validated_sizing.py` | NEW (CAI Pivot 1) | **DONE** (Phase G) |
| `src/v25/contracts/exit_strategy.py` | NEW (CAI Pivot 3) | **DONE** (Phase H) |
| `src/execution/dynamic_exit.py` | NEW (CAI Pivot 3) | **DONE** (Phase H) |
| `src/engines/hermes/whale_momentum.py` | NEW (CAI Pivot 4) | **DONE** (Phase I) |
| `src/execution/hyper_precision.py` | NEW (CAI Pivot 5) | **DONE** (Phase J) |
| `src/engines/nautilus/range_mapper.py` | NEW (Phase D) | **DONE** |
| `src/engines/nautilus/micro_reversion.py` | NEW (Phase D) | **DONE** |
| `src/engines/nautilus/chop_corr_gap.py` | NEW (Phase D) | **DONE** |
| `src/mde/precision_filter.py` | NEW (Phase E) | **DONE** |
| `src/factory/` | Plan Section 25 | NOT STARTED |
| `src/evolution/` | Plan Section 26 | NOT STARTED |
| `src/daemon/` | Plan Section 27 | NOT STARTED |
| `src/radar/` | Plan Section 24 | NOT STARTED |
| `src/adapters/` | Plan Section 23 | NOT STARTED |
| `src/v25/intelligence/` | Plan Section 21 | NOT STARTED |

---

## 1) GOLDEN RULES — NEVER VIOLATE

These rules apply to ALL coding sessions. If any instruction conflicts with these rules, these rules win.

### GR-1: Protection > Profit
```
NEVER increase risk to chase returns.
Circuit breaker levels are immutable: 1.5% → 3% → 4% → 8%.
Kill switch level 3+ = EXIT ONLY. No exceptions.
```

### GR-2: Fee-Inclusive Everything
```
EVERY backtest MUST include fees + slippage.
FeeModel from src/v25/contracts/fee.py is the single source.
backtest_cost_mult = 2.0 (double fees in backtest for safety margin).
NEVER evaluate a strategy on gross returns.
```

### GR-3: Hermes Sentiment Check Before Every Trade
```
SQSScore.hermes_news_risk is component C5 (weight: 15%).
If hermes_news_risk < 0.10 → SQS fails → trade blocked.
If SentimentSnapshot.urgent_event = True → CRISIS override possible.
NO TRADE enters without sentiment check in the SQS pipeline.
```

### GR-4: Correlation Veto > Risk Tolerance
```
PreTradeInput.correlation_with_book > 0.60 → trade REJECTED.
This check exists in src/risk/pre_trade.py line 53.
The correlation engine FEEDS this value. It does not override it.
If CorrelationMatrix.is_decorrelated = False AND adding this trade
would exceed portfolio correlation limit → HARD BLOCK.
```

### GR-5: No Production Changes Without Tests
```
Every new module MUST have corresponding test file in tests/.
Tests MUST pass before merge: python -m pytest tests/ -x
Type checking MUST pass: python -m mypy src/ --ignore-missing-imports
```

### GR-6: Contracts Are Sacred
```
src/v25/contracts/ models are frozen=True, strict=True, extra="forbid".
NEVER add mutable state to contract models.
NEVER use float in v2.5 contracts — use Decimal.
NEVER skip NaN/Inf validation (ArgusModel._reject_nan).
```

### GR-7: Deterministic Reproducibility
```
All backtest runs seeded. All artifact outputs include run_id.
numpy.random.default_rng(seed) — never bare random.
Results must be reproducible given same seed + same data.
```

### GR-8: Exchange-Side Stop Loss Is Mandatory
```
Every open position MUST have SL on the exchange.
StopLossManager.enforce() verifies this every cycle.
SLPlacementFailedError → close position immediately.
```

### GR-9: Event Shield Before Macro Events
```
FOMC/CPI/NFP → 2h before: tighten stops, no new entries.
30min before: full shield (reduce or close all).
30min after: no trades (whipsaw risk).
Macro calendar is checked every pipeline cycle.
```

### GR-10: Single-Direction Extends Only
```
NEVER refactor existing stable modules during feature work.
ADD new files, EXTEND existing classes via composition.
If you must modify an existing file, the diff must be < 20 lines.
```

### GR-11: Leverage Is DERIVED, Never an Input (CAI Pivot 1)
```
The formula: notional = risk_usd / sl_pct
Leverage = notional / equity → ALWAYS a derived OUTPUT.
NEVER allow leverage as an input parameter that inflates position size.
Existing leverage_mult fields become CAPS, not multipliers.
compute_validated_size() is the canonical sizing function.
Any sizing path that bypasses this function is a BUG.
```

### GR-12: Breakeven-R Gate Mandatory (CAI Pivot 1)
```
breakeven_r = fee_cost / risk_usd
If breakeven_r > 0.30 → trade REJECTED (fees eat >30% of risk).
This gate (Gate 9) runs AFTER sizing, BEFORE execution.
No exceptions. Applies to ALL engines including Gemini and Hydra.
At BingX maker rates (0.02% RT), this allows stops as tight as 0.067%.
At BingX taker rates (0.10% RT), minimum viable stop is ~0.33%.
```

### GR-13: Dynamic Exit Overrides Static TP (CAI Pivot 3)
```
Static take-profit levels are REPLACED by 3-stage dynamic exit.
Stage 1 (+0.5R): close 25%, SL → breakeven.
Stage 2 (+1.5R): close 25%, engage ATR trailing.
Stage 3 (+3.0R): close 25%, tighten trailing.
Final 25% rides the trend until trailing stop hit.
Regime CRISIS → immediate market close ALL stages.
```

### GR-14: Defensive Always Beats Offensive (CAI Pivot 4)
```
Hermes defensive veto overrides whale momentum boost in ALL regimes.
Whale offensive boost ONLY in TREND_STRONG.
If hermes_news_risk < 0.30 → whale boost is ZERO (defensive override).
Max SQS C5 boost from whale momentum: +0.10 (capped at 1.0).
```

---

## 2) INTERFACE DEFINITIONS — Exact Function Signatures

### 2.1 — Correlation Engine Interfaces

```python
# src/correlation/tracker.py

def calculate_correlation(
    prices_a: pd.Series,      # close prices for asset A
    prices_b: pd.Series,      # close prices for asset B
    window: int = 100,         # rolling window in bars
) -> float:
    """Pearson rolling correlation. Returns [-1.0, 1.0]."""

def calculate_spread(
    prices_a: pd.Series,
    prices_b: pd.Series,
    method: str = "log_ratio",  # "log_ratio" | "zscore" | "residual"
) -> pd.Series:
    """Normalized spread between two price series."""

def estimate_half_life(
    spread: pd.Series,
) -> float | None:
    """Ornstein-Uhlenbeck half-life estimation.
    Returns None if spread is not mean-reverting (negative half-life).
    """

def test_cointegration(
    prices_a: pd.Series,
    prices_b: pd.Series,
    significance: float = 0.05,
) -> tuple[bool, float]:
    """Engle-Granger cointegration test.
    Returns (is_cointegrated, p_value).
    """

class CorrelationTracker:
    """Maintains rolling correlation state for all configured pairs."""

    def __init__(self, pairs_config: list[dict], clock: Clock) -> None: ...

    def update(
        self,
        prices: dict[str, pd.Series],  # symbol → close price series
    ) -> list[CorrelationPair]:
        """Recompute all pair correlations. Returns updated pair states."""

    def get_matrix(self) -> CorrelationMatrix:
        """Return full N×N correlation matrix for all tracked assets."""

    def get_pair(self, pair_id: str) -> CorrelationPair | None:
        """Lookup specific pair state."""
```

```python
# src/correlation/signals.py

class CorrelationSignalGenerator:
    """Generate trading signals from correlation state."""

    def __init__(self, pairs_config: list[dict]) -> None: ...

    def generate(
        self,
        pair: CorrelationPair,
        regime: RegimeState,
        sentiment: SentimentSnapshot | None = None,
    ) -> CorrelationSignal | None:
        """Generate signal if spread z-score exceeds entry threshold.
        Returns None if no signal.
        Respects regime filter (no signals in CRISIS).
        Applies sentiment modifier to confidence.
        """
```

```python
# src/correlation/ou_estimator.py

def fit_ou_process(
    spread: pd.Series,
) -> tuple[float, float, float]:
    """Fit Ornstein-Uhlenbeck process to spread series.
    Returns (theta: mean-reversion speed, mu: long-run mean, sigma: volatility).
    """
```

### 2.2 — Gemini Engine Interface

```python
# src/engines/gemini/engine.py

@dataclass
class GeminiEngine:
    """Correlation-based pairs trading engine.
    Consumes CorrelationSignal, produces EngineSignal.
    """
    correlation_tracker: CorrelationTracker
    signal_generator: CorrelationSignalGenerator
    max_simultaneous_pairs: int = 3

    def generate_signal(
        self,
        regime: RegimeState,
        features: dict[str, FeatureVector],  # symbol → features
    ) -> EngineSignal | None:
        """
        1. Update correlation tracker with latest prices.
        2. For each pair, check for CorrelationSignal.
        3. If signal found, convert to EngineSignal format.
        4. Return highest-confidence signal (or None).
        """
```

### 2.3 — Enhanced Nautilus (CHOP) Interfaces

```python
# src/engines/nautilus/chop_corr_gap.py

def detect_chop_correlation_gap(
    pair: CorrelationPair,
    regime_a: RegimeState,
    regime_b: RegimeState,
) -> CorrelationSignal | None:
    """
    In CHOP regime: if pair normally correlated but one asset
    deviates within the range → generate convergence signal.
    Only fires when BOTH assets are in CHOP/RANGING.
    """

# src/engines/nautilus/micro_reversion.py

def detect_micro_reversion(
    features: FeatureVector,
    range_high: float,
    range_low: float,
    range_midpoint: float,
) -> EngineSignal | None:
    """
    Within identified range, use 5m microstructure to enter:
    - Long at range_low if OBI > 0.55 and RSI < 35
    - Short at range_high if OBI < -0.55 and RSI > 65
    Stop: outside range by 0.5 ATR. Target: midpoint.
    """

# src/engines/nautilus/range_mapper.py

def identify_range(
    candles: pd.DataFrame,
    lookback: int = 50,
    atr_filter: float = 0.5,
) -> tuple[float, float, float] | None:
    """
    Detect horizontal range from recent candles.
    Returns (range_high, range_low, midpoint) or None if no range found.
    Uses cluster analysis on pivot highs/lows.
    """
```

### 2.4 — Precision Entry Interface

```python
# src/mde/precision_filter.py

@dataclass(frozen=True)
class PrecisionGrade:
    grade: str           # "A" | "B" | "C" | "D" | "F"
    score: float         # 0.0 to 1.0
    obi: float           # orderbook imbalance at entry
    spread_ratio: float  # current_spread / median_spread
    vwap_deviation: float
    recommended_entry: float   # optimal limit price
    recommended_order_type: str  # "limit" | "market"
    reason: str

def assess_entry_precision(
    features: FeatureVector,
    signal: EngineSignal,
    fee_model: FeeModel,
) -> PrecisionGrade:
    """
    Evaluate microstructure quality at the moment of entry.
    Returns grade A-F with optimal entry price.
    Grade F = do not enter (bad microstructure).
    """
```

### 2.5 — Validated Sizer Interface (CAI Pivot 1)

```python
# src/risk/validated_sizer.py

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
    breakeven_r: float          # fee_cost / risk_usd
    net_risk_usd: float         # risk_usd after fee reservation

def compute_validated_size(inp: ValidatedSizingInput) -> ValidatedSizingOutput:
    """THE canonical sizing function. Leverage is always a RESULT.

    Invariants enforced:
      1. sl_price != entry_price (division by zero guard)
      2. leverage <= phase_max_leverage (capped, never amplified)
      3. breakeven_r < 0.30 (if fees eat >30% of risk, skip trade)
      4. quantity > exchange_min_lot (tradeable amount)

    Fee-adjusted formula:
      notional = risk_usd / (sl_pct + fee_round_trip_pct)
      This ensures total risk (SL hit + fees) never exceeds risk_usd.
    """
```

### 2.6 — Dynamic Exit FSM Interface (CAI Pivot 3)

```python
# src/execution/dynamic_exit.py

class DynamicExitManager:
    """Manages 3-stage partial take-profit + ATR trailing stop."""

    def __init__(self, config: dict) -> None: ...

    def on_position_open(
        self,
        position_id: str,
        symbol: str,
        entry_price: float,
        risk_per_unit: float,  # abs(entry - sl) per unit
        regime: str,
    ) -> DynamicExitState:
        """Initialize exit state for a new position at Stage 0 (ENTRY)."""

    def update(
        self,
        state: DynamicExitState,
        current_price: float,
        atr_14: float,
        regime: str,
    ) -> tuple[DynamicExitState, list[dict]]:
        """Check for stage transitions. Returns (updated_state, actions).

        Actions are dicts like:
          {"action": "partial_close", "pct": 0.25, "reason": "BREAKEVEN_LOCK"}
          {"action": "move_sl", "new_sl": 98500.0, "reason": "breakeven"}
          {"action": "update_trailing", "new_sl": 99200.0, "reason": "atr_trail"}
          {"action": "market_close_all", "reason": "CRISIS_regime_flip"}

        Stage transitions:
          ENTRY → BREAKEVEN_LOCK at +0.5R
          BREAKEVEN_LOCK → PROFIT_CAPTURE at +1.5R
          PROFIT_CAPTURE → TREND_RIDER at +3.0R
          Any stage → CLOSED when trailing SL hit or CRISIS

        Regime-conditional:
          TREND_STRONG: all 3 stages, wide trail (ATR × 2.0 → 1.5)
          TREND_WEAK:   stages 1+2 only, tighter trail
          CHOP:         stage 1 only (exit at midpoint)
          VOLATILE:     stages 1+2, very tight trail (ATR × 1.0)
          CRISIS:       immediate market close ALL
        """

    def get_trailing_sl(
        self,
        state: DynamicExitState,
        current_price: float,
        atr_14: float,
    ) -> float | None:
        """Compute trailing SL (only moves up, never down).
        Returns None if trailing not yet engaged (pre-Stage 2).
        """
```

### 2.7 — Whale Momentum Interface (CAI Pivot 4)

```python
# src/engines/hermes/whale_momentum.py

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
      - momentum_score < -0.5 → sqs_boost = 0.0 (defensive takes over)
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
```

### 2.8 — Hyper-Precision Execution Interface (CAI Pivot 5)

```python
# src/execution/hyper_precision.py

class HyperPrecisionExecutor:
    """1m/3m timeframe execution layer for entry sniping and trailing."""

    def __init__(self, config: dict, fee_model: FeeModel) -> None: ...

    def snipe_entry(
        self,
        symbol: str,
        direction: str,           # "LONG" | "SHORT"
        target_price: float,      # from signal
        features_1m: FeatureVector,  # 1m timeframe features
    ) -> dict:
        """Attempt limit order entry on 1m timeframe.

        Returns:
          {"order_type": "limit", "price": ..., "timeout_bars": 3}
          {"order_type": "market", "reason": "timeout+urgency"}
          {"order_type": "skip", "reason": "obi_insufficient"}

        Logic:
          1. Check OBI > 0.60 on 1m bar (directional)
          2. Place limit at VWAP_1m band edge
          3. Timeout: 3 × 1m bars → fallback to market if urgency
        """

    def snipe_partial_exit(
        self,
        symbol: str,
        direction: str,
        pct_to_close: float,      # 0.25 typically
        features_1m: FeatureVector,
    ) -> dict:
        """Attempt limit partial close on 1m timeframe.

        Wait for OBI reversal (selling into strength, buying into weakness).
        Timeout: 5 × 1m bars → market order fallback.
        """

    def update_trailing_sl(
        self,
        symbol: str,
        current_price: float,
        atr_3m: float,            # ATR computed on 3m bars
        trailing_mult: float,     # from DynamicExitState
    ) -> float:
        """Recompute trailing SL using 3m ATR for tighter granularity.
        Updates exchange-side SL every 3 minutes.
        """
```

### 2.9 — Existing Interfaces (Reference — DO NOT REDEFINE)

```python
# src/engines/base.py — AbstractEngine Protocol
class AbstractEngine(Protocol):
    def generate_signal(
        self,
        regime: RegimeState,
        features: FeatureVector,
    ) -> EngineSignal | None: ...

# src/mde/gates.py — evaluate_gates
def evaluate_gates(inp: GateInput) -> GateResult: ...

# src/mde/sizing.py — compute_size
def compute_size(inp: SizingInput) -> SizingResult: ...

# src/risk/pre_trade.py — PreTradeChecker
class PreTradeChecker:
    def check(self, inp: PreTradeInput) -> PreTradeResult: ...

# src/risk/sizing.py — compute_growth_size
def compute_growth_size(inp: GrowthSizingInput) -> GrowthSizingResult: ...

# src/backtest/engine.py — BacktestEngine
class BacktestEngine:
    def run(self, candles: pd.DataFrame, signal_fn: Callable) -> BacktestResult: ...

# src/backtest/metrics.py — metric functions
def max_drawdown(equity_curve: Iterable[float]) -> float: ...
def win_rate(pnls: Iterable[float]) -> float: ...
def sharpe_ratio(returns: Iterable[float], periods_per_year: int = 8760) -> float: ...
def sortino_ratio(returns: Iterable[float], periods_per_year: int = 8760) -> float: ...
def calmar_ratio(returns: Iterable[float], equity_curve: Iterable[float], ...) -> float: ...
```

---

## 3) ATOMIC IMPLEMENTATION CHECKLIST

### Phase A: Correlation Engine Foundation

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| A-01 | Create `src/correlation/__init__.py` | `src/correlation/__init__.py` | — | import check | **DONE** |
| A-02 | Implement `calculate_correlation()` | `src/correlation/tracker.py` | A-01 | `test_calculate_correlation_basic` | **DONE** |
| A-03 | Implement `calculate_spread()` (log_ratio method) | `src/correlation/tracker.py` | A-01 | `test_spread_log_ratio` | **DONE** |
| A-04 | Implement `estimate_half_life()` (OU) | `src/correlation/ou_estimator.py` | A-01 | `test_half_life_mean_reverting` | **DONE** |
| A-05 | Implement `test_cointegration()` | `src/correlation/tracker.py` | A-01 | `test_cointegration_known_pair` | **DONE** |
| A-06 | Implement `CorrelationTracker` class | `src/correlation/tracker.py` | A-02..A-05 | `test_tracker_update` | **DONE** |
| A-07 | Create `CorrelationPair` contract | `src/v25/contracts/correlation.py` | — | `test_correlation_pair_validation` | **DONE** |
| A-08 | Create `CorrelationSignal` contract | `src/v25/contracts/correlation.py` | A-07 | `test_correlation_signal_validation` | **DONE** |
| A-09 | Create `CorrelationHealth` contract | `src/v25/contracts/correlation.py` | A-07 | `test_correlation_health_validation` | **DONE** |
| A-10 | Add pairs config to `config/engines.yaml` | `config/engines.yaml` | — | YAML load check | **DONE** |
| A-11 | Load pairs config in `V25Config` | `src/v25/config/loader.py` | A-10 | `test_load_gemini_config` | **DONE** |

### Phase B: Correlation Signal Generation + Gemini Engine

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| B-01 | Implement `CorrelationSignalGenerator` | `src/correlation/signals.py` | A-06, A-08 | `test_signal_when_spread_exceeds_threshold` | **DONE** |
| B-02 | Signal respects regime filter | `src/correlation/signals.py` | B-01 | `test_no_signal_in_crisis` | **DONE** |
| B-03 | Create `src/engines/gemini/__init__.py` | `src/engines/gemini/__init__.py` | — | import check | **DONE** |
| B-04 | Implement `GeminiEngine.generate_signal()` | `src/engines/gemini/engine.py` | B-01, A-06 | `test_gemini_produces_engine_signal` | **DONE** |
| B-05 | Register Gemini in `RegimeRouter` | `src/core/constants.py` | B-04 | `test_router_includes_gemini` | **DONE** |
| B-06 | Add `CORR_MEAN_REVERSION` to `TemplateName` | `src/v25/contracts/signal.py` | — | `test_template_enum` | **DONE** |
| B-07 | Add `CORR_DECOUPLING_ARB` to `TemplateName` | `src/v25/contracts/signal.py` | — | `test_template_enum` | **DONE** |

### Phase C: Database + Telemetry

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| C-01 | Add `correlation_logs` DDL | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-02 | Add `correlation_signals` DDL | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-03 | Add `pyramid_layers` DDL | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-04 | Add `hermes_fusion_log` DDL | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-05 | Add `precision_entries` DDL | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-06 | Add `dynamic_exit_log` DDL (Table 19, Pivot 3) | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-07 | Add `validated_sizing_log` DDL (Table 20, Pivot 1) | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-08 | Add `whale_momentum_log` DDL (Table 21, Pivot 4) | `src/v25/db/migrations.py` | — | `test_migration_creates_table` | **DONE** |
| C-09 | Add 14 new indexes (9 v1.0 + 5 v2.0) | `src/v25/db/migrations.py` | C-01..C-08 | `test_indexes_exist` | **DONE** |
| C-10 | Add `log_correlation()` to log_writer | `src/v25/telemetry/log_writer.py` | C-01 | `test_log_correlation` | **DONE** |
| C-11 | Add `log_precision_entry()` to log_writer | `src/v25/telemetry/log_writer.py` | C-05 | `test_log_precision` | **DONE** |
| C-12 | Add `log_dynamic_exit()` to log_writer | `src/v25/telemetry/log_writer.py` | C-06 | `test_log_dynamic_exit` | **DONE** |
| C-13 | Add `log_validated_sizing()` to log_writer | `src/v25/telemetry/log_writer.py` | C-07 | `test_log_validated_sizing` | **DONE** |
| C-14 | Add `log_whale_momentum()` to log_writer | `src/v25/telemetry/log_writer.py` | C-08 | `test_log_whale_momentum` | **DONE** |

### Phase D: Enhanced CHOP Alpha

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| D-01 | Implement `identify_range()` | `src/engines/nautilus/range_mapper.py` | — | `test_range_detection_obvious_range` | **DONE** |
| D-02 | Implement `detect_micro_reversion()` | `src/engines/nautilus/micro_reversion.py` | D-01 | `test_micro_reversion_at_range_low` | **DONE** |
| D-03 | Implement `detect_chop_correlation_gap()` | `src/engines/nautilus/chop_corr_gap.py` | A-06, D-01 | `test_chop_corr_gap_signal` | **DONE** |
| D-04 | Add `CHOP_CORR_GAP` to `TemplateName` | `src/v25/contracts/signal.py` | — | `test_template_enum` | **DONE** |
| D-05 | Add `CHOP_MICRO_REVERSION` to `TemplateName` | `src/v25/contracts/signal.py` | — | `test_template_enum` | **DONE** |
| D-06 | Wire new sub-strategies into `NautilusEngine` | `src/engines/nautilus/engine.py` | D-02, D-03 | `test_nautilus_dispatches_new_strategies` | **DONE** |
| D-07 | Update CHOP daily trade cap: 4 → 6 | `config/engines.yaml` | — | config load check | **DONE** |

### Phase E: Precision Entry Pipeline

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| E-01 | Implement `assess_entry_precision()` | `src/mde/precision_filter.py` | — | `test_grade_a_good_microstructure` | **DONE** |
| E-02 | Grade thresholds from config | `src/mde/precision_filter.py` | — | `test_grade_from_config` | **DONE** |
| E-03 | Wire precision filter into pipeline | `src/main.py` | E-01 | `test_pipeline_applies_precision` | **DONE** |
| E-04 | Add precision config to `engines.yaml` | `config/engines.yaml` | — | YAML load check | **DONE** |
| E-05 | Log precision entries to DB | `src/v25/telemetry/log_writer.py` | C-05 | `test_log_precision` | **DONE** (Phase C) |

### Phase F: Integration + Backtest Validation

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| F-01 | Backtest Gemini on historical BTC/ETH spread | `tests/integration/test_phase_f_validation.py` | B-04 | `test_gemini_mean_reversion_profitable` | **DONE** |
| F-02 | Backtest enhanced Nautilus on CHOP periods | `tests/integration/test_phase_f_validation.py` | D-06 | `test_bb_reversion_profitable_in_range` | **DONE** |
| F-03 | Stress test: correlation blow-up | `tests/integration/test_phase_f_validation.py` | B-04 | `test_gemini_no_signal_when_correlation_collapses` | **DONE** |
| F-04 | Full pipeline integration test | `tests/integration/test_phase_f_validation.py` | ALL | `test_router_dispatches_to_nautilus_in_ranging` | **DONE** |
| F-05 | Fee drag validation: 20 trades/day | `tests/integration/test_phase_f_validation.py` | E-01 | `test_fee_drag_20_trades_per_day` | **DONE** |

### Phase G: Validated Sizing Protocol (CAI Pivot 1)

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| G-01 | Create `ValidatedSizing` contract | `src/v25/contracts/validated_sizing.py` | — | `test_validated_sizing_contract` | **DONE** |
| G-02 | Implement `compute_validated_size()` | `src/risk/validated_sizer.py` | G-01 | `test_validated_size_basic` | **DONE** |
| G-03 | Verify leverage is DERIVED (never > notional/equity) | `src/risk/validated_sizer.py` | G-02 | `test_leverage_always_derived` | **DONE** |
| G-04 | Implement breakeven-R gate (Gate 9) | `src/mde/gates.py` | G-02 | `test_breakeven_r_rejects_high_fee_trade` | **DONE** |
| G-05 | Fee-adjusted notional: `notional = risk / (sl_pct + fee_pct)` | `src/risk/validated_sizer.py` | G-02 | `test_fee_adjusted_notional` | **DONE** |
| G-06 | Leverage cap enforcement (cap, not multiply) | `src/risk/validated_sizer.py` | G-02 | `test_leverage_capped_at_phase_max` | **DONE** |
| G-07 | Wire validated sizer into pipeline (replace final sizing step) | `src/main.py`, `src/mde/sizing.py` | G-02, G-04 | `test_pipeline_uses_validated_sizer` | **DONE** |
| G-08 | Add `validated_sizing_log` DB table + telemetry | `src/v25/db/migrations.py`, `src/v25/telemetry/log_writer.py` | C-07, C-13 | `test_validated_sizing_logged` | **DONE** |
| G-09 | Convert `leverage_mult` in SizingInput to cap semantics | `src/mde/sizing.py` | G-02 | `test_leverage_mult_is_cap_not_multiplier` | **DONE** |

### Phase H: Dynamic 3-Stage Exit (CAI Pivot 3)

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| H-01 | Create `ExitStage` enum + `DynamicExitState` contract | `src/v25/contracts/exit_strategy.py` | — | `test_exit_stage_enum` | **DONE** |
| H-02 | Implement `DynamicExitManager.__init__()` | `src/execution/dynamic_exit.py` | H-01 | `test_exit_manager_init` | **DONE** |
| H-03 | Implement `on_position_open()` (Stage 0: ENTRY) | `src/execution/dynamic_exit.py` | H-02 | `test_position_starts_at_entry_stage` | **DONE** |
| H-04 | Implement Stage 1: BREAKEVEN_LOCK at +0.5R | `src/execution/dynamic_exit.py` | H-03 | `test_breakeven_lock_at_half_r` | **DONE** |
| H-05 | Implement Stage 2: PROFIT_CAPTURE at +1.5R + ATR trailing | `src/execution/dynamic_exit.py` | H-04 | `test_profit_capture_engages_trailing` | **DONE** |
| H-06 | Implement Stage 3: TREND_RIDER at +3.0R + tightened trailing | `src/execution/dynamic_exit.py` | H-05 | `test_trend_rider_tightens_trail` | **DONE** |
| H-07 | Implement trailing SL (only moves up, never down) | `src/execution/dynamic_exit.py` | H-05 | `test_trailing_never_moves_down` | **DONE** |
| H-08 | Implement regime-conditional stage behavior | `src/execution/dynamic_exit.py` | H-06 | `test_chop_stage1_only` | **DONE** |
| H-09 | CRISIS → immediate market close all | `src/execution/dynamic_exit.py` | H-06 | `test_crisis_closes_all` | **DONE** |
| H-10 | Wire into `executor.py` (partial close support) | `src/execution/executor.py` | H-06 | `test_executor_partial_close` | **DONE** |
| H-11 | Wire trailing SL into `sl_manager.py` (read trailing_sl from dynamic exit state) | `src/execution/sl_manager.py` | H-07 | `test_enforce_uses_trailing_when_dynamic_state_has_trailing` | **DONE** |
| H-12 | Dynamic exit FSM replaces static TP (no tp_manager.py exists — by design) | N/A | H-06 | `test_profit_capture_produces_partial_close_action` | **DONE** |

### Phase I: Whale Momentum SQS Boost (CAI Pivot 4)

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| I-01 | Add `WhaleMomentumSignal` contract | `src/v25/contracts/intelligence.py` | — | `test_whale_momentum_signal_contract` | **DONE** |
| I-02 | Implement `compute_whale_momentum()` | `src/engines/hermes/whale_momentum.py` | I-01 | `test_whale_momentum_bullish_outflow` | **DONE** |
| I-03 | Implement `apply_whale_boost_to_sqs()` | `src/engines/hermes/whale_momentum.py` | I-02 | `test_whale_boost_only_trend_strong` | **DONE** |
| I-04 | Defensive override: base_c5 < 0.30 → zero boost | `src/engines/hermes/whale_momentum.py` | I-03 | `test_defensive_overrides_offensive` | **DONE** |
| I-05 | Stablecoin mint detection ($100M+ threshold) | `src/engines/hermes/whale_momentum.py` | I-02 | `test_stablecoin_mint_signal` | **DONE** |
| I-06 | Wire whale momentum into pipeline (step 6.6) | `src/main.py` | I-03 | `test_hermes_bidirectional` | **DONE** |
| I-07 | Add `whale_momentum_log` DB table + telemetry | `src/v25/db/migrations.py`, `src/v25/telemetry/log_writer.py` | C-08, C-14 | `test_whale_momentum_logged` | **DONE** |
| I-08 | Max boost cap: +0.10 to C5, never exceed 1.0 | `src/engines/hermes/whale_momentum.py` | I-03 | `test_boost_cap_1_0` | **DONE** |

### Phase J: Hyper-Precision 1m/3m Execution (CAI Pivot 5)

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| J-01 | Implement `snipe_entry()` (1m OBI + VWAP limit) | `src/execution/hyper_precision.py` | — | `test_snipe_entry_limit_order` | **DONE** |
| J-02 | Implement entry timeout + market fallback | `src/execution/hyper_precision.py` | J-01 | `test_entry_timeout_fallback` | **DONE** |
| J-03 | Implement `snipe_partial_exit()` (OBI reversal) | `src/execution/hyper_precision.py` | J-01 | `test_partial_exit_snipe` | **DONE** |
| J-04 | Implement `compute_trailing_sl()` (3m ATR) | `src/execution/hyper_precision.py` | J-01 | `test_trailing_sl_3m_atr` | **DONE** |
| J-05 | Wire hyper-precision into executor pipeline | `src/execution/executor.py` | J-01..J-04 | `test_executor_uses_hyper_precision` | **DONE** |
| J-06 | Wire into position manager (live dynamic exit) | `src/execution/hermes_position_manager.py` | J-04 | `test_live_exit` | **DONE** |
| J-07 | Signal GENERATION stays on 5m+ (no 1m/3m signals) | `src/execution/hyper_precision.py` | — | `test_no_signal_on_low_tf` | **DONE** (by design) |

### Phase K: CAI Integration + End-to-End Validation

| ID | Task | File(s) | Depends On | Test | Status |
|----|------|---------|-----------|------|--------|
| K-01 | E2E: validated sizing → dynamic exit → hyper-precision flow | `tests/integration/test_e2e_cai_pivots.py` | G-07, H-10, J-05 | `test_full_cai_flow` | **DONE** |
| K-02 | E2E: dynamic exit progression (LONG + SHORT) | `tests/integration/test_e2e_cai_pivots.py` | H-06 | `test_dynamic_exit_progression` | **DONE** |
| K-03 | E2E: shadow intent emission | `tests/integration/test_e2e_cai_pivots.py` | H-06 | `test_shadow_intent_emission` | **DONE** |
| K-04 | E2E: whale boost in TRENDING, blocked in RANGING | `tests/integration/test_e2e_cai_pivots.py` | I-06 | `test_whale_boost_e2e` | **DONE** |
| K-05 | Verify: breakeven-R rejects micro-stop trades correctly | `tests/risk/test_breakeven_gate.py` | G-04 | `test_micro_stop_rejected` | **DONE** |

---

## 4) CONTEXT ANCHORS — Quick Reference Card

Print this section at the start of every coding session.

```
┌─────────────────────────────────────────────────────────────┐
│                 ARGUS CONTEXT ANCHORS v2.0                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  BASE CLASS:  ArgusModel (frozen, strict, extra=forbid)      │
│  FEE MODEL:   FeeModel from src/v25/contracts/fee.py         │
│  REGIME ENUM: RegimeType in src/v25/contracts/signal.py      │
│  ENGINES:     Titan|Nautilus|Phoenix|Hermes|Hydra|Gemini      │
│  ENGINE PROTO: AbstractEngine in src/engines/base.py         │
│  KILL SWITCH: 5 levels (0=NORMAL to 4=LOCKDOWN)              │
│  CIRCUIT BRK:  1.5% → 3% → 4% → 8% DD thresholds           │
│  DB PATH:     data/trade_logs/argus.db (SQLite WAL)          │
│  DB TABLES:   21 total (13 original + 8 added)               │
│  CONFIG:      config/{base,risk,engines,regimes,telemetry}   │
│  ENTRY POINT: src/main.py :: ArgusPipeline                   │
│  BACKTEST:    src/backtest/engine.py :: BacktestEngine        │
│  SIZING:      src/risk/validated_sizer.py (CANONICAL)         │
│                                                               │
│  GOLDEN RULES:                                                │
│  1.  Protection > Profit                                      │
│  2.  Fee-inclusive everything (backtest_cost_mult=2.0)         │
│  3.  Hermes check before every trade (SQS.C5)                │
│  4.  Correlation veto > risk tolerance (max_corr=0.6)         │
│  5.  Tests before merge                                       │
│  6.  Contracts are sacred (frozen, Decimal, no NaN)           │
│  7.  Deterministic reproducibility (seeded)                   │
│  8.  Exchange-side SL mandatory                               │
│  9.  Event shield before FOMC/CPI/NFP                        │
│  10. Extend only, never refactor stable modules               │
│  11. Leverage is DERIVED (notional/equity), never an input    │
│  12. Breakeven-R gate: fees > 30% of risk → REJECT trade     │
│  13. Dynamic exit replaces static TP (3-stage partials)       │
│  14. Defensive Hermes always beats offensive whale boost      │
│                                                               │
│  CAI PIVOT MODULES (NEW):                                     │
│  src/risk/validated_sizer.py       — canonical sizing (P1)    │
│  src/v25/contracts/validated_sizing.py — sizing contract (P1) │
│  src/v25/contracts/exit_strategy.py — exit FSM contract (P3)  │
│  src/execution/dynamic_exit.py     — 3-stage TP + trail (P3)  │
│  src/engines/hermes/whale_momentum.py — SQS boost (P4)       │
│  src/execution/hyper_precision.py  — 1m/3m execution (P5)     │
│                                                               │
│  CORRELATION MODULES (v1.0):                                  │
│  src/correlation/tracker.py     — correlation computation     │
│  src/correlation/signals.py     — spread → trading signal     │
│  src/correlation/ou_estimator.py — mean-reversion speed      │
│  src/engines/gemini/engine.py   — pairs trading engine        │
│                                                               │
│  CHOP ALPHA MODULES (v1.0):                                   │
│  src/engines/nautilus/chop_corr_gap.py — CHOP corr alpha     │
│  src/engines/nautilus/micro_reversion.py — CHOP micro MR     │
│  src/engines/nautilus/range_mapper.py — range detection       │
│  src/mde/precision_filter.py    — entry quality grading       │
│  src/v25/contracts/correlation.py — new Pydantic contracts    │
│                                                               │
│  KEY FORMULA (memorize):                                      │
│  notional = risk_usd / (sl_pct + fee_round_trip_pct)         │
│  leverage = notional / equity  (OUTPUT, never INPUT)          │
│  breakeven_r = fee_cost / risk_usd  (must be < 0.30)         │
│                                                               │
│  VERIFY: python -m pytest tests/ -x --tb=short               │
│  TYPES:  python -m mypy src/ --ignore-missing-imports         │
└─────────────────────────────────────────────────────────────┘
```

---

## 5) IMPLEMENTATION PRIORITY ORDER

```
WEEK 1:  Phase A (A-01 through A-11)  — Correlation foundations
WEEK 2:  Phase C (C-01 through C-14)  — DB schema + telemetry (all 21 tables)
WEEK 3:  Phase G (G-01 through G-09)  — Validated Sizing Protocol (CAI Pivot 1)
         ↑ CRITICAL: This changes the sizing pipeline. Must land before H/J.
WEEK 4:  Phase B (B-01 through B-07)  — Gemini engine
WEEK 5:  Phase D (D-01 through D-07)  — Enhanced CHOP
WEEK 6:  Phase H (H-01 through H-12)  — Dynamic 3-Stage Exit (CAI Pivot 3)
WEEK 7:  Phase I (I-01 through I-08)  — Whale Momentum SQS Boost (CAI Pivot 4)
WEEK 8:  Phase E (E-01 through E-05)  — Precision entries
WEEK 9:  Phase J (J-01 through J-09)  — Hyper-Precision 1m/3m (CAI Pivot 5)
         ↑ Depends on H (dynamic exit) and G (validated sizing)
WEEK 10: Phase F (F-01 through F-05)  — Integration + backtest validation (v1.0)
WEEK 11: Phase K (K-01 through K-05)  — CAI pivot integration + E2E validation
```

Rationale:
- Foundations first (A), then ALL infrastructure (C, expanded for 21 tables).
- **Validated Sizing (G) moves to Week 3** — it changes the core sizing pipeline and is a dependency for Dynamic Exit (H) and Hyper-Precision (J).
- Gemini (B) and CHOP (D) are independent feature tracks.
- Dynamic Exit (H) before Whale Momentum (I) because H changes execution flow.
- Hyper-Precision (J) last among features — depends on both G and H.
- Two validation phases: F (v1.0 features) and K (CAI pivots).

---

## 6) RISK REGISTER — Hyper-Aggressive Yield Targets

### 6.1 — Honest Assessment

| Target | Achievable? | Conditions | Danger |
|--------|:-----------:|-----------|--------|
| 5%/day | Possible on TREND days | ADX>30, multi-asset, 15+ trades, leverage 2-3x | Requires perfect execution; fee drag is real |
| 10%/day | Rare | Exceptional trend + all engines firing + no drawdown | Statistically ~2-3 days/month maximum |
| 5%/day average | Unlikely | Would require trend market every day | CHOP/VOLATILE days yield 0-2% |
| 2-3%/day average | Realistic stretch | Mixed regime, disciplined execution | Still requires strong edge maintenance |

### 6.2 — Guardrails Against Ruin

```
HARD LIMITS (non-negotiable):
  - Daily loss cap: 3% (unchanged from config/risk.yaml)
  - Max leverage: 3x (from config/risk.yaml global_caps)
  - Kill switch level 3 (DD > 4%): EXIT ONLY
  - Kill switch level 4 (DD > 8%): LOCKDOWN
  - Correlation limit: 0.6 max portfolio correlation
  - Per-trade risk cap: 3% (from risk.yaml per_trade_risk_cap)
  
ANTI-OVERTRADING:
  - Max 15 trades/day (from pre_trade.py max_trades_per_day)
  - CHOP max 6/day (after enhancement)
  - Hydra (scalp) uses LIMIT only → natural speed limit
  - 2 consecutive losses → 60min cooldown
  - 3 consecutive losses → EOD halt

CAI PIVOT GUARDRAILS (v2.0):
  - Breakeven-R gate: fees > 30% of risk → trade REJECTED (GR-12)
  - Leverage is DERIVED: notional/equity, NEVER an input (GR-11)
  - Max fee drag at 25 trades/day (mostly maker): ~1.0%
  - Dynamic exit: CRISIS regime → immediate market close ALL
  - Whale boost ONLY in TREND_STRONG (GR-14)
  - Defensive Hermes veto overrides whale boost in ALL regimes
  - Hyper-precision 1m/3m for EXECUTION only, never signal generation
```

---

## 7) DEPENDENCY RESOLUTION ORDER

When implementing, resolve imports in this order:

```
Layer 0 (no internal deps — contracts only):
  src/v25/contracts/correlation.py       ← only depends on src/v25/contracts/base.py
  src/v25/contracts/validated_sizing.py   ← only depends on src/v25/contracts/base.py (Pivot 1)
  src/v25/contracts/exit_strategy.py      ← only depends on src/v25/contracts/base.py (Pivot 3)
  src/correlation/ou_estimator.py         ← only depends on pandas, numpy

Layer 1 (depends on Layer 0 — core logic):
  src/correlation/tracker.py             ← depends on contracts/correlation.py
  src/correlation/signals.py             ← depends on contracts/correlation.py + signal.py
  src/risk/validated_sizer.py            ← depends on contracts/validated_sizing.py + fee.py (Pivot 1)

Layer 2 (depends on Layer 1 — engines + features):
  src/engines/gemini/engine.py           ← depends on correlation/tracker.py + signals.py
  src/engines/nautilus/range_mapper.py   ← standalone (pandas only)
  src/engines/nautilus/micro_reversion.py ← depends on range_mapper.py
  src/engines/nautilus/chop_corr_gap.py   ← depends on correlation/tracker.py
  src/engines/hermes/whale_momentum.py    ← depends on contracts/intelligence.py (Pivot 4)

Layer 3 (depends on Layer 2 — execution + precision):
  src/mde/precision_filter.py            ← depends on core/types.py + contracts/fee.py
  src/mde/gates.py (MODIFY)              ← add Gate 9: breakeven-R (Pivot 1)
  src/mde/router.py (MODIFY)             ← add Gemini routing
  src/execution/dynamic_exit.py          ← depends on contracts/exit_strategy.py (Pivot 3)

Layer 4 (depends on Layer 3 — integration):
  src/execution/hyper_precision.py       ← depends on dynamic_exit.py + core/types.py (Pivot 5)
  src/engines/hermes/engine.py (MODIFY)  ← wire whale_momentum into pipeline (Pivot 4)
  src/execution/executor.py (MODIFY)     ← support partial close + hyper-precision

Layer 5 (infrastructure — can be done in parallel with Layer 1+):
  src/v25/db/migrations.py (MODIFY)      ← add 8 new tables (14-21)
  src/v25/telemetry/log_writer.py (MODIFY) ← add 5 new log functions
  src/main.py (MODIFY)                   ← wire validated sizer + precision filter
  config/base.yaml (MODIFY)              ← add execution_entry/execution_trailing TFs
  config/engines.yaml (MODIFY)           ← add gemini + hyper_precision sections
```

---

## 8) FILE MODIFICATION LIMITS

To prevent scope creep, here are the exact existing files that may be modified and the maximum change size:

| File | Max Lines Changed | What to Change |
|------|:-----------------:|---------------|
| `src/v25/contracts/signal.py` | 6 lines | Add 4 new `TemplateName` enum members |
| `src/v25/contracts/intelligence.py` | 20 lines | Add `WhaleMomentumSignal` contract (Pivot 4) |
| `src/v25/db/migrations.py` | 120 lines | Append 8 new table DDLs + 14 indexes to tuples |
| `src/v25/telemetry/log_writer.py` | 60 lines | Add 5 new log functions (corr, precision, exit, sizing, whale) |
| `src/mde/router.py` | 15 lines | Register Gemini engine in routing table |
| `src/mde/gates.py` | 15 lines | Add Gate 9: breakeven-R check (Pivot 1) |
| `src/mde/sizing.py` | 10 lines | Convert `leverage_mult` to cap semantics (Pivot 1) |
| `src/engines/nautilus/engine.py` | 20 lines | Add dispatch to new sub-strategies |
| `src/engines/hermes/engine.py` | 25 lines | Wire whale_momentum into pipeline (Pivot 4) |
| `src/execution/executor.py` | 30 lines | Support partial close + hyper-precision (Pivots 3,5) |
| `src/exit/stop_manager.py` | 10 lines | Read trailing_sl from DynamicExitState (Pivot 3) |
| `src/exit/tp_manager.py` | 15 lines | Replace static TP with stage-based partials (Pivot 3) |
| `src/main.py` | 15 lines | Wire validated sizer + precision filter into pipeline |
| `config/base.yaml` | 4 lines | Add `execution_entry: "1m"` and `execution_trailing: "3m"` |
| `config/engines.yaml` | 60 lines | Add gemini + precision + hyper_precision sections |

**Total existing-file modifications: ~425 lines across 15 files.**  
**Total new files: ~18 files (12 v1.0 + 6 CAI pivot modules).**

New files created by CAI pivots:
| New File | Pivot | Purpose |
|----------|:-----:|---------|
| `src/v25/contracts/validated_sizing.py` | P1 | ValidatedSizing Pydantic contract |
| `src/risk/validated_sizer.py` | P1 | Canonical sizing function (notional = risk/sl_pct) |
| `src/v25/contracts/exit_strategy.py` | P3 | ExitStage enum + DynamicExitState contract |
| `src/execution/dynamic_exit.py` | P3 | 3-stage partial TP + ATR trailing FSM |
| `src/engines/hermes/whale_momentum.py` | P4 | Whale flow → SQS boost logic |
| `src/execution/hyper_precision.py` | P5 | 1m/3m entry sniping + trailing updates |

---

## 9) SESSION START PROTOCOL

At the beginning of every coding session, execute:

```bash
# 1. Verify codebase health
cd E:\argus\argus-terminal
python -m pytest tests/ -x --tb=short -q

# 2. Verify imports
python -c "from src.core.types import FeatureVector; from src.v25.contracts.signal import SQSScore; print('OK')"

# 3. Verify DB
python -c "from src.v25.db.migrations import run_v25_migrations; c=run_v25_migrations(':memory:'); print(f'{len(c.execute(\"SELECT name FROM sqlite_master WHERE type=\\\"table\\\"\").fetchall())} tables OK')"

# 4. Check which phase to work on
# Read this document, find first PENDING task, mark IN_PROGRESS
```

---

## 10) GLOSSARY — Term Definitions

| Term | Definition | Where Used |
|------|-----------|-----------|
| SQS | Signal Quality Score (5 components, 0-1) | `src/v25/contracts/signal.py` |
| ChopEdgeScore | CHOP-specific quality (5 components, 0-1) | `src/v25/contracts/signal.py` |
| R-Multiple | Trade profit as multiple of risk (1R = risked amount) | All engines |
| OBI | Orderbook Imbalance (buy-side vs sell-side pressure) | `FeatureVector.orderbook_imbalance` |
| DD | Drawdown (peak-to-trough equity decline) | `src/risk/kill_switch.py` |
| Circuit Breaker | Kill switch levels 0-4 based on DD | `config/risk.yaml` |
| Hermes | Intelligence/sentiment subsystem (now bidirectional) | `src/engines/hermes/` |
| Atlas | Risk overlay multiplier (macro conditions) | `src/engines/atlas/` |
| Darwin | Genetic algorithm for parameter evolution | `src/learning/darwin.py` |
| Reflector | Post-trade failure analysis + shadow simulation | `src/learning/reflector.py` |
| Gemini | Correlation-based pairs trading engine | `src/engines/gemini/` |
| OU | Ornstein-Uhlenbeck process (mean-reversion model) | `src/correlation/ou_estimator.py` |
| Half-life | Bars for spread to mean-revert 50% | `src/correlation/ou_estimator.py` |
| Spread Z-Score | How many std deviations spread is from mean | `CorrelationPair.spread_zscore` |
| Validated Sizing | Canonical sizing where leverage = notional/equity (DERIVED) | `src/risk/validated_sizer.py` |
| Breakeven-R | Fee cost as fraction of risk_usd; must be < 0.30 | `src/risk/validated_sizer.py`, Gate 9 |
| Dynamic Exit | 3-stage partial TP FSM (ENTRY→BREAKEVEN→PROFIT→RIDER) | `src/execution/dynamic_exit.py` |
| ExitStage | Enum: ENTRY, BREAKEVEN_LOCK, PROFIT_CAPTURE, TREND_RIDER, CLOSED | `src/v25/contracts/exit_strategy.py` |
| ATR Trailing | Trailing stop = price - (ATR_14 × multiplier), only moves up | `src/execution/dynamic_exit.py` |
| Whale Momentum | Aggregated whale flow direction (+outflow = bullish) | `src/engines/hermes/whale_momentum.py` |
| SQS Boost | Whale momentum +0.05/+0.10 to C5 in TREND_STRONG only | `src/engines/hermes/whale_momentum.py` |
| Hyper-Precision | 1m/3m execution layer for entry sniping + trailing | `src/execution/hyper_precision.py` |
| Entry Sniper | 1m OBI + VWAP limit order for optimal entry | `src/execution/hyper_precision.py` |
| Defensive Override | Hermes negative sentiment always beats whale boost | GR-14 |

---

**End of Project State & Memory Map v2.0**
