# ARGUS v2.5 — PLAN REVISION PATCH 002

**Date:** 2026-02-13  
**Applies to:** Implementation Plan (implementation_plan.md) + REVISION_PATCH_001 acceptance tests  
**Status:** MANDATORY — apply before Package 0 coding begins

---

## A) PLAN PATCHES

---

### PATCH 1: Prevent "Two Sources of Truth" Drift

**Problem:** With `src/v25/` and `src/` coexisting, config loading, fee calculations, and migrations could get duplicated.

#### ADD new section to Implementation Plan after "Module Layout":

```
## Drift Prevention Guardrails

RULE-DRIFT-1: SINGLE OWNER PER CONCERN
  The following concerns are owned EXCLUSIVELY by src/v25/.
  No other module may re-implement them.
  
  | Concern              | Owner Module               | Legacy src/ equivalent   | Action on legacy         |
  |----------------------|----------------------------|--------------------------|--------------------------|
  | Fee/slippage model   | src/v25/contracts/fee.py   | (none existed)           | N/A — new capability     |
  | Global risk caps     | src/v25/risk/caps.py       | src/risk/sizing.py       | Legacy reads v25 caps    |
  | Config validation    | src/v25/config/loader.py   | src/core/config.py       | Legacy calls v25 loader  |
  | SQLite v25 schemas   | src/v25/db/migrations.py   | (none existed)           | N/A — new tables only    |
  | Accel gate eval      | src/v25/risk/accel_gates.py| (none existed)           | N/A — new capability     |
  | Stop resize logic    | src/v25/risk/stop_resize.py| (none existed)           | N/A — new capability     |

RULE-DRIFT-2: LEGACY READS, NEVER FORKS
  When existing src/ code needs v2.5 data (e.g., fee model params, global caps),
  it MUST import through the bootstrap seam (see Patch 2).
  It must NEVER copy constants or re-derive values.

RULE-DRIFT-3: DEPRECATION TIMELINE
  After Package 3 completes, src/ modules that overlap with src/v25/ are
  scheduled for removal. A MIGRATION_CHECKLIST.md will be created at that time.
  Until then, both coexist with v25 as source of truth for its concerns.

RULE-DRIFT-4: CI ENFORCEMENT
  A structural test (test_import_boundary) ensures no file under src/ 
  (excluding src/v25/) contains `from src.v25.contracts` or 
  `from src.v25.config` or `from src.v25.db` imports.
  All cross-boundary access goes through src/v25/bootstrap.py only.
```

---

### PATCH 2: Integration Seam / Bootstrap Boundary

**Problem:** No defined public API for legacy code to consume v2.5 capabilities safely.

#### ADD new file to Module Layout:

```
src/v25/
├── __init__.py
├── bootstrap.py              ◄── NEW: sole public API for cross-boundary access
├── contracts/
│   └── ...
├── config/
│   └── ...
├── db/
│   └── ...
├── risk/
│   └── ...
└── telemetry/
    └── ...
```

#### ADD specification for bootstrap.py:

```
## Integration Seam: src/v25/bootstrap.py

This is the ONLY module legacy src/ code may import from src/v25/.
It re-exports a fixed set of named functions. No other import path is valid.

PUBLIC API (exhaustive — nothing else is exported):

  load_v25_config(
      risk_yaml_path: str = "config/risk.yaml",
      engines_yaml_path: str = "config/engines.yaml"
  ) -> V25Config
      Loads and validates both YAML files.
      Raises ConfigValidationError on any constraint violation.
      Returns a frozen V25Config dataclass.

  run_v25_migrations(db_path: str) -> sqlite3.Connection
      Creates all 13 tables + indexes idempotently.
      Returns an open connection.

  build_fee_model(config: V25Config) -> FeeModel
      Builds FeeModel from config.risk.fee_model section.
      All fee consumers call this; no hardcoded constants.

  compute_effective_cap(
      phase_risk: float,
      global_per_trade_cap: float
  ) -> float
      Returns min(phase_risk, global_per_trade_cap).

  evaluate_accel_gates(
      sub_regime: str,
      alignment_score: float,
      sqs_score: float,
      kill_switch_level: int,
      rolling_vol_24h: float,
      current_drawdown_pct: float,
      recent_slippage_err: float | None,
      filled_order_count: int,
      config: V25Config
  ) -> tuple[bool, str]
      Returns (passed, reason).

  recalculate_after_stop_widening(
      risk_per_trade: float,
      old_stop: float,
      stop_multiplier_delta: float,
      min_stop: float = 0.01,
      max_stop: float = 0.05
  ) -> tuple[float, float]
      Returns (new_stop, new_position_size).

IMPORT RULES:
  ✅ ALLOWED:   from src.v25.bootstrap import load_v25_config
  ✅ ALLOWED:   from src.v25.bootstrap import build_fee_model
  ❌ FORBIDDEN: from src.v25.contracts.fee import FeeModel  (internal path)
  ❌ FORBIDDEN: from src.v25.db.migrations import run_migrations  (internal path)
  ❌ FORBIDDEN: from src.v25.risk.caps import compute_effective_cap  (internal path)

EXCEPTION: Tests under tests/ MAY import internal modules directly for unit testing.
```

#### ADD structural test to Verification Plan:

```
TEST-BOUNDARY-01: Import Boundary Enforcement
  GIVEN the full source tree under src/ (excluding src/v25/)
  WHEN scanning all .py files for import statements
  THEN no file contains "from src.v25." imports EXCEPT "from src.v25.bootstrap"
  AND no file contains "import src.v25." EXCEPT "import src.v25.bootstrap"
```

---

### PATCH 3: Contracts Index (Resolve Count Ambiguity)

**Problem:** Plan says "16 contracts" but SPEC says "13 canonical contracts". The actual total is 16: 13 original + FeeModel (Patch 2) + CorrelationMatrix (Phase 2 stub) + PortfolioVariance (Phase 2 stub).

#### REPLACE the sentence "16 pydantic v2 models from SPEC PART1 Sections 2.1–2.16" with:

```
## Contracts Index

| # | Contract Name        | File                        | Spec Ref | Phase | Pkg 0 Required | Consumed By                              |
|---|----------------------|-----------------------------|----------|-------|----------------|------------------------------------------|
| 1 | MarketSnapshot       | contracts/market.py         | 2.1      | 0     | YES            | Snapshot builder, regime detector, SQS   |
| 2 | FeatureVector        | contracts/market.py         | 2.2      | 0     | YES            | Regime, engines, SQS                     |
| 3 | RegimeState          | contracts/regime.py         | 2.3      | 0     | YES            | Engines, MDE, SQS, accel gates           |
| 4 | Signal               | contracts/signal.py         | 2.4      | 0     | YES            | SQS gate, MDE, sizing                    |
| 5 | SignalQualityScore   | contracts/signal.py         | 2.5      | 1     | STUB           | SQS gate (Pkg 1 impl)                   |
| 6 | ConfidenceState      | contracts/signal.py         | 2.6      | 1     | STUB           | MDE, accel eval (Pkg 1/2 impl)          |
| 7 | TradeDecision        | contracts/decision.py       | 2.7      | 0     | YES            | RSL, execution, telemetry                |
| 8 | SizingDecision       | contracts/decision.py       | 2.8      | 0     | YES            | HyperSizer, RSL                         |
| 9 | ExecutionPlan        | contracts/decision.py       | 2.9      | 2     | STUB           | Execution engine (Pkg 2 impl)           |
| 10| PositionState        | contracts/position.py       | 2.10     | 0     | YES            | Risk, stop_resize, telemetry             |
| 11| LedgerEvent          | contracts/ledger.py         | 2.11     | 0     | YES            | Ledger writer                            |
| 12| RiskVerdict          | contracts/risk.py           | 2.12     | 0     | YES            | RSL, MDE                                |
| 13| TradeRecord          | contracts/trade.py          | 2.13     | 0     | YES            | Trade logger, edge health                |
| 14| FeeModel             | contracts/fee.py            | 2.14/P2  | 0     | YES            | SQS, backtest, time machine, bootstrap   |
| 15| CorrelationMatrix    | contracts/portfolio.py      | 2.15     | 2     | STUB           | Portfolio variance (Phase 2)             |
| 16| PortfolioVariance    | contracts/portfolio.py      | 2.16     | 2     | STUB           | Dynamic allocation (Phase 2)             |

TOTAL: 16 contracts.  
  13 = original canonical (Spec PART1 §2.1–2.13)  
   1 = FeeModel (added by REVISION_PATCH_001)  
   2 = Phase 2 stubs (CorrelationMatrix, PortfolioVariance)  

"Required in Package 0" means full field definitions + validation.  
"STUB" means class definition with all fields present, but no downstream logic yet.  
All 16 classes are instantiable and testable in Package 0.
```

---

### PATCH 4: Config Validation Error Handling

**Problem:** Plan says "raises SystemExit" in config loader. This couples library code to CLI behavior.

#### REPLACE in config loader description:

**Old:**
```
Startup validation (TEST-RC04): asserts every phase_risk <= global_caps.per_trade_risk_cap;
raises SystemExit on violation
```

**New:**
```
Startup validation (TEST-RC04): asserts every phase_risk <= global_caps.per_trade_risk_cap;
raises ConfigValidationError on violation.

ConfigValidationError is defined in src/v25/config/loader.py:

  class ConfigValidationError(Exception):
      """Raised when config values violate ARGUS v2.5 invariants."""
      violations: list[str]   # human-readable list of what failed

RULE: Only CLI entrypoints (src/main.py, scripts/) may catch ConfigValidationError
and convert it to SystemExit with a printed message. Library code (src/v25/*) must
NEVER call sys.exit().
```

#### UPDATE TEST-RC04:

**Old:**
```
THEN FATAL error: "phase_risk 4.5% exceeds global cap 3.0% — fix config"
AND system refuses to start
```

**New:**
```
THEN ConfigValidationError raised
AND error.violations contains "ACCELERATION.phase_risk 0.045 exceeds global_caps.per_trade_risk_cap 0.03"
AND load_v25_config() does NOT call sys.exit()
```

---

### PATCH 5: SQLite Migrations Completeness and Idempotency

**Problem:** Migration spec doesn't guarantee idempotent index creation or define precise behavior.

#### REPLACE the migrations description with:

```
## SQLite Migrations: src/v25/db/migrations.py

### run_v25_migrations(db_path: str) -> sqlite3.Connection

BEHAVIOR:
  1. Opens SQLite connection with WAL mode, foreign_keys=ON
  2. Wraps all DDL in a single transaction
  3. Executes CREATE TABLE IF NOT EXISTS for all 13 tables
  4. Executes CREATE INDEX IF NOT EXISTS for all indexes
  5. Inserts singleton row into kill_switch_state if not exists
  6. Returns open connection
  7. Safe to call repeatedly (fully idempotent)
  8. On DDL error: rolls back transaction, raises MigrationError (never partial state)

### Required Index Checklist

| Table                 | Index Name                  | Columns                    | Unique? |
|-----------------------|-----------------------------|----------------------------|---------|
| trades                | idx_trades_symbol           | symbol                     | No      |
| trades                | idx_trades_engine           | engine                     | No      |
| trades                | idx_trades_time             | entry_time                 | No      |
| trades                | idx_trades_capital          | capital_engine             | No      |
| decisions             | idx_decisions_time          | timestamp                  | No      |
| decisions             | idx_decisions_regime        | regime                     | No      |
| ledger                | idx_ledger_time             | timestamp                  | No      |
| ledger                | idx_ledger_type             | event_type                 | No      |
| ledger                | idx_ledger_engine           | capital_engine             | No      |
| sqs_log               | idx_sqs_time                | timestamp                  | No      |
| sqs_log               | idx_sqs_passed              | passed                     | No      |
| regime_history        | idx_regime_time             | timestamp                  | No      |
| counterfactuals       | idx_cf_time                 | timestamp                  | No      |
| counterfactuals       | idx_cf_resolved             | resolved                   | No      |
| edge_health           | idx_edge_engine             | engine                     | No      |
| experiment_versions   | idx_expver_status           | status                     | No      |
| backtest_runs         | idx_bt_strategy             | strategy_version           | No      |
| backtest_runs         | idx_bt_dates                | (start_date, end_date)     | No      |
| backtest_trades       | idx_bt_trades_run           | run_id                     | No      |
| backtest_equity_curve | idx_bt_eq_run               | run_id                     | No      |

TOTAL: 13 tables, 20 indexes, 1 singleton seed row.
```

#### ADD migration structural test:

```
TEST-MIG-01: Idempotent Migrations
  GIVEN a fresh in-memory SQLite database
  WHEN run_v25_migrations(":memory:") called TWICE
  THEN no errors raised
  AND all 13 tables exist
  AND all 20 indexes exist
  AND kill_switch_state has exactly 1 row with level=0

TEST-MIG-02: WAL Mode and Foreign Keys
  GIVEN run_v25_migrations(":memory:") returns conn
  WHEN querying PRAGMA journal_mode and PRAGMA foreign_keys
  THEN journal_mode = "wal"
  AND foreign_keys = 1
```

---

### PATCH 6: Accel Gates — Insufficient Data Safety

**Problem:** TEST-ACCEL04 allows Gate C (slippage) to PASS with insufficient data. Combined with other gates passing, this could activate Accel on the very first STRONG_TREND — before execution quality is proven.

#### REPLACE the Gate C spec (in REVISION_PATCH_001 Section, Accel Engine Override):

**Old:**
```
  Gate C — Slippage Quality Guard:
    ...
    IF fewer than 10 orders in history: Gate C = PASS (insufficient data to judge)
```

**New:**
```
  Gate C — Slippage Quality Guard:
    recent_slippage_err = mean(abs(actual_slippage - expected_slippage))
                          over last N filled orders (N = slippage_lookback_orders)
    max_slippage_err = 0.001 (0.1%)
    
    IF filled_order_count < slippage_lookback_orders:
      Gate C = NEUTRAL (neither pass nor fail — not evaluated)
    ELSE:
      IF recent_slippage_err > max_slippage_err: Gate C = FAIL
      ELSE: Gate C = PASS

  Gate D — Minimum Order History (NEW):
    min_orders_for_accel = 20
    IF filled_order_count < min_orders_for_accel: Gate D = FAIL
    ELSE: Gate D = PASS
    
    Rationale: Accel uses higher leverage. We must have enough
    execution history to trust our slippage estimates and confirm
    that the exchange adapter is working correctly. 20 orders ≈
    2-4 weeks of normal trading, enough to observe various market
    conditions.
```

#### ADD to config/engines.yaml dual_speed.accel section:

```yaml
    min_orders_for_accel: 20           # Gate D: minimum filled orders before accel eligible
```

#### REPLACE TEST-ACCEL04:

**Old:**
```
TEST-ACCEL04: Slippage Gate Passes with Insufficient Data
  GIVEN fewer than 10 historical orders
  WHEN Gate C evaluated
  THEN Gate C = PASS (insufficient data, benefit of doubt)
```

**New:**
```
TEST-ACCEL04a: Slippage Gate Neutral with Insufficient Data
  GIVEN filled_order_count = 5 (< slippage_lookback_orders = 10)
  AND all other signal+safety gates pass
  WHEN evaluate_accel_gates() called
  THEN Gate C = NEUTRAL (not evaluated, skipped)
  AND Gate D FAILS because 5 < min_orders_for_accel (20)
  AND overall result: BLOCKED
  AND reason contains "insufficient order history (5 < 20)"

TEST-ACCEL04b: Minimum Orders Gate Blocks Early Accel
  GIVEN filled_order_count = 15
  AND slippage_err = 0.0005 (would pass Gate C if evaluated)
  AND all signal gates pass, kill_switch=0, vol OK, dd OK
  WHEN evaluate_accel_gates() called
  THEN Gate C = NEUTRAL (15 > 10 lookback? Actually 15 >= 10, so Gate C evaluates)
  AND Gate C = PASS (0.0005 < 0.001)
  AND Gate D = FAIL (15 < 20)
  AND overall result: BLOCKED
  AND reason contains "insufficient order history (15 < 20)"

TEST-ACCEL04c: Full History Allows Activation
  GIVEN filled_order_count = 25
  AND slippage_err = 0.0005
  AND all other gates pass
  WHEN evaluate_accel_gates() called
  THEN Gate C = PASS
  AND Gate D = PASS
  AND overall result = PASS (assuming all 9 gates pass)
```

#### UPDATE TEST-ACCEL05 gate count:

**Old:**
```
TEST-ACCEL05: All Gates Must Pass Together
  ... (assumes 8 conditions)
```

**New:**
```
TEST-ACCEL05: All 9 Gates Must Pass Together
  GIVEN:
    Gate S1: sub_regime = "STRONG_TREND"           ✓
    Gate S2: alignment_score = 0.97 (>= 0.95)      ✓
    Gate S3: sqs_score = 0.90 (>= 0.85)            ✓
    Gate R1: kill_switch_level = 0                  ✓
    Gate A:  rolling_vol_24h = 0.03 (<= 0.04)       ✓
    Gate B:  current_drawdown_pct = 0.01 (<= 0.02)  ✓
    Gate C:  recent_slippage_err = 0.0005 (<= 0.001) ✓
    Gate D:  filled_order_count = 25 (>= 20)        ✓
  WHEN evaluate_accel_gates() called
  THEN result = (True, "all 9 gates passed")
  AND any single gate failing → result = (False, "<gate> failed: <reason>")
```

---

## B) CONTRACTS INDEX TABLE

(See Patch 3 above — the table IS the deliverable.)

Summary count reconciliation:

| Count | Description |
|-------|-------------|
| 13    | Original canonical contracts from SPEC PART1 §2.1–2.13 |
| +1    | FeeModel (REVISION_PATCH_001, Patch 2) |
| +2    | Phase 2 stubs: CorrelationMatrix, PortfolioVariance |
| **16**| **Total contract classes in src/v25/contracts/** |
| 11    | Fully implemented in Package 0 (YES in table) |
| 5     | Stub definitions in Package 0 (all fields present, no downstream logic) |

---

## C) UPDATED / NEW ACCEPTANCE TESTS

### From Patch 1 (Drift Prevention):

```
TEST-BOUNDARY-01: Import Boundary Enforcement
  GIVEN all .py files under src/ EXCLUDING src/v25/
  WHEN scanning for "from src.v25." or "import src.v25." patterns
  THEN the ONLY matches are "from src.v25.bootstrap" or "import src.v25.bootstrap"
  AND zero matches for any deeper import path (contracts, config, db, risk, telemetry)
```

### From Patch 4 (Config Error Handling):

```
TEST-RC04 (REVISED): Config Validation Raises Exception, Not SystemExit
  GIVEN config with ACCELERATION.phase_risk = 0.045
  AND global_caps.per_trade_risk_cap = 0.03
  WHEN load_v25_config() called
  THEN ConfigValidationError raised (NOT SystemExit)
  AND error.violations contains "ACCELERATION.phase_risk 0.045 exceeds global_caps.per_trade_risk_cap 0.03"
  AND calling code can catch and handle without process termination
```

### From Patch 5 (Migrations):

```
TEST-MIG-01: Idempotent Migrations
  GIVEN a fresh in-memory SQLite database
  WHEN run_v25_migrations(":memory:") called TWICE sequentially
  THEN no errors on either call
  AND all 13 tables exist (verified via sqlite_master)
  AND all 20 indexes exist
  AND kill_switch_state has exactly 1 row with level=0

TEST-MIG-02: WAL Mode and Foreign Keys
  GIVEN run_v25_migrations(":memory:") returns conn
  WHEN querying PRAGMA journal_mode and PRAGMA foreign_keys
  THEN journal_mode = "wal"
  AND foreign_keys = 1
```

### From Patch 6 (Accel Gates):

```
TEST-ACCEL04a, TEST-ACCEL04b, TEST-ACCEL04c, TEST-ACCEL05 (REVISED)
  (See Patch 6 above for full GIVEN/WHEN/THEN)
```

### Complete Test Count for Package 0:

| Category       | Test IDs                                              | Count |
|----------------|-------------------------------------------------------|-------|
| Risk caps      | RC01, RC02, RC03, RC04 (revised)                      | 4     |
| Fee model      | FEE01, FEE02, FEE03, FEE04                            | 4     |
| Accel gates    | ACCEL01, ACCEL02, ACCEL03, ACCEL04a/b/c, ACCEL05 (rev)| 7     |
| Stop resize    | SS01, SS02, SS03, SS04                                | 4     |
| Boundary       | BOUNDARY-01                                           | 1     |
| Migrations     | MIG-01, MIG-02                                        | 2     |
| **TOTAL**      |                                                       | **22**|

Plus structural tests: contract instantiation (16 valid, 16 invalid → 32 micro-tests), for a grand total of **54 test cases**.

---

## D) IMPLEMENTATION NOTES FOR CODEX

```
ARGUS v2.5 PACKAGE 0 — CODEX IMPLEMENTATION BRIEF
==================================================

ARCHITECTURE BOUNDARY:
  All v2.5 code lives in src/v25/.
  The ONLY public API is src/v25/bootstrap.py.
  Legacy src/ modules must NEVER import internal v25 paths.
  Test files MAY import internal modules directly.

CONTRACTS:
  16 pydantic v2 classes in src/v25/contracts/.
  All inherit ArgusModel(frozen=True, strict=True, extra="forbid").
  11 fully defined, 5 stubs (all fields present, no logic).
  FeeModel has 3 computed methods: live_round_trip, backtest_round_trip,
  estimate_slippage(notional_usd). These are the ONLY source for fee data.
  Zero hardcoded fee constants anywhere in the codebase.

CONFIG:
  load_v25_config() reads risk.yaml + engines.yaml.
  Validates ALL invariants at load time:
    - Every phase_risk <= global_caps.per_trade_risk_cap
    - Every phase max_leverage <= global_caps.max_leverage_global
    - fee_model fields are all positive
  Raises ConfigValidationError (never sys.exit).

SQLITE:
  run_v25_migrations() creates 13 tables + 20 indexes.
  Uses CREATE TABLE/INDEX IF NOT EXISTS. Fully idempotent.
  WAL mode + foreign_keys=ON. Single transaction.
  Seeds kill_switch_state singleton row (level=0).

RISK HELPERS:
  compute_effective_cap: returns min(phase_risk, global_cap).
  evaluate_accel_gates: 9 gates (3 signal + 6 safety). ALL must pass.
    Gate D (min_orders_for_accel=20) prevents early activation.
    Gate C is NEUTRAL (skipped) when order count < lookback window.
  recalculate_after_stop_widening: preserves risk_per_trade invariant.
    new_size = risk_per_trade / new_stop. Clamps stop to [0.01, 0.05].

INVARIANTS (assert-level, must never be violated):
  INV-RC1: risk_per_trade <= global_caps.per_trade_risk_cap
  INV-RC2: phase.phase_risk <= global_caps.per_trade_risk_cap (config load)
  INV-RC3: leverage <= max_leverage_core IF core
  INV-RC4: leverage <= max_leverage_accel IF accel
  INV-RC5: leverage <= max_leverage_global ALWAYS
  INV-RC6: position_size_pct <= max_position_size
  INV-RC7: invariant failure → trade REJECTED + alert (never silent clamp)
  INV-SS1: risk_per_trade = position_size × stop_distance
  INV-SS2: stop increase → size decrease proportionally
  INV-SS3: new_size = old_size / (1 + delta)
  INV-SS4: open positions: SL amended only, size unchanged
  INV-SS5: 0.01 <= new_stop <= 0.05

TEST EXECUTION:
  python -m pytest tests/unit/test_v25_package0.py -v
  Expected: 54 test cases, all PASS.
```

---

**END OF PLAN REVISION PATCH 002**
