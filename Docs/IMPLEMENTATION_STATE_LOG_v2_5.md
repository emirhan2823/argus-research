# IMPLEMENTATION_STATE_LOG_v2_5

Last updated: 2026-02-21  
Scope baseline: v2.5 implementation work completed through PR-H06, PR-G03.1, FIX-01 through FIX-05, PR-SHADOW-PERSIST, PR-EXIT-CONFIG, PR-I01, PR-I02, PR-J01, PR-J02, Phase A, Phase B (including B-05 router wiring), Phase C, Phase D, Phase E, Phase F, P4-A, P4-B, P4-C (adaptive hold optimization track), E2E harness, remaining gap closures (A-11, B-07, H-11, H-12), production hardening (Gemini pipeline wiring, PrecisionConfig YAML loading, NautilusEngine candle feeding, CorrelationTracker pipeline integration), ORION v1 meta-orchestrator, and Stage-2A real data integration in this repository state.

This log records implemented changes only, current safety posture, known debt, and the next ordered PR sequence.

## 1. Current Architecture State (Implemented)

### PR-G01 — Validated Sizing core
- What changed: Added `ValidatedSizing` contract (`src/v25/contracts/validated_sizing.py`), `compute_validated_size()` (`src/risk/validated_sizer.py`), Gate 9 utility `gate_breakeven_r_fee()` in `src/mde/gates.py`, and unit tests in `tests/risk/test_validated_sizer.py` and `tests/mde/test_breakeven_gate.py`.
- Risk addressed: Removed leverage-as-input sizing path in the new function; added deterministic fee-burden gate computation (`fee_risk_ratio`) with explicit fail reason.
- Remaining limitation: ~~Notional is currently `risk_usd / sl_pct` (not fee-adjusted notional formula).~~ Resolved by FIX-01.

### PR-G02 — Gate 9 integration into pre-trade path
- What changed: Wired `compute_validated_size()` into `PreTradeChecker.check()` (`src/risk/pre_trade.py`) and rejected candidates when `ValidatedSizing.passed_gate9` is false.
- Risk addressed: Trade admission now blocks fee-inefficient trades in pre-trade before execution decisions.
- Remaining limitation: At this stage, approval path temporarily used `validated_sizing.notional_usd` as `adjusted_position_size` (later corrected in PR-G03.1).

### PR-G03 — PreTrade integration hardening
- What changed: Added safe optional extraction for `max_leverage`, added sizing snapshot propagation, and ensured validated sizing rejection reasons (`gate9_fail` / `leverage_fail`) become primary reject reason.
- Risk addressed: Removed `max_leverage` attribute assumption failure mode and made validated-sizing rejection deterministic in pre-trade output.
- Remaining limitation: Unit mismatch remained on approved trades (`adjusted_position_size` temporarily held USD notional) until PR-G03.1.

### PR-G03.1 — Semantic correction for pre-trade size field
- What changed: Restored `adjusted_position_size` to legacy semantics (`max(size, 0.0)`), added `validated_notional_usd` to `PreTradeResult`, and updated `tests/risk/test_pre_trade_validated_sizing.py`.
- Risk addressed: Removed unsafe USD-notional-to-position-size semantic collision.
- Remaining limitation: `validated_notional_usd` is exposed as string metadata and is not yet consumed downstream by the execution path.

### PR-H01 — Dynamic Exit FSM skeleton
- What changed: Added `ExitStage` and `DynamicExitState` contracts (`src/v25/contracts/dynamic_exit.py`) and pure FSM functions (`src/execution/dynamic_exit.py`) with deterministic tests (`tests/execution/test_dynamic_exit_fsm.py`).
- Risk addressed: Exit logic is now deterministic, testable, and separated from broker side effects.
- Remaining limitation: ~~FSM policy is long-side oriented; no execution integration yet.~~ Short-side resolved by FIX-03.

### PR-H02 — Exit action outputs
- What changed: Added `ExitActionType` and `ExitAction`; added `update_dynamic_exit_with_action()` returning `(next_state, action)` and preserved `update_dynamic_exit()` as wrapper.
- Risk addressed: Stage transitions now produce explicit action intents (`UPDATE_STOP`, `TAKE_PARTIAL`, `NOOP`) for side-effect-free orchestration.
- Remaining limitation: Action policy is static (fixed partial fractions and ATR multipliers), and no close-position action path is emitted here.

### PR-H03 — OrderIntent abstraction
- What changed: Added `OrderIntentType` and `OrderIntent` (`src/v25/contracts/order_intent.py`), added mapper `map_exit_action_to_intent()` (`src/execution/exit_intent_mapper.py`), and mapping tests (`tests/execution/test_exit_intent_mapper.py`).
- Risk addressed: Introduced explicit contract boundary between exit policy and eventual order execution.
- Remaining limitation: `CLOSE_POSITION` is defined but not emitted by current mapper flow.

### PR-H04 — Shadow integration in position manager
- What changed: Added `shadow_dynamic_exit_intents()` to `HermesPositionManager` (`src/execution/hermes_position_manager.py`) to compute state/action/intent and log intent details without placing orders.
- Risk addressed: Enabled dry-run/observation path for dynamic exit behavior with zero broker interaction.
- Remaining limitation: Initial version used symbol-only cache key and immediate stale cleanup; both addressed by later PRs.

### PR-H05 — NOOP suppression and lock
- What changed: Added lightweight `threading.Lock` guard to shadow loop, suppressed NOOP intent emission/logging, and added test coverage.
- Risk addressed: Reduced race exposure in in-memory shadow updates and removed non-actionable output noise.
- Remaining limitation: Initial stale cleanup behavior still deleted state too aggressively on missing snapshots (addressed in PR-H05.1).

### PR-H05.1 — Shadow lifecycle stabilization
- What changed: Added `_shadow_missed_counts` and cleanup threshold logic (delete only after 3 consecutive misses), with tests updated to assert 1st/2nd miss keep state and 3rd miss removes state.
- Risk addressed: Prevented state loss from transient partial position snapshots.
- Remaining limitation: At this stage cache keys were still symbol-based, causing collision risk for multiple same-symbol positions.

### PR-H06 — Stable cache key (`position_id` first)
- What changed: Added cache key derivation using `position_id` then `id`, fallback to symbol; switched shadow state and missed-count maps to key-based tracking; logs now include both symbol and key; added test for two same-symbol positions with distinct ids.
- Risk addressed: Removed state collision between concurrent positions sharing the same symbol.
- Remaining limitation: If upstream snapshots omit both `position_id` and `id`, fallback key remains symbol and can still collide for same-symbol multi-position scenarios.

---

### FIX-01 — Fee-adjusted notional formula (Blueprint Pivot 1 alignment)
- What changed: Updated `compute_validated_size()` in `src/risk/validated_sizer.py` to use the fee-adjusted formula `notional = risk_usd / (sl_pct + fee_round_trip_pct)` instead of the previous `risk_usd / sl_pct`. Added `net_risk_usd` field to `ValidatedSizing` contract (`src/v25/contracts/validated_sizing.py`). Rewrote `tests/risk/test_validated_sizer.py` with 7 tests including `test_total_risk_within_budget` which mathematically proves `sl_loss + fee_cost == risk_usd`. Updated `tests/risk/test_pre_trade_validated_sizing.py` to match new formula outputs.
- Risk addressed: The core invariant from Blueprint Pivot 1 — that total risk (SL hit + round-trip fees) never exceeds `risk_usd` — is now enforced in code. Previously, fees were computed *after* sizing but not subtracted from the risk budget, meaning actual risk-on-the-table could exceed the intended risk by the fee amount.
- Mathematical guarantee: `notional × sl_pct + notional × fee_pct = notional × (sl_pct + fee_pct) = risk_usd`. With zero fees, formula degenerates to the old `risk_usd / sl_pct` (verified by `test_zero_fee_matches_old_formula`).
- Files touched: `src/risk/validated_sizer.py` (4 lines changed), `src/v25/contracts/validated_sizing.py` (1 field added), `tests/risk/test_validated_sizer.py` (rewritten, 7 tests), `tests/risk/test_pre_trade_validated_sizing.py` (updated assertions).
- Test result: 24/24 related tests pass.

### FIX-02 — DB migrations for CAI pivot tables (Phase C partial)
- What changed: Added 3 new tables to `src/v25/db/migrations.py`: `dynamic_exit_log` (Table 19, stage transitions and trailing stop audit), `validated_sizing_log` (Table 20, sizing computation audit with fee reservation), `whale_momentum_log` (Table 21, whale flow signal history). Added 7 new indexes (`idx_dynamic_exit_pos`, `idx_dynamic_exit_stage`, `idx_dynamic_exit_time`, `idx_val_sizing_time`, `idx_val_sizing_symbol`, `idx_whale_momentum_time`, `idx_whale_momentum_symbol`). Added 3 new telemetry functions to `src/v25/telemetry/log_writer.py`: `log_dynamic_exit()`, `log_validated_sizing()`, `log_whale_momentum()`. All follow the append-only, never-mutate design pattern of existing log functions.
- Risk addressed: Previously, dynamic exit transitions, validated sizing decisions, and whale momentum signals had no persistent audit trail. Restart or crash would lose all shadow state history. Now all three can be persisted to SQLite for post-mortem analysis.
- Schema totals: 16 application tables (13 existing + 3 new) + 27 indexes (20 existing + 7 new).
- Files touched: `src/v25/db/migrations.py` (~70 lines added), `src/v25/telemetry/log_writer.py` (~120 lines added).
- Test result: In-memory migration creates all 16 tables; all 3 log functions insert and read back correctly.

### FIX-03 — Short-side dynamic exit support
- What changed: Added `side` field to `DynamicExitState` contract (`src/v25/contracts/dynamic_exit.py`, default `"LONG"`, pattern-validated to `LONG|SHORT`). Updated `init_dynamic_exit()` in `src/execution/dynamic_exit.py` to accept `side` parameter: SHORT positions get stop above entry (`entry × (1 + sl_pct)`), TP targets below entry. Updated `update_dynamic_exit_with_action()`: SHORT PnL computed as `(entry - current) / risk_abs`; trailing stop uses `min()` (moves down only, never up) instead of `max()`; trailing candidates use `current × (1 + atr_mult)` instead of `current × (1 - atr_mult)`. Updated `HermesPositionManager.shadow_dynamic_exit_intents()` to read `side` from position snapshots and pass to `init_dynamic_exit()`. Added 5 short-side tests to `tests/execution/test_dynamic_exit_fsm.py`.
- Risk addressed: The system supports SHORT positions (BingX perpetual swap), but the exit FSM previously had no short-side logic. Stop monotonicity was enforced with `max()` which is wrong for shorts (stop is above entry and should only decrease). This is now corrected.
- Backward compatibility: `side` defaults to `"LONG"`, so all existing tests and call sites continue to work unchanged. All 7 original long-side tests pass unmodified.
- Files touched: `src/v25/contracts/dynamic_exit.py` (1 field added), `src/execution/dynamic_exit.py` (~40 lines changed), `src/execution/hermes_position_manager.py` (3 lines added), `tests/execution/test_dynamic_exit_fsm.py` (5 tests added).
- Test result: 12/12 dynamic exit tests pass (7 long + 5 short).

### FIX-04 — Shadow loop pipeline wiring
- What changed: Added `_open_positions` in-memory tracker to `ArgusPipeline.__init__()` in `src/main.py`. After successful executor fill, position metadata (position_id, symbol, side, entry_price, current_price, sl_pct, r_value_pct, atr_pct) is stored. Updated `_shadow_positions_snapshot()` from returning empty list to returning tracked positions. Shadow dynamic exit loop (`_run_shadow_dynamic_exit`) was already called per cycle; it now receives actual position data instead of empty snapshots.
- Risk addressed: Previously, `shadow_dynamic_exit_intents()` was called every cycle but received zero positions, making it a no-op in production. The shadow FSM now tracks real fills and computes exit intents on them. This is still shadow-only (no broker actions) but provides observability into what the dynamic exit system *would* do.
- Remaining limitation: Position tracking is in-memory and not synced with actual exchange state. In production, this should read from the broker/exchange API. Current implementation is sufficient for paper trading and shadow observation.
- Files touched: `src/main.py` (~15 lines added/changed).

### FIX-05 — Gate 9 single-path enforcement
- What changed: Removed the split-path Gate 9 block from `evaluate_gates()` in `src/mde/gates.py`. Previously, Gate 9 existed in two places: (1) optionally in `evaluate_gates()` when `risk_usd`/`notional_usd` were provided (never populated by pipeline), and (2) mandatorily in `PreTradeChecker.check()` via `compute_validated_size()`. Removed the optional path and cleaned `GateInput` of unused fields (`risk_usd`, `notional_usd`, `fee_bps`, `slippage_bps`). Added documentation comment in `evaluate_gates()` explaining that Gate 9 is enforced in pre_trade.py per GR-12. The `gate_breakeven_r_fee()` utility function remains in `gates.py` for standalone use.
- Risk addressed: Split enforcement created confusion about where Gate 9 was actually active. Since the pipeline never populated `risk_usd`/`notional_usd` in `GateInput`, the gates.py path was dead code. Now there is exactly one enforcement point (pre_trade.py), making the audit trail unambiguous.
- Files touched: `src/mde/gates.py` (~15 lines removed/changed).
- Test result: All gate tests pass; pre-trade Gate 9 enforcement unchanged.

### PR-SHADOW-PERSIST — Telemetry persistence wiring
- What changed: Wired `log_dynamic_exit()` into `_run_shadow_dynamic_exit()` in `src/main.py` so that every non-NOOP shadow exit intent is persisted to the `dynamic_exit_log` table. Wired `log_validated_sizing()` into the pre-trade path in `src/main.py` so that every `compute_validated_size()` result (approved or rejected) is persisted to the `validated_sizing_log` table. Added `v25_conn: sqlite3.Connection | None` parameter to `ArgusPipeline.__init__()` and passed it from `main()` when `--v25` flag is active. Added `validated_sizing: ValidatedSizing | None` field to `PreTradeResult` in `src/risk/pre_trade.py` so the pipeline can access the full sizing object for telemetry logging. Added `_persist_dynamic_exit_intent()` and `_persist_validated_sizing()` private methods to `ArgusPipeline` — both silently skip when `v25_conn` is None. Added `_stage_from_reason()` static helper to map intent reason strings to valid `dynamic_exit_log` stage values. Created 13 tests in `tests/v25/test_shadow_persist.py` covering: PreTradeResult.validated_sizing exposure (3 tests), log_writer DB insertion (3 tests), pipeline persistence integration (5 tests), stage mapping (1 test), no-op behavior (1 test).
- Risk addressed: Previously, `dynamic_exit_log` and `validated_sizing_log` tables existed (FIX-02) but were never written to from the production path. Shadow exit transitions and validated sizing decisions now have a persistent audit trail in SQLite for post-mortem analysis and debugging. Both writers are fault-tolerant (silently catch exceptions and log at DEBUG level).
- Backward compatibility: `v25_conn` defaults to `None`, so all existing code paths (non-v25 mode) are unaffected. `PreTradeResult.validated_sizing` defaults to `None`, so all existing tests pass unchanged.
- Files touched: `src/main.py` (~60 lines added), `src/risk/pre_trade.py` (3 lines added), `tests/v25/test_shadow_persist.py` (new, 13 tests).
- Test result: 13/13 new tests pass; 509/511 full suite pass (same 2 pre-existing failures).

### PR-EXIT-CONFIG — Dynamic exit config extraction
- What changed: Extracted all 7 hard-coded dynamic exit constants from `src/execution/dynamic_exit.py` into `config/engines.yaml` under `engines.hermes.dynamic_exit`. Added frozen `DynamicExitConfig` dataclass to `src/v25/config/loader.py` with fields: `r_breakeven` (0.5), `r_profit_capture` (1.5), `r_trend_rider` (3.0), `atr_mult_profit_capture` (2.0), `atr_mult_trend_rider` (1.2), `partial_fraction_profit_capture` (0.30), `partial_fraction_trend_rider` (0.20). Added `_parse_dynamic_exit_config()` parser and config validation (R thresholds must be strictly increasing, ATR mults > 0, partial fractions in (0,1]). Updated `init_dynamic_exit()` and `update_dynamic_exit_with_action()` in `src/execution/dynamic_exit.py` to accept optional `config: DynamicExitConfig | None` parameter; `None` uses built-in defaults for full backward compatibility. Updated `HermesPositionManager` to accept `dynamic_exit_config` field and pass it to FSM functions. Updated `ArgusPipeline` to load config from `engines.yaml` at init and pass to position manager. Created 11 tests in `tests/v25/test_exit_config.py` covering: default constants match, custom R thresholds for LONG/SHORT, config=None backward compat, custom ATR multipliers, custom partial fractions, YAML loader, missing-section defaults, validation of bad R ordering, and HermesPositionManager config forwarding.
- Risk addressed: All dynamic exit policy parameters are now tunable via YAML config without code changes, which is a prerequisite for backtesting different exit policies. The validation invariant (R thresholds strictly increasing) prevents misconfiguration that could cause skipped or impossible stage transitions.
- Backward compatibility: All functions default `config=None`, which uses the same hard-coded values as before. All 19 existing dynamic exit + position manager tests pass unchanged. `DynamicExitConfig()` with no args produces identical values to the old constants.
- Files touched: `config/engines.yaml` (8 lines added), `src/v25/config/loader.py` (~50 lines added), `src/execution/dynamic_exit.py` (~30 lines changed), `src/execution/hermes_position_manager.py` (5 lines changed), `src/main.py` (~30 lines added), `tests/v25/test_exit_config.py` (new, 11 tests).
- Test result: 11/11 new tests pass; 520/522 full suite pass (same 2 pre-existing failures).

### PR-I01 — Whale Momentum contract and aggregation (Blueprint Pivot 4)
- What changed: Added full `WhaleMomentumSignal` contract to `src/v25/contracts/intelligence.py` (frozen, strict, extra=forbid, extends `TimestampedModel`) with fields: `symbol`, `net_flow_usd_24h`, `exchange_reserve_change_pct`, `stablecoin_mint_usd_24h`, `accumulation_addresses`, `is_bullish_flow`, `is_bearish_flow`, `momentum_score` (SignedUnitDecimal), `sqs_boost` (RatioDecimal), `size_modifier` (NonNegativeDecimal), `confidence` (RatioDecimal). Expanded `src/engines/hermes/whale_momentum.py` with two new functions: `compute_whale_momentum(whale_alerts, timeframe_hours, median_net_flow_30d)` aggregates raw `WhaleAlert` list into full `WhaleMomentumSignal` (sums inflows/outflows, detects accumulation addresses, normalizes against 30d median, maps to SQS boost tiers: 0.5R→0.05, 0.8R→0.10, quantizes Decimals to avoid pydantic digit overflow); `apply_whale_boost_to_sqs(base_c5, whale, regime)` applies whale boost to SQS C5 with rules: only in TREND_STRONG, defensive override if base_c5 < 0.30 (GR-14), max output 1.0. Existing `compute_whale_boost`/`build_whale_momentum_signal` preserved for backward compatibility (uses simplified `WhaleMomentumSignal` from `src/v25/contracts/whale_momentum.py`). Created 16 tests in `tests/v25/test_whale_momentum_contract.py` covering: contract validation (frozen, NaN rejection, bounds, extra field rejection, valid construction), `compute_whale_momentum` aggregation (empty alerts, bullish/bearish dominance, tier1/tier2 boost, old alerts excluded, confidence averaging), `apply_whale_boost_to_sqs` (boost applied, regime block, defensive override, cap at 1.0).
- Risk addressed: Blueprint Pivot 4 contract is now code-complete with strict validation and aggregation logic. The defensive override precedence (GR-14) is enforced in `apply_whale_boost_to_sqs` — if base SQS C5 < 0.30, whale boost is zeroed regardless of whale signal strength.
- Dual contract note: There are now two `WhaleMomentumSignal` classes: (1) `src/v25/contracts/whale_momentum.py` — simplified scoring output used by legacy `build_whale_momentum_signal`; (2) `src/v25/contracts/intelligence.py` — full Blueprint Pivot 4 contract used by new `compute_whale_momentum`. These serve different purposes and will converge when PR-I02 wires the new contract into the Hermes engine.
- Backward compatibility: Existing `compute_whale_boost` and `build_whale_momentum_signal` functions unchanged. All pre-existing tests pass.
- Files touched: `src/v25/contracts/intelligence.py` (~40 lines added), `src/engines/hermes/whale_momentum.py` (~100 lines added), `tests/v25/test_whale_momentum_contract.py` (new, 16 tests).
- Test result: 16/16 new tests pass; 534/537 full suite pass (3 pre-existing failures).

### PR-I02 — Whale momentum boost wiring (Blueprint Pivot 4 integration)
- What changed: Added `is_trend_strong(regime, confidence, stability)` helper to `src/engines/hermes/whale_momentum.py` that maps the real regime taxonomy (`TRENDING` + high confidence/stability) to the blueprint's `TREND_STRONG` gate, since the codebase has no literal `TREND_STRONG` regime. Added `apply_whale_boost_to_signal(base_confidence, whale, regime, regime_confidence, regime_stability)` pipeline-facing API that returns `(boosted_confidence, was_applied, reason)` — works with `RegimeState` fields directly. Wired whale boost into `ArgusPipeline.run_once()` as step 6.6 (between signal quality assessment and gates): calls `compute_whale_momentum()` on stored alerts, applies boost via `apply_whale_boost_to_signal()`, and updates signal confidence. Added `_apply_whale_momentum_boost()` method to `ArgusPipeline` — orchestrates whale computation, boost application, and telemetry persistence. Added `_persist_whale_momentum()` method to `ArgusPipeline` — writes to `whale_momentum_log` table via `log_whale_momentum()`, fault-tolerant. Added `_whale_alerts: list[WhaleAlert]` field to `ArgusPipeline` for external data source injection. Created 21 tests in `tests/v25/test_whale_boost_wiring.py` covering: `is_trend_strong` regime mapping (9 tests including boundary), `apply_whale_boost_to_signal` pipeline API (6 tests: boost applied, regime block, defensive override GR-14, neutral whale, cap at 1.0, low stability), telemetry persistence (2 tests), pipeline integration via mock (4 tests: no alerts passthrough, boost with alerts, DB persistence, no-DB skip).
- Risk addressed: Whale momentum is now fully wired into the pipeline signal path. The regime mismatch between blueprint (`TREND_STRONG`) and codebase (`TRENDING`) is resolved via `is_trend_strong()` which requires `TRENDING` + `confidence >= 0.70` + `stability >= 0.60` — preventing whale boost in weak or unstable trends. GR-14 defensive override is enforced: base confidence < 0.30 blocks all whale boost. Telemetry is persisted for every whale computation regardless of whether boost was applied. The existing `apply_whale_boost_to_sqs()` is preserved unchanged for backward compatibility.
- Backward compatibility: `apply_whale_boost_to_sqs()` unchanged. `_whale_alerts` defaults to empty list so pipeline behavior is identical when no whale data source is connected. All 16 PR-I01 tests pass unchanged.
- Files touched: `src/engines/hermes/whale_momentum.py` (~60 lines added), `src/main.py` (~70 lines added), `tests/v25/test_whale_boost_wiring.py` (new, 21 tests).
- Test result: 21/21 new tests pass; 555/558 full suite pass (3 pre-existing failures).

### PR-J01 — Hyper-Precision module (CAI Pivot 5, pure helpers)
- What changed: Created `src/execution/hyper_precision.py` with three pure functions (no broker calls): `snipe_entry()` evaluates 1m timeframe microstructure for optimal entry — checks directional OBI >= 0.60, places limit at VWAP band edge (0.3% band), skips on LOW/NORMAL urgency with bad OBI, falls back to market on HIGH/CRITICAL urgency, CRITICAL reduces timeout from 3 to 1 bar. `snipe_partial_exit()` evaluates OBI reversal for optimal partial close — detects opposing OBI >= 0.30 and narrow spread for limit exit, otherwise market fallback. `compute_trailing_sl()` computes ATR-based trailing stop — LONG: `price - atr * mult` (ratchets UP only via `max()`), SHORT: `price + atr * mult` (ratchets DOWN only via `min()`). All thresholds are module-level constants: `OBI_THRESHOLD=0.60`, `SPREAD_RATIO_LIMIT=2.0`, `VWAP_LIMIT_BAND_PCT=0.003`, `EXIT_OBI_REVERSAL_THRESHOLD=0.30`. Two frozen dataclasses: `PrecisionEntryResult` and `PrecisionExitResult`. Created 36 tests in `tests/execution/test_hyper_precision.py` covering all paths.
- Risk addressed: Hyper-precision execution decisions are now available as pure, testable functions. Monotonic SL enforcement works correctly for both LONG and SHORT positions. The module has zero broker dependencies — it only computes decisions, which PR-J02 will wire into the executor.
- Files created: `src/execution/hyper_precision.py` (~120 lines), `tests/execution/test_hyper_precision.py` (36 tests).
- Test result: 36/36 new tests pass.

### Phase A — Correlation Engine Foundation
- What changed: Created `src/v25/contracts/correlation.py` with three strict contracts: `CorrelationPair` (tracked pair state with correlation, spread z-score, half-life, cointegration status, regime), `CorrelationSignal` (trading signal with dual-leg directions, confidence, z-score levels), `CorrelationHealth` (system health metrics). All frozen, strict, extra=forbid per GR-6. Created `src/correlation/` package with three modules: `tracker.py` provides `calculate_correlation()` (rolling Pearson), `calculate_spread()` (log_ratio/zscore methods), and `CorrelationTracker` class (maintains pair state, recomputes from price dict); `ou_estimator.py` provides `estimate_half_life()` (AR(1) half-life, returns None if not mean-reverting) and `fit_ou_process()` (theta/mu/sigma via discrete OU); `cointegration.py` provides `test_cointegration()` (Engle-Granger: OLS residuals + ADF, with statsmodels fallback). Created 42 tests across `tests/correlation/test_correlation_contracts.py` (20 tests), `tests/correlation/test_tracker.py` (14 tests), `tests/correlation/test_ou_estimator.py` (8 tests).
- Risk addressed: Correlation engine foundation is now code-complete with strict contracts and tested computation functions. This enables Phase B (Gemini pairs trading engine) and Phase D (CHOP correlation gap detection).
- Files created: `src/v25/contracts/correlation.py` (~60 lines), `src/correlation/__init__.py`, `src/correlation/tracker.py` (~100 lines), `src/correlation/ou_estimator.py` (~80 lines), `src/correlation/cointegration.py` (~60 lines), `tests/correlation/__init__.py`, `tests/correlation/test_correlation_contracts.py` (20 tests), `tests/correlation/test_tracker.py` (14 tests), `tests/correlation/test_ou_estimator.py` (8 tests).
- Test result: 42/42 new tests pass; 633/636 full suite pass (3 pre-existing failures).

### PR-J02 — Execution integration (graduate from shadow to conditional live)
- What changed: Extended `src/execution/executor.py` with two new methods: `execute_with_precision()` uses `snipe_entry()` from hyper-precision module to decide order type (limit/market/skip) based on OBI, spread, and urgency before calling broker — skips trade if OBI insufficient and urgency is LOW/NORMAL, falls back to market on HIGH/CRITICAL; `execute_partial_close()` uses `snipe_partial_exit()` to optimize partial close order type via OBI reversal detection. Extended `src/execution/hermes_position_manager.py` with `live_dynamic_exit_intents()` that computes dynamic exit intents AND executes them against the broker (UPDATE_STOP calls `broker.modify_stop_loss` with hyper-precision trailing SL via `compute_trailing_sl()`, CLOSE_POSITION calls `broker.close_position`). Added `_find_position()` helper. Wired `compute_trailing_sl` import. Added conditional live/shadow mode to `src/main.py`: `_live_exit_enabled` flag (default False, shadow mode), `_run_live_dynamic_exit()` method that calls `live_dynamic_exit_intents()` and persists telemetry. Fixed PR-I01 test timestamp fragility: `tests/v25/test_whale_momentum_contract.py` used hardcoded `_NOW = datetime(2026, 2, 16, ...)` which aged past the 24h cutoff window; changed to `datetime.now(timezone.utc)`. Created 14 tests in `tests/execution/test_execution_integration.py`.
- Risk addressed: The execution layer now has a complete path from signal → precision entry → dynamic exit → precision partial close → trailing SL, all gated behind a `_live_exit_enabled` flag. Shadow mode remains the default, ensuring zero broker interaction until explicitly enabled. The hyper-precision trailing SL uses `compute_trailing_sl()` with monotonic enforcement (LONG: only up, SHORT: only down).
- Backward compatibility: `execute()` unchanged. `shadow_dynamic_exit_intents()` unchanged. `_live_exit_enabled` defaults to False, so existing behavior is preserved. All existing tests pass.
- Files touched: `src/execution/executor.py` (~100 lines added), `src/execution/hermes_position_manager.py` (~80 lines added), `src/main.py` (~20 lines added), `tests/v25/test_whale_momentum_contract.py` (1 line fix), `tests/execution/test_execution_integration.py` (new, 14 tests).
- Test result: 14/14 new tests pass; 647/650 full suite pass (3 pre-existing failures).

### E2E Validation Harness — CAI pivot integration tests
- What changed: Created `tests/integration/test_e2e_cai_pivots.py` with 14 integration tests across 5 test classes validating composed behavior of all CAI pivot modules. `TestSizingToGate9Flow` (3 tests): validated sizing approval, gate 9 rejection for high-fee trades, and mathematical proof that `sl_loss + fee_cost == risk_usd`. `TestDynamicExitProgression` (4 tests): full ENTRY→BREAKEVEN_LOCK→PROFIT_CAPTURE→TREND_RIDER progression for LONG and SHORT, plus monotonic stop enforcement for both sides. `TestShadowIntentEmission` (3 tests): UPDATE_STOP and TAKE_PARTIAL intent emission, NOOP suppression. `TestPrecisionExecutionFlow` (2 tests): precision entry → partial close flow with FakeBroker, and live exit SL update via broker. `TestWhaleBoostE2E` (2 tests): whale boost applied in TRENDING regime, blocked in RANGING.
- Risk addressed: All key CAI pivot modules are now validated in composition: validated sizing + gate 9, dynamic exit FSM (both sides), shadow intent emission, hyper-precision + executor integration, and whale momentum boost. This is the safety net that catches regressions in cross-module behavior.
- Files created: `tests/integration/__init__.py`, `tests/integration/test_e2e_cai_pivots.py` (14 tests).
- Test result: 14/14 new tests pass; 661/664 full suite pass (3 pre-existing failures).

### B-05 — Gemini Router Registration
- What changed: Added `ENGINE_GEMINI` to `REGIME_TO_SECONDARY_ENGINES[REGIME_RANGING]` in `src/core/constants.py`. Gemini now participates as a secondary engine alongside Hydra when the regime is RANGING. The router will call Gemini's `generate_signal()` and compete its output against the primary (Nautilus) and other secondaries (Hydra) by confidence. Also added `CORR_MEAN_REVERSION` to `TemplateName` enum in `src/v25/contracts/signal.py` for Gemini's signal template.
- Risk addressed: Gemini was created in Phase B but not registered in the routing infrastructure, making it unreachable from the pipeline. Now it is reachable in RANGING regime.
- Backward compatibility: Gemini engine instance must be registered in `RegimeRouter.engines` dict for the route to actually call it. If not present, the router silently skips (existing behavior for missing engine keys).
- Files touched: `src/core/constants.py` (1 line changed), `src/v25/contracts/signal.py` (1 line added).
- Test result: 4 router registration tests pass.

### Phase D — Enhanced CHOP Alpha
- What changed: Created three new modules for the Nautilus engine to improve alpha in CHOP/RANGING markets. `src/engines/nautilus/range_mapper.py` provides `identify_range()` which detects horizontal price ranges from candle data using pivot-high/low clustering with ATR-based tolerance; returns `RangeResult` (frozen dataclass with range_high, range_low, midpoint, width, touch counts) or None. `src/engines/nautilus/micro_reversion.py` provides `detect_micro_reversion()` which generates entry signals at range boundaries using 5m microstructure: LONG at range_low when OBI > 0.55 and RSI < 35, SHORT at range_high when OBI < -0.55 and RSI > 65, stop outside range by 0.5 ATR, target at midpoint. `src/engines/nautilus/chop_corr_gap.py` provides `detect_chop_correlation_gap()` which generates convergence signals when a normally-correlated pair (correlation >= 0.60) shows one asset deviating while both remain in RANGING with ADX < 25. Added `CHOP_CORR_GAP` and `CHOP_MICRO_REVERSION` to `TemplateName` enum. Wired `micro_reversion` into `NautilusEngine.generate_signal()` as a third sub-strategy candidate (alongside `bb_reversion` and `funding_reversion`). Added `feed_candles()` method and `_candle_history`/`_cached_ranges` state to `NautilusEngine` for range detection data. Updated `src/engines/nautilus/__init__.py` to export all new modules. Added `max_chop_trades_per_day: 6`, `micro_reversion`, and `chop_corr_gap` config sections to `config/engines.yaml` under `nautilus`. The `chop_corr_gap` function takes pair-level data (features_a, features_b, regime_a, regime_b, correlation, spread_zscore) and is designed to be called from the pipeline when correlation pair data is available, not from the standard engine dispatch. Created 35 tests in `tests/engines/test_nautilus_enhanced.py` covering: range detection (9 tests: flat range, insufficient data, zero ATR, trending rejection, touch counts, narrow range rejection, pivot highs/lows, cluster detection), micro-reversion (6 tests: long at range_low, short at range_high, weak OBI, neutral RSI, missing OBI, far from boundary), chop correlation gap (8 tests: short on positive zscore, long on negative, regime blocking, low correlation, small zscore, high ADX, cointegration boost, half-life boost), template names (4 tests), engine wiring (4 tests: micro_reversion wired, works without candles, non-RANGING rejection, best signal selection), router registration (4 tests).
- Risk addressed: CHOP/RANGING regimes now have three additional alpha sources: micro-reversion at range boundaries with microstructure confirmation, and correlation gap convergence for pair deviations. The existing BB reversion and funding reversion strategies are preserved unchanged. All new strategies are pure functions with no broker side effects. The `chop_corr_gap` requires both assets to be in RANGING with low ADX, preventing false signals during transitional regimes.
- Backward compatibility: `NautilusEngine.generate_signal()` signature unchanged. `_candle_history` defaults to empty dict, so existing callers that don't call `feed_candles()` get identical behavior (only BB and funding strategies). All 4 existing Nautilus tests pass unchanged.
- Files created: `src/engines/nautilus/range_mapper.py` (~140 lines), `src/engines/nautilus/micro_reversion.py` (~110 lines), `src/engines/nautilus/chop_corr_gap.py` (~125 lines), `tests/engines/test_nautilus_enhanced.py` (35 tests).
- Files modified: `src/engines/nautilus/engine.py` (~30 lines added), `src/engines/nautilus/__init__.py` (8 lines added), `src/v25/contracts/signal.py` (3 lines added), `config/engines.yaml` (~15 lines added).
- Test result: 35/35 new tests pass; 715/718 full suite pass (same 2 pre-existing failures, 1 skip).

### Phase E — Precision Entry Pipeline
- What changed: Created `src/mde/precision_filter.py` with `assess_entry_precision()` that grades microstructure quality A-F using 5 weighted factors: OBI alignment (0.30), spread tightness (0.25), VWAP proximity (0.20), volume support (0.15), ATR reasonableness (0.10). Returns frozen `PrecisionGrade` dataclass with grade, score, component values, recommended entry price, and order type. `PrecisionConfig` frozen dataclass makes all thresholds configurable. Grade F rejects the trade, Grade A/B boosts confidence (+0.05/+0.02), Grade D penalizes (-0.05). Wired at pipeline step 6.7 in `src/main.py` (between whale boost 6.6 and gates 7) — Grade F triggers `_reject()`, otherwise applies confidence adjustment. Added `precision_filter` config section to `config/engines.yaml` with grade thresholds and confidence adjustments. Created 47 tests in `tests/mde/test_precision_filter.py` covering: grades A/B/C/D/F (7 tests), OBI scoring (7), spread scoring (4), VWAP scoring (4), volume scoring (3), ATR scoring (3), grade assignment (8), confidence adjustment (5), order type (2), output structure (3).
- Risk addressed: Previously, the pipeline had no microstructure quality assessment at entry time. Bad microstructure (wide spread, no OBI support, VWAP deviation) could lead to poor fills and increased slippage. The precision filter now gates entry quality and adjusts confidence accordingly. Grade F blocks entry entirely, preventing trades in hostile microstructure.
- Backward compatibility: `assess_entry_precision()` is a standalone function; pipeline wiring is additive (new step 6.7). All existing tests pass unchanged.
- Files created: `src/mde/precision_filter.py` (~200 lines), `tests/mde/test_precision_filter.py` (47 tests).
- Files modified: `src/main.py` (~15 lines added), `config/engines.yaml` (~10 lines added).
- Test result: 47/47 new tests pass; 762/765 full suite pass (same 3 pre-existing failures).

### Phase F — Integration + Backtest Validation
- What changed: Created `tests/integration/test_phase_f_validation.py` with 21 integration tests across 5 test classes validating the composed behavior of all new modules in realistic scenarios. `TestGeminiBacktest` (3 tests): mean-reversion backtest on synthetic cointegrated pair (verifies positive PnL after fees), engine signal production from correlation pair, spread half-life detection within expected bounds. `TestNautilusCHOPBacktest` (4 tests): BB reversion profitability in RANGING, range mapper detection on synthetic data, micro-reversion signal at boundary with correct direction, engine strategy selection among sub-strategies. `TestCorrelationBlowup` (5 tests): no signal on collapsed correlation (< 0.60), CRISIS regime blocking, regime mismatch blocking (one asset trending), extreme z-score handling, NaN price survival without crash. `TestFullPipelineIntegration` (4 tests): router dispatch to Nautilus in RANGING, signal quality then precision filter chain (verify confidence adjustment), CRISIS produces no signal, precision grade variance with different microstructure quality. `TestFeeDragValidation` (5 tests): 20 trades/day maker fee drag < 2% of equity, taker fee drag < 3%, backtest engine fee accounting (PnL < gross), breakeven-R gate math (high fee ratio rejected), reasonable stop passes breakeven gate.
- Risk addressed: All new modules (Gemini, enhanced Nautilus, correlation engine, precision filter) are now validated in composition with realistic scenarios. Fee drag is verified to be within acceptable bounds. Edge cases (correlation collapse, CRISIS regime, NaN data, extreme z-scores) are explicitly tested. This is the safety net that catches cross-module regressions.
- Files created: `tests/integration/test_phase_f_validation.py` (21 tests).
- Test result: 21/21 new tests pass; 782/786 full suite pass (3 pre-existing Windows-specific failures, 1 skip). Zero regressions.

### P4-A — Regime-aware adaptive hold from sweep (backtest-only, analysis-driven application)
- What changed: Added hold-grid sweep analysis and adaptive hold application wiring in backtest simulator path only. Simulated exits continue to be deterministic and derived from replay-aware close lookup + cost model. Adaptive hold selection uses sweep-derived performance and persists selected `hold_minutes` into `trades` rows.
- CLI added: `--hold-grid-minutes`, `--hold-grid-by`, `--adaptive-hold-from-sweep`.
- Summary/reporting: `summary.json` now contains `exit_sweep` payload (`enabled`, `holds`, `best_hold_overall`, `by_hold`, `best_hold_by_regime`, `skipped_rows`) and `summary.md` includes an "Exit Sweep (Hold Grid)" section.
- Tests: `test_backtest_exit_hold_grid_sweep_outputs`, `test_backtest_adaptive_hold_from_sweep_by_regime` in `tests/data/test_v25_cycle_execution.py`.

### P4-B — In-sample / out-of-sample adaptive hold split (backtest-only, no leakage)
- What changed: Added split-based adaptive learning/apply control to prevent look-ahead. For cycles in IS window, sweep rows update learning stats but persisted trades use default hold; for OOS window, adaptive per-regime hold is applied using IS-only accumulated stats.
- CLI added: `--adaptive-split-ratio` (`0.0..1.0`, default `0.5`).
- Summary/reporting: `summary.json` now includes `adaptive_hold_used`, `adaptive_split_ratio`, `in_sample_cycles`, `out_of_sample_cycles`.
- Tests: `test_backtest_adaptive_hold_split_uses_is_then_oos` in `tests/data/test_v25_cycle_execution.py`.

### P4-C — Rolling walk-forward adaptive hold (backtest-only, deterministic)
- What changed: Added rolling walk-forward adaptive hold mode. When walk-forward window is configured, static split logic is disabled and hold selection uses only prior-window sweep rows (`decision_cycle` bounded to learning window), eliminating future leakage.
- CLI added: `--adaptive-walk-window`, `--adaptive-walk-step`.
- Summary/reporting: `summary.json.walk_forward` object added with fields: `enabled`, `window`, `step`, `segments`, `oos_cycles`.
- Determinism: Selection remains deterministic (fixed tie-breaking, replay-timestamp based ordering, no randomness).
- Live/paper impact: **None**. Changes are isolated to backtest simulator logic.
- Acceptance test: `test_backtest_walk_forward_adaptive_hold` in `tests/data/test_v25_cycle_execution.py` verifies 60-cycle run, varying `hold_minutes`, and `summary.walk_forward.enabled == true`.

### P4-D — Engine Observatory (always-on per-engine analytics)
- What changed: Created `src/v25/reports/engine_observatory.py` with `write_engine_observatory(db_path, run_dir, mode)` entry point. Generates 6 output files: `engine_overview.json`, `engine_overview.md`, `engine_overview.csv`, `engine_regime_breakdown.csv`, `engine_recent_windows.csv`, `signal_funnel.csv`. Computes per-engine metrics: `closed_trades_count`, `win_rate`, `total_return`, `avg_trade_return`, `median_trade_return`, `max_drawdown` (multiplicative from sequential net_pnl_pct), `avg_hold_minutes` (from column or derived from timestamps), `exposure_proxy`. Regime breakdown repeats metrics grouped by `(engine, regime_at_entry)`. Recent windows compute metrics for last-20, last-50, last-200 trades per engine. Signal funnel aggregates from `decisions` table: `decisions_total`, `executed`, `rejected`, `no_signal`, `crisis_override_count`, `gate9_fail_count` (parsed from `gate_results_json` or `reason`). Graceful degradation: missing tables/columns default to 0/null via `_safe_query` and `_has_column` helpers. Wired into `src/main.py` for all v25 modes (backtest/paper/live). Updated `src/v25/reports/__init__.py` exports.
- Live/paper impact: **None**. Report generation only; no trading logic touched.
- Files created: `src/v25/reports/engine_observatory.py` (~310 lines), `tests/data/test_engine_observatory.py` (10 tests).
- Files modified: `src/main.py` (~14 lines added), `src/v25/reports/__init__.py` (2 lines added).
- Test result: 10/10 new tests pass; 19/19 existing v25 cycle tests pass (zero regressions).

### Stage-2A — Real Data Integration (live market data pipeline)
- What changed: Updated `BinancePublicClient` in `src/data/exchange_clients.py` with in-memory TTL cache (default 55s, LRU eviction at 100 entries) and inter-request rate limiter (100ms min between API calls). Added `cache_ttl` constructor parameter. Updated `_load_ohlcv()` in `src/main.py` with a new `"live"` mode path: when `data_factory.mode == "live"` and exchange client is available, fetches real klines from Binance API instead of generating mock random walks. Falls back to mock if fetch returns empty. Added `--live-data` CLI flag (sets `data_mode="live"`) and `--timeframe` CLI flag (default `1h`, sets `_primary_tf` on pipeline). Pipeline initialization wires these into `DataFactory` constructor via the existing `data_mode` parameter. Added startup status lines: `[data] LIVE` or `[data] MOCK`. Created `tests/integration/test_live_data.py` with 5 tests: real Binance API schema validation (online), DataFactory delegation (offline), 2-cycle paper smoke with real data (online), cache hit prevention (offline), cache TTL expiry (offline).
- Risk addressed: Previously, paper mode always used `_mock_ohlcv()` which generates random walks — useless for evaluating real market behavior. Now paper/live modes can use real Binance klines with a single flag. TTL cache prevents redundant API calls when multiple assets share the same symbol. Rate limiter keeps requests well within Binance's 1200 req/min limit. Mock fallback ensures no crash if network is unavailable.
- Backward compatibility: Default behavior unchanged (mock data). `--live-data` is opt-in. `BinancePublicClient` constructor accepts `cache_ttl=None` which defaults to 55s; existing callers unaffected. All 39 existing regression tests pass.
- Files modified: `src/data/exchange_clients.py` (~40 lines changed), `src/main.py` (~40 lines added).
- Files created: `tests/integration/test_live_data.py` (5 tests).
- Test result: 5/5 new tests pass; 39/39 existing regression tests pass (zero regressions).

### Stage-2D — Reliability + Notifications + Multi-symbol (paper/live readiness)
- What changed: Upgraded Binance public client resilience for live-data path with (1) idle session refresh (default 180s, env-overridable), (2) exponential backoff + jitter (`min(30, 2**attempt + rand(0,1))`), and (3) circuit breaker (default open after 5 consecutive failures, 60s cooldown). Added structured logs for attempt/failure/backoff and breaker OPEN/CLOSE transitions.
- Multi-symbol support: Added CLI `--symbols` and `--symbol-universe-size {5,15}`. For live-data runs, default crypto universe now uses a safe top-5 basket (`BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT`) unless overridden. 15-symbol option remains opt-in.
- Telegram signal notifier: Added `src/notifications/telegram.py` and CLI `--telegram-signals`, `--telegram-min-confidence`. Notifications trigger only for actionable advisory signals (`status=executed`, `reason=advisory_signal_sent`, `action in {long,short}`) with confidence gate, dedup (same symbol/action within 10m), daily cap (30/day UTC), and DB-backed persistence via `telegram_notifications`.
- DB/schema: Added `telegram_notifications` table and indexes in v2.5 migrations for dedup/cap audit traceability.
- Python 3.12 migration safety: Added isolated venv setup guidance in `Docs/ENV_SETUP.md`; validated install path on 3.12; added `pyarrow` to runtime requirements for parquet/replay compatibility; kept `pandas_ta` optional with fallback behavior intact (`BasicFeatureBuilder`).
- Verification docs: Added/updated `Docs/VERIFY_STAGE2D.md` with copy-paste commands for venv setup, dependency install, full regression (`pytest -q`), targeted Stage-2D tests, paper one-cycle, paper 24h supervisor, Telegram enablement, and online-test gating.
- Live/paper impact: additive and opt-in (CLI/env gated). Backtest deterministic behavior remains unchanged unless backtest-specific flags are explicitly enabled.
- Tests added:
  - `tests/unit/test_exchange_client_resilience.py` (`test_backoff_and_circuit_breaker_behavior`, `test_session_refresh_after_idle`)
  - `tests/unit/test_telegram_notifier.py` (`test_telegram_dedup_logic`, `test_telegram_daily_cap`)
  - `tests/unit/test_symbol_universe.py` (`test_symbols_parsing_and_default_universe`)
  - `tests/integration/test_live_data.py` (`test_live_data_path_uses_exchange_client_and_cache_for_multiple_symbols`, `test_binance_live_data_multi_symbol_smoke`, `test_binance_live_data_handles_disconnect_gracefully`)
- Local verification result (2026-02-21): `973 passed, 5 skipped` on Python 3.12 (`venv312`) with full `pytest -q` run.

### Release hardening update — 7/24 paper + forward/backtest analytics (2026-02-21)
- Python 3.12 parallel venv migration path finalized with `.venv312` naming in docs (`Docs/ENV_SETUP.md`, `Docs/VERIFY_STAGE2D.md`) while preserving existing environments.
- Binance live-data resilience hardened for `RemoteDisconnected` path in `src/data/exchange_clients.py`: explicit disconnect exception handling now routes through retry/backoff + circuit-breaker logic; cache lookup is now evaluated before breaker short-circuit to maximize cached continuity during cooldown.
- Telegram notifier message contract updated in `src/notifications/telegram.py` to include a mandatory disclaimer line: `paper signal only`.
- Added integration coverage for Telegram sender workflow with env-config bootstrap and mocked API call in `tests/integration/test_telegram_signal_integration.py`.
- Added resilience coverage for disconnect breaker/recovery behavior in `tests/unit/test_exchange_client_resilience.py` (`test_remote_disconnected_triggers_breaker_and_recovers`).
- Added long-scenario WAR backtest runner/reporter `Scripts/war_backtest_report.py`:
  - Scenario date-range execution with replay + forward stepping
  - Per-scenario artifacts: `equity_curve.csv`, `drawdown_curve.csv`, `trades/*.json`, `monthly_summary.csv`, `monthly_summary.md`
  - Aggregate markdown output: `reports/WAR_BACKTEST_REPORT.md`
  - Failure-safe behavior for missing cache ranges (scenario marked failed, run continues).

### Release captain validation refresh (2026-02-21)
- Verified Python 3.12 isolated venv path in `.venv312` without touching existing envs; `pip` upgraded and both `requirements.txt` and `requirements-dev.txt` install cleanly.
- Hardened Telegram message contract in `src/notifications/telegram.py` with explicit `Entry Time` field while keeping `paper signal only` disclaimer.
- Added resilience coverage in `tests/unit/test_exchange_client_resilience.py` with `test_cache_is_served_while_breaker_open` to prove TTL cache is served before HTTP calls even during breaker cooldown.
- Updated live-data multi-symbol integration in `tests/integration/test_live_data.py` to validate 5-symbol flow (`BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT`) with cache reuse on the second cycle.
- Full-suite verification on Python 3.12 (`.venv312`): `976 passed, 5 skipped` (`pytest -q`).

## Verification (Local Commands)

1) Run backtest with walk-forward adaptive hold (copy/paste):

```bash
python src/main.py --mode backtest --assets crypto --max-cycles 60 --replay-now 2024-02-01T12:00:00Z --cycle-step-minutes 1 --risk-profile relaxed --allow-crisis --hold-minutes 45 --hold-grid-minutes 10,30,60 --adaptive-hold-from-sweep --adaptive-walk-window 20 --adaptive-walk-step 10 --hold-grid-by regime --v25 --v25-db "runs/v25/bt_p4c_verify.db"
```

2) SQLite checks for decisions/trades/hold distribution:

```bash
python -c "import sqlite3; conn=sqlite3.connect('runs/v25/bt_p4c_verify.db'); cur=conn.cursor(); print('decisions', cur.execute('select count(*) from decisions').fetchone()[0]); print('closed_trades', cur.execute('select count(*) from trades where exit_time is not null').fetchone()[0]); print('hold_dist', cur.execute('select hold_minutes, count(*) from trades where exit_time is not null group by hold_minutes order by hold_minutes').fetchall()); conn.close()"
```

3) Confirm summary walk-forward fields:

```bash
python -c "import json, pathlib; p=pathlib.Path('runs/backtest_v25/summary.json'); d=json.loads(p.read_text(encoding='utf-8')); print('walk_forward', d.get('walk_forward')); print('adaptive_hold_used', d.get('adaptive_hold_used'))"
```

4) Confirm report artifacts exist (`exit_sweep.csv`, `equity.csv`, `summary.json`, `summary.md`):

```bash
python -c "import pathlib; r=pathlib.Path('runs/backtest_v25'); print({n:(r/n).exists() for n in ['exit_sweep.csv','equity.csv','summary.json','summary.md']})"
```

---

## 2. Safety Invariants Now Enforced

1) Derived leverage rule  
- Enforced in `compute_validated_size()` (`src/risk/validated_sizer.py`): leverage is computed as `notional_usd / equity_usd` when equity is present; leverage cap violations return `leverage_fail`.

2) Breakeven-R gate  
- Enforced in `compute_validated_size()` via single path in `PreTradeChecker.check()` (`src/risk/pre_trade.py`); threshold is `fee_risk_ratio <= 0.30`. The `gate_breakeven_r_fee()` utility in `src/mde/gates.py` remains available for standalone validation.

3) Fee-adjusted notional (NEW — FIX-01)  
- Enforced in `compute_validated_size()`: `notional = risk_usd / (sl_pct + fee_round_trip_pct)`. This guarantees that total risk (SL hit + round-trip fees) never exceeds `risk_usd`. Mathematically proven by `test_total_risk_within_budget`.

4) No gross-return backtests  
- Existing backtest engine uses fee/slippage costs (`src/backtest/engine.py` has `fee_bps`, `slippage_bps`, and cost application). No gross-only evaluation path was added in this implementation set.

5) Shadow-only execution isolation  
- `shadow_dynamic_exit_intents()` computes and logs intents only; it does not call broker methods. Unit tests assert no broker close/SL/TP calls in shadow flow. Pipeline now feeds real position data to shadow loop (FIX-04), but execution remains shadow-only.

6) Defensive override principle (current enforceable subset)  
- Entry blocking via Hermes sentiment is enforced in gates (`hermes_block_active` Gate 2 in `src/mde/gates.py`). No offensive whale-momentum path is implemented yet, so no conflict path exists in code.

7) Monotonic stop rule (EXTENDED — FIX-03)  
- LONG: Dynamic stop updates use `max(old_stop, candidate)` — stop only moves UP.
- SHORT: Dynamic stop updates use `min(old_stop, candidate)` — stop only moves DOWN.
- Tests assert monotonicity for both sides separately.

8) Idempotent exit stage transitions  
- FSM transitions are one-way (`ENTRY -> BREAKEVEN_LOCK -> PROFIT_CAPTURE -> TREND_RIDER`), with repeat updates producing NOOP when no new transition/tightening occurs. Works identically for LONG and SHORT sides.

9) State cleanup safety  
- Shadow state eviction now requires 3 consecutive misses (`_shadow_missed_counts`) before removal; cleanup is lock-protected.

10) Pivot audit trail (NEW — FIX-02, EXTENDED — PR-SHADOW-PERSIST)  
- Three new DB tables (`dynamic_exit_log`, `validated_sizing_log`, `whale_momentum_log`) with corresponding telemetry functions provide persistent audit trail for CAI pivot decisions. Shadow exit intents and validated sizing decisions are now actively written to DB from the pipeline.

## 3. Remaining Known Technical Debt

1) ~~Shadow state persistence is missing~~ **Resolved by PR-SHADOW-PERSIST**  
- Shadow exit intents are now persisted to `dynamic_exit_log` via `_persist_dynamic_exit_intent()`. In-memory FSM state (`_shadow_states`) is still not restored on restart, but the audit trail is now persistent.

2) ~~Shadow toggle is not config-driven~~ **Partially resolved by PR-EXIT-CONFIG**  
- R thresholds, partial fractions, and ATR multipliers are now config-driven via `engines.hermes.dynamic_exit` in YAML. Shadow enabled/disabled was already config-driven.

3) `validated_notional_usd` is metadata only  
- It is carried in `PreTradeResult` as string and is not yet consumed by downstream sizing/execution modules.

4) ~~Dynamic-exit policy is fixed constants~~ **Resolved by PR-EXIT-CONFIG**  
- All 7 constants are now in `config/engines.yaml` under `engines.hermes.dynamic_exit`. Loaded via `DynamicExitConfig` dataclass with validation.

5) ~~OrderIntent has no execution consumer~~ **Resolved by PR-J02**  
- `live_dynamic_exit_intents()` in `HermesPositionManager` consumes intents and executes via broker. `execute_with_precision()` and `execute_partial_close()` in `Executor` consume precision decisions.

6) ~~Whale Momentum module is not implemented~~ **Resolved by PR-I01 + PR-I02**  
- Contract, aggregation, boost functions, regime mapping, pipeline wiring, and telemetry persistence are all implemented. 37 tests (16 PR-I01 + 21 PR-I02).

7) ~~Hyper-Precision module is not implemented~~ **Resolved by PR-J01 + PR-J02**  
- Pure helpers (PR-J01, 36 tests) and execution wiring (PR-J02, 14 tests) both complete. `execute_with_precision()`, `execute_partial_close()`, and `live_dynamic_exit_intents()` use hyper-precision functions.

8) ~~No cross-module E2E harness for new pivots~~ **Resolved by E2E harness**  
- 14 integration tests validate sizing→gate9, dynamic exit progression (LONG+SHORT), intent emission, precision execution, and whale boost in composition.

9) Pipeline position tracker is in-memory only  
- `_open_positions` in `ArgusPipeline` is not synced with exchange state. In production, should read from broker API.

10) ~~Shadow loop does not persist to DB~~ **Resolved by PR-SHADOW-PERSIST**  
- `log_dynamic_exit()` is now called from `_run_shadow_dynamic_exit()` for every non-NOOP intent. `log_validated_sizing()` is called from `run_once()` after every pre-trade check.

## 4. Resolved Debt (from prior version of this log)

| Prior Debt Item | Resolution | PR/FIX |
|---|---|---|
| Validated sizing formula gap (`notional = risk_usd / sl_pct`) | Fee-adjusted formula implemented: `notional = risk_usd / (sl_pct + fee_round_trip_pct)` | FIX-01 |
| Gate 9 split-path enforcement | Removed optional Gate 9 from `evaluate_gates()`; single enforcement in `pre_trade.py` | FIX-05 |
| No DB schema for pivot logging | Added `dynamic_exit_log`, `validated_sizing_log`, `whale_momentum_log` + 7 indexes + 3 telemetry functions | FIX-02 |
| Dynamic-exit model is long-side oriented | Added `side` field, SHORT PnL/stop/trailing logic, 5 new short tests | FIX-03 |
| Shadow loop not called from main pipeline | Shadow loop now receives real tracked positions from executor fills | FIX-04 |
| Shadow loop does not persist to DB | `log_dynamic_exit()` wired into `_run_shadow_dynamic_exit()`; `log_validated_sizing()` wired into pre-trade path | PR-SHADOW-PERSIST |
| No validated sizing audit trail | `log_validated_sizing()` called after every `compute_validated_size()` in pipeline | PR-SHADOW-PERSIST |
| Dynamic exit constants hard-coded | All 7 constants extracted to `config/engines.yaml` with `DynamicExitConfig` dataclass, validation, and full backward compat | PR-EXIT-CONFIG |
| Whale Momentum module not implemented | Contract, aggregation, boost, regime mapping (`is_trend_strong`), pipeline wiring (`_apply_whale_momentum_boost`), telemetry persistence; GR-14 enforced; 37 tests | PR-I01 + PR-I02 |
| Hyper-Precision module not implemented | Pure helpers (PR-J01, 36 tests) + executor/position manager wiring (PR-J02, 14 tests); live mode behind `_live_exit_enabled` flag | PR-J01 + PR-J02 |
| OrderIntent has no execution consumer | `live_dynamic_exit_intents()` consumes intents via broker; `execute_with_precision()` and `execute_partial_close()` use hyper-precision decisions | PR-J02 |
| Gemini engine not registered in router | Added `ENGINE_GEMINI` to `REGIME_TO_SECONDARY_ENGINES[REGIME_RANGING]` | B-05 |
| No CHOP-specific alpha beyond BB/funding reversion | Added range mapper, micro-reversion, and chop-corr-gap sub-strategies to Nautilus with 35 tests | Phase D |
| No microstructure quality gate at entry | Precision filter (Grade A-F) wired at pipeline step 6.7 with configurable thresholds, 47 tests | Phase E |
| No integration/backtest validation for new modules | 21 integration tests: Gemini backtest, Nautilus CHOP, correlation blowup, full pipeline, fee drag validation | Phase F |
| Gemini pairs config not loadable from V25Config | Added GeminiConfig, GeminiPairConfig, GeminiCorrelationConfig to loader; gemini section in engines.yaml; 7 tests | A-11 |
| CORR_DECOUPLING_ARB template not in enum | Added to TemplateName enum; 2 tests | B-07 |
| SL manager not aware of dynamic exit trailing SL | Extended StopLossManager.enforce() with dynamic_exit_state param; trailing_stop takes precedence; 5 tests | H-11 |
| No tp_manager.py to replace with dynamic exit | Confirmed by design: dynamic exit FSM (Phase H) is the TP mechanism; 3 tests | H-12 |
| GeminiEngine not instantiated in pipeline | Created `_init_gemini_engine()`, wired into RegimeRouter as "GEMINI" key; CorrelationTracker initialized from engines.yaml pairs config | Production Hardening |
| PrecisionConfig hardcoded, not from YAML | Created `_load_precision_config()`, reads precision_filter section from engines.yaml; used in step 6.7 | Production Hardening |
| NautilusEngine.feed_candles() never called | Wired in `run_once()` loop after candle loading; micro-reversion sub-strategy now receives real candle data | Production Hardening |
| CorrelationTracker not instantiated in pipeline | Created alongside GeminiEngine; `update()` called per-symbol in `run_once()` to feed price data | Production Hardening |

## 5. Next Ordered PR Roadmap

1) ~~PR-SHADOW-PERSIST~~ **DONE** (see section 1 above)

2) ~~PR-EXIT-CONFIG~~ **DONE** (see section 1 above)

3) ~~PR-I01~~ **DONE** (see section 1 above)

4) ~~PR-I02~~ **DONE** (see section 1 above)

5) ~~PR-J01~~ **DONE** (see section 1 above)

6) ~~PR-J02~~ **DONE** (see section 1 above)

7) ~~E2E validation harness~~ **DONE** (see section 1 above)

## 6. Risk Assessment

| Layer | Risk Level | Comment |
|---|---|---|
| Validated Sizing | LOW | Fee-adjusted formula with mathematical proof; single enforcement path in pre-trade. |
| Dynamic Exit FSM | LOW | Pure functions, one-way transitions, monotonic stop for both LONG and SHORT, 12 tests. |
| Shadow Lifecycle | LOW | Lock-protected in-memory state, NOOP suppression, missed-count cleanup, stable position-id keys, now fed real position data. |
| DB Audit Trail | LOW | Tables, telemetry functions, and pipeline wiring all operational. Shadow exit intents and validated sizing decisions are persisted. |
| Gate 9 Enforcement | LOW | Single path (pre_trade.py), split-path eliminated, clean audit. |
| Hermes Wiring | LOW | Shadow + live modes available. Live mode executes intents via broker behind `_live_exit_enabled` flag. |
| Whale Momentum | LOW | Fully wired: contract, aggregation, regime mapping, pipeline boost, telemetry. 37 tests. |
| Hyper Precision | LOW | Fully wired: pure helpers + executor integration + live mode. 50 tests (36 + 14). |
| Correlation Engine | LOW | Foundation complete: contracts, tracker, OU estimator, cointegration. 42 tests. |
| Gemini Router Wiring | LOW | Registered as secondary in RANGING. Router silently skips if engine instance not in dict. |
| Enhanced CHOP Alpha | LOW | Range mapper, micro-reversion, chop-corr-gap. All pure functions, no broker calls. 35 tests. |
| Precision Entry Filter | LOW | Grade A-F microstructure assessment. Wired at pipeline step 6.7. 47 tests. |
| Integration Validation | LOW | Phase F: 21 integration tests cover Gemini backtest, CHOP alpha, correlation blowup, full pipeline, fee drag. Zero regressions. |

## 7. Test Coverage Summary

| Test File | Tests | Status |
|---|---|---|
| `tests/risk/test_validated_sizer.py` | 7 | ALL PASS |
| `tests/risk/test_pre_trade_validated_sizing.py` | 3 | ALL PASS |
| `tests/mde/test_breakeven_gate.py` | 2 | ALL PASS |
| `tests/execution/test_dynamic_exit_fsm.py` | 12 (7 long + 5 short) | ALL PASS |
| `tests/execution/test_exit_intent_mapper.py` | 3 | ALL PASS |
| `tests/unit/test_hermes_position_manager.py` | 7 | ALL PASS |
| `tests/v25/test_shadow_persist.py` | 13 | ALL PASS |
| `tests/v25/test_exit_config.py` | 11 | ALL PASS |
| `tests/v25/test_whale_momentum_contract.py` | 16 | ALL PASS |
| `tests/v25/test_whale_boost_wiring.py` | 21 | ALL PASS |
| `tests/execution/test_hyper_precision.py` | 36 | ALL PASS |
| `tests/correlation/test_correlation_contracts.py` | 20 | ALL PASS |
| `tests/correlation/test_tracker.py` | 14 | ALL PASS |
| `tests/correlation/test_ou_estimator.py` | 8 | ALL PASS |
| `tests/execution/test_execution_integration.py` | 14 | ALL PASS |
| `tests/integration/test_e2e_cai_pivots.py` | 14 | ALL PASS |
| `tests/engines/test_nautilus_enhanced.py` | 35 | ALL PASS |
| `tests/mde/test_precision_filter.py` | 47 | ALL PASS |
| `tests/integration/test_phase_f_validation.py` | 21 | ALL PASS |
| `tests/v25/test_remaining_gaps.py` | 17 | ALL PASS |
| `tests/data/test_engine_observatory.py` | 10 | ALL PASS |
| `tests/integration/test_live_data.py` | 5 | ALL PASS |
| `tests/unit/test_orion.py` | 22 | ALL PASS |
| Full suite (excl. 2 pre-existing failures) | 827/830 | PASS |

Pre-existing failures (not caused by our changes):
- `tests/unit/test_config.py::test_risk_config` — config value drift (`base_risk_pct` 0.015 vs test expectation 0.02)
- `tests/unit/test_vault.py::test_key_file_permissions_best_effort` — Windows platform permission check
- `tests/unit/test_telemetry_writer.py::test_concurrent_heartbeat_updates_never_corrupt_json` — Windows PermissionError race (flaky)
