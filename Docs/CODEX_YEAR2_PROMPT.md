# ARGUS v2.0 — Codex Implementation Prompt

**Purpose:** This prompt gives a Codex-class agent everything needed to implement the ARGUS v2.0 system from scratch, building the `src/` directory tree alongside the existing `argus_py/` codebase.

**Required reading before implementation:** `Docs/CONSTITUTION_V2.md` (the single source of truth).

---

## Context

You are implementing ARGUS v2.0, a multi-regime algorithmic crypto trading system. The project lives at `/argus-terminal/`. There is an existing `argus_py/` directory with v1.0 code (155 Python files, 47 test files). **Do NOT modify `argus_py/`.** Build v2.0 in a new `src/` directory.

### Architecture Summary

- **3 engines:** TITAN (trend), NAUTILUS (mean-rev), PHOENIX (carry/basis)
- **2 overlays:** ATLAS (risk governor), SENTINEL (data quality)
- **4 regime states:** TRENDING, RANGING, VOLATILE, CRISIS
- **Decision style:** Regime-based ROUTING (not voting). One engine leads per regime.
- **Sizing:** Fixed fractional, 2% base risk (NOT Kelly)
- **Kill switch:** 5 levels (NORMAL → CAUTION → DEFENSIVE → HALT → LOCKDOWN)
- **Exchange SL:** MANDATORY on every position
- **Priority:** Capital Safety > Robustness > Scale > Profit

### Technical Stack

- Python 3.11+
- pydantic v2 (frozen=True, strict=True for all models)
- asyncio for concurrency
- ccxt for exchange communication
- pandas/numpy for feature computation
- LightGBM for ML classification (Phase 4)
- PyTorch for Chronos-Bolt inference (Phase 4, research node only)
- SQLite for trade/decision logging
- Parquet for OHLCV storage
- YAML for all configuration

---

## Implementation Phases

Execute these phases IN ORDER. Each phase has explicit acceptance criteria. Do not start the next phase until the current phase's tests pass.

---

### Phase 1: Core Foundation

**Goal:** Create the shared kernel that all other modules depend on.

**Files to create:**

```
src/__init__.py
src/core/__init__.py
src/core/types.py          # All pydantic v2 frozen models
src/core/config.py          # YAML loader with typed config objects
src/core/events.py          # EventBus pub/sub with 17 event types
src/core/clock.py           # Unified clock (real or simulated)
src/core/exceptions.py      # DataStale, SentinelHalt, KillSwitchActive, etc.
src/core/constants.py       # Named constants (no magic numbers)
config/base.yaml
config/regimes.yaml
config/engines.yaml
config/risk.yaml
config/telemetry.yaml
tests/unit/test_types.py
```

**Implementation details:**

`src/core/types.py`:
- Implement ALL models from Constitution Section 5.1: FeatureVector (50 fields), RegimeState, EngineSignal, Decision, RiskVerdict, ExecutionResult, Position, PortfolioState, TradeRecord
- Base class `ArgusModel(BaseModel)` with `ConfigDict(frozen=True, strict=True, extra="forbid")`
- All float fields that are bounded must use `Field(ge=..., le=...)`
- NaN validator: add a model_validator that rejects any float field that is NaN (for non-Optional fields)

`src/core/config.py`:
- Load YAML from `config/` directory
- Merge: base.yaml + mode-specific yaml (paper.yaml / production.yaml / backtest.yaml)
- Environment variable overlay (ARGUS_MODE, ARGUS_LOG_LEVEL, etc.)
- Return typed dataclass objects, not raw dicts

`src/core/events.py`:
- EventBus class with subscribe(event_type, callback) and publish(event_type, data)
- 17 event types as defined in Constitution Section 9.2
- All published events are logged to SQLite via telemetry

**Config files:**
- Copy YAML structures exactly from Constitution Sections 10.1-10.5
- All values must match the Constitution's mathematical foundations (Section 13)

**Acceptance criteria:**
```bash
pytest tests/unit/test_types.py -v  # All type validations pass
# Test: frozen immutability, field bounds, NaN rejection, Optional fields
# Test: FeatureVector with all 50 fields
# Test: Decision with invalid leverage (>3.0) → ValidationError
```

---

### Phase 2: Data Layer (SENTINEL + Features)

**Goal:** Stream data, validate quality, compute 50 features.

**Files to create:**

```
src/data/__init__.py
src/data/ingest/__init__.py
src/data/ingest/binance_ws.py
src/data/ingest/binance_rest.py
src/data/ingest/bybit_rest.py
src/data/ingest/coingecko.py
src/data/ingest/fear_greed.py
src/data/sentinel/__init__.py
src/data/sentinel/validator.py
src/data/sentinel/anomaly.py
src/data/features/__init__.py
src/data/features/technical.py
src/data/features/volume.py
src/data/features/microstructure.py
src/data/features/crypto_native.py
src/data/features/cross_asset.py
src/data/features/statistical.py
src/data/features/ml_features.py    # Stub — returns None for all ML features
src/data/store/__init__.py
src/data/store/parquet_store.py
src/data/store/sqlite_store.py
src/data/snapshot.py
tests/unit/test_sentinel.py
tests/unit/test_features.py
```

**Implementation details:**

`src/data/sentinel/validator.py`:
- 6 checks from Constitution Section 6, Step 2
- Returns `data_quality_score: float` (0.0-1.0)
- Thresholds: >= 0.7 proceed, 0.4-0.7 reduce confidence, < 0.4 HALT, < 0.2 EMERGENCY

`src/data/features/technical.py`:
- Volatility (6): atr_14, atr_14_pct, atr_ratio_5_20, realized_vol_20d, parkinson_vol, bb_width
- Trend (6): adx_14, price_vs_ma200, ema_21_vs_55, lr_slope_20, supertrend_dir, aroon_osc
- Momentum (5): rsi_14, bb_pct_b, roc_10, willr_14, cci_20
- Use pandas-ta or ta-lib. Avoid computing from scratch unless necessary.

`src/data/snapshot.py`:
- Assembles MarketSnapshot from all feature sources
- Snapshot is FROZEN once created — no mutation
- Total computation must complete within 2000ms

**NaN Policy:** From Constitution Section 5.2. Tier 1 NaN → halt pipeline. Tier 2 → set None, reduce sentinel score. Tier 3 → set None.

**Acceptance criteria:**
```bash
pytest tests/unit/test_sentinel.py -v   # All 6 checks tested
pytest tests/unit/test_features.py -v   # Golden tests: known OHLCV → known feature values
# Verify: No NaN propagates past snapshot builder
# Verify: Feature computation < 2000ms on 2 years of 1h data
```

---

### Phase 3: Regime Detection

**Goal:** Classify market into 4 states with consensus and state machine.

**Files to create:**

```
src/regime/__init__.py
src/regime/rule_based.py
src/regime/volatility_classifier.py
src/regime/microstructure_cls.py
src/regime/consensus.py
src/regime/state_machine.py
tests/unit/test_regime.py
tests/unit/test_state_machine.py
```

**Implementation details:**

`src/regime/rule_based.py`:
- CRISIS: instant (any 1 trigger: price drop >8%/24h, vol >3x 60d, liquidation cascade, depth <30%)
- VOLATILE: ATR(5)/ATR(20) > 1.8 OR vol > 2x 60d median
- TRENDING: ADX > 25 AND directional alignment
- RANGING: ADX < 20 AND Hurst < 0.45
- Ambiguous default: RANGING (conservative)

`src/regime/state_machine.py`:
- Implement all transition rules from Constitution Section 7.2
- Confirmation windows: CRISIS entry = 0 candles, TRENDING↔RANGING = 3, to VOLATILE = 2, CRISIS exit = 12
- Hysteresis: min 6 candles before TRENDING↔RANGING transition
- CRISIS can ONLY exit to VOLATILE (no direct to TRENDING/RANGING)
- Gradual recovery: Phase 1 (CRISIS) → Phase 2 (VOLATILE, 25% size) → Phase 3 (normal, gradual size increase)

`src/regime/consensus.py`:
- 3-of-4 agreement for TRENDING/RANGING
- Any 1 sufficient for VOLATILE/CRISIS (safety bias)

**Acceptance criteria:**
```bash
pytest tests/unit/test_regime.py -v          # Classification accuracy
pytest tests/unit/test_state_machine.py -v   # All transitions tested
# Test: CRISIS detection is instant (0 confirmation)
# Test: CRISIS→TRENDING is BLOCKED (must go through VOLATILE)
# Test: Rapid ADX oscillation around 25 → max 2 transitions in 48h
# Test: 2020-style crash data → CRISIS detected within 1 candle
```

---

### Phase 4: Engine Portfolio

**Goal:** Implement 3 engines + ATLAS overlay.

**Files to create:**

```
src/engines/__init__.py
src/engines/base.py
src/engines/titan/__init__.py
src/engines/titan/engine.py
src/engines/titan/trend_follow.py
src/engines/titan/breakout.py
src/engines/nautilus/__init__.py
src/engines/nautilus/engine.py
src/engines/nautilus/bb_reversion.py
src/engines/nautilus/funding_reversion.py
src/engines/phoenix/__init__.py
src/engines/phoenix/engine.py
src/engines/phoenix/funding_harvest.py
src/engines/phoenix/basis_trade.py
src/engines/atlas/__init__.py
src/engines/atlas/risk_overlay.py
tests/unit/test_titan.py
tests/unit/test_nautilus.py
tests/unit/test_phoenix.py
tests/unit/test_atlas.py
```

**Implementation details:**

`src/engines/base.py`:
```python
from typing import Protocol, Optional
class AbstractEngine(Protocol):
    def generate_signal(self, snapshot: MarketSnapshot, regime: RegimeState, features: FeatureVector) -> Optional[EngineSignal]: ...
```

Engine rules:
- TITAN: ONLY fires when `regime.regime == "TRENDING"` AND `features.adx_14 >= 25`
- NAUTILUS: ONLY fires when `regime.regime == "RANGING"` AND `features.adx_14 <= 22`
- PHOENIX: Fires in TRENDING, RANGING, VOLATILE. NOT in CRISIS.
- Each engine returns `None` (not a neutral signal) when inactive.
- Each engine picks the strongest sub-strategy signal internally.
- MIN_CONFIDENCE = 0.55 for all engines.

ATLAS overlay:
- Input: BTC dominance, total mcap momentum, stablecoin flows
- Output: `risk_multiplier` in [0.0, 1.5]
- RISK_ON: 1.0-1.5, RISK_NEUTRAL: 0.7-1.0, RISK_OFF: 0.2-0.5, CRISIS: 0.0

Stop loss multipliers from Constitution Section 13.2.

**Acceptance criteria:**
```bash
pytest tests/unit/test_titan.py -v      # Signals in TRENDING, silence in RANGING
pytest tests/unit/test_nautilus.py -v    # Signals in RANGING, silence in TRENDING
pytest tests/unit/test_phoenix.py -v    # Signals in all non-CRISIS
pytest tests/unit/test_atlas.py -v      # Multiplier in [0.0, 1.5]
```

---

### Phase 5: MDE + Risk Layer

**Goal:** Routing engine, 7 gates, fixed fractional sizing, 5-level kill switch.

**Files to create:**

```
src/mde/__init__.py
src/mde/router.py
src/mde/gates.py
src/mde/sizing.py
src/risk/__init__.py
src/risk/rsl.py
src/risk/pre_trade.py
src/risk/drawdown.py
src/risk/kill_switch.py
src/risk/cooldown.py
tests/unit/test_mde.py
tests/unit/test_sizing.py
tests/unit/test_rsl.py
tests/unit/test_kill_switch.py
tests/unit/test_pre_trade.py
```

**Implementation details:**

`src/mde/router.py`:
- Regime → lead engine: TRENDING→TITAN, RANGING→NAUTILUS, VOLATILE→PHOENIX, CRISIS→None
- CRISIS: close_all if positions, hold otherwise
- PHOENIX fallback: if lead engine returns None, try PHOENIX

`src/mde/gates.py`:
- 7 sequential gates from Constitution Section 6, Step 6
- Every gate rejection is logged with reason

`src/mde/sizing.py`:
- Fixed fractional formula from Constitution Section 13.1
- All multipliers, clamps, and bounds as specified

`src/risk/kill_switch.py`:
- 5-level FSM from Constitution Section 8
- Escalation is automatic and immediate
- De-escalation requires sustained improvement (time gates)
- Level 3+ requires manual restart
- State persists in SQLite (survives restart)

`src/risk/pre_trade.py`:
- 8 checks from Constitution Section 6, Step 7

**Acceptance criteria:**
```bash
pytest tests/unit/test_mde.py -v           # All 7 gates, routing logic
pytest tests/unit/test_sizing.py -v        # Sizing math, clamps, edge cases
pytest tests/unit/test_rsl.py -v           # All 5 levels, transitions
pytest tests/unit/test_kill_switch.py -v   # Persistence, manual restart
pytest tests/unit/test_pre_trade.py -v     # All 8 checks
```

---

### Phase 6: Execution

**Goal:** Order placement with mandatory exchange-side SL.

**Files to create:**

```
src/execution/__init__.py
src/execution/executor.py
src/execution/order_router.py
src/execution/sl_manager.py
src/execution/reconciler.py
tests/unit/test_sl_manager.py
tests/integration/test_execution.py
```

**Implementation details:**

- 4 urgency levels (EMERGENCY, HIGH, NORMAL, LOW) from Constitution Section 6, Step 8
- SL manager: place exchange-side SL immediately on fill. Verify confirmation. If SL fails → close position immediately + alert.
- Reconciler: compare local state vs exchange state. Flag discrepancies.
- All execution uses ccxt (unified exchange interface)

**Acceptance criteria:**
```bash
pytest tests/unit/test_sl_manager.py -v       # SL placement, failure handling
pytest tests/integration/test_execution.py -v  # Full order lifecycle (mock exchange)
# Test: SL failure → position closed immediately
# Test: Fill reconciliation detects discrepancy
```

---

### Phase 7: Telemetry

**Goal:** Log every event, every decision, every rejection.

**Files to create:**

```
src/telemetry/__init__.py
src/telemetry/trade_logger.py
src/telemetry/event_logger.py
src/telemetry/attribution.py
src/telemetry/drift_detector.py
src/telemetry/decay_detector.py
tests/integration/test_telemetry.py
```

**Implementation details:**

- Event schemas from Constitution Section 9.2 (21 event types)
- All events stored in SQLite
- Rejection logging: every rejected signal/decision with full context
- TradeRecord created on position close with all fields from Constitution Section 5.1

**Acceptance criteria:**
```bash
pytest tests/integration/test_telemetry.py -v
# Test: Pipeline run → all expected events logged
# Test: Rejection includes features_snapshot and gate_that_rejected
# Test: TradeRecord has all required fields
```

---

### Phase 8: Main Pipeline + Integration

**Goal:** Wire everything together into the 10-step pipeline.

**Files to create:**

```
src/main.py
src/ops/__init__.py
src/ops/supervisor.py
src/ops/health.py
src/ops/alerts.py
src/interface/__init__.py
src/interface/telegram_bot.py
tests/integration/test_pipeline.py
tests/stress/test_crash_scenario.py
tests/stress/test_regime_flapping.py
tests/stress/test_nan_propagation.py
```

**Implementation details:**

`src/main.py`:
- Entry point with argparse: `--mode paper|live|backtest`
- Implements the 10-step pipeline from Constitution Section 6
- Each step has latency tracking
- Circuit breaker: if any step exceeds 2x latency budget, emit alert

**Acceptance criteria:**
```bash
pytest tests/integration/test_pipeline.py -v       # Full pipeline with mock data
pytest tests/stress/test_crash_scenario.py -v       # 15% drop → CRISIS → close all
pytest tests/stress/test_regime_flapping.py -v      # ADX oscillation → stable regime
pytest tests/stress/test_nan_propagation.py -v      # NaN injected → caught at Layer 0
# Verify: Total pipeline latency < 10s
# Verify: All telemetry events emitted
```

---

## Rules for the Implementing Agent

1. **Read CONSTITUTION_V2.md first.** Every answer is in there.
2. **Do NOT modify `argus_py/`.** Build everything in `src/`.
3. **All models use pydantic v2** with `frozen=True, strict=True`.
4. **No magic numbers.** Everything comes from config YAML.
5. **No NaN propagation.** Validate at every boundary.
6. **Every decision is logged.** No exceptions.
7. **Tests first, then implementation.** Or at minimum, tests alongside.
8. **Run `pytest` after each phase.** Do not proceed if tests fail.
9. **Config values from Constitution Section 13** (mathematical foundations).
10. **Priority: Capital Safety > Robustness > Scale > Profit.**

---

## Verification Checklist (Run After All Phases)

```bash
# Full test suite
pytest tests/ -v --tb=short

# Type checking
mypy src/ --strict

# Lint
ruff check src/

# Integration: full pipeline with mock data
pytest tests/integration/test_pipeline.py -v

# Stress: crash scenario
pytest tests/stress/test_crash_scenario.py -v

# Verify: no imports from argus_py in src/
grep -r "from argus_py" src/ && echo "FAIL: src/ must not import argus_py" || echo "PASS"

# Verify: all config values match Constitution
python -c "from src.core.config import load_config; c = load_config('paper'); assert c.risk.sizing.base_risk_pct == 0.02"
```
