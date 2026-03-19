# Experiment Log

Historical record of experiments run on the ARGUS system. Each entry captures the change, scope, result, and interpretation at time of running. Results are point-in-time and may not reflect current system state if code has changed since.

---

## EXP-001: TITAN ADX Rising Bars Relaxation
- **Date:** 2026-03-14
- **Goal:** Unblock TITAN by reducing adx_rising_bars from 3 to 1
- **Change:** config/engines.yaml `adx_rising_bars: 1`, added field to src/core/config.py TitanConfig, wired in src/main.py
- **Scope:** TITAN continuation chain only (isolated, no other changes)
- **Result (forced-TRENDING diagnostic):** Signal count 17→21 (+24%), PASS count +35%
- **Result (real pipeline, Bull 2024):** ZERO change — identical 84 AEGEAN trades, 0 TITAN trades
- **Interpretation:** ADX rising alone is insufficient. The real blockers are pullback rejection (97%) and regime classification (only 14.4% TRENDING). ADX rising was not the binding constraint.
- **Next step:** Parked — user pivoted to full audit before proceeding to Faz 2 (min_adx) or Faz 3 (pullback tolerance)

## EXP-002: Volume Threshold Diagnostic
- **Date:** 2026-03-14
- **Goal:** Check if continuation_min_volume blocks TITAN
- **Change:** config/engines.yaml `continuation_min_volume: 0.8` (from default 1.2)
- **Scope:** TITAN continuation volume gate only
- **Result:** Volume accounts for only 1.5% of rejections in diagnostic funnel
- **Interpretation:** Volume is not a meaningful bottleneck at any tested threshold. Confirmed non-blocker.
- **Next step:** No action needed on volume

---

## Experiment Branch State

The following experiment values are **currently active on the feature/phase19-5-observability-ui branch** (verified 2026-03-15 against current HEAD):

| Parameter | Baseline default | Current YAML value | Status |
|-----------|-----------------|-------------------|--------|
| adx_rising_bars | 3 (config.py default) | 1 (engines.yaml:8) | **Experiment value — not reverted** |
| continuation_min_volume | 1.2 (config.py default) | 0.8 (engines.yaml:7) | **Experiment value — not reverted** |
| allow_grade_c_in_crypto | False (code default) | true (engines.yaml:235) | **Set in YAML — status unclear (experiment or intentional?)** |

These values are on the current working branch. If merging to main, decide whether to keep experiment values or revert to baseline defaults.

---

## Planned Experiments (not yet executed)

### PLAN-A: Grade B Threshold Reduction
- **Goal:** Reduce grade_b_threshold from 0.65 to 0.58 to allow more borderline signals
- **Change:** config/engines.yaml → trade_quality.grade_b_threshold: 0.58
- **Rationale:** Composite 0.58-0.64 signals have passed 5/6 factors — likely not "bad" trades
- **Status:** Awaiting user decision
- **Dependency:** Independent, can run alongside other experiments

### PLAN-B: Signal Quality Penalty Reduction
- **Goal:** Reduce cascading confidence penalties by ~40% to soften filter chain
- **Change:** Code change in src/mde/signal_quality.py — reduce 6 general penalty magnitudes
- **Rationale:** Penalties independently reduce confidence which cascades through downstream filters
- **Status:** Awaiting user decision — may be unnecessary if PLAN-A results are sufficient
- **Dependency:** Better to measure after Grade C/B changes to isolate attribution

### PLAN-C: Paper Time-Exit Enforcement
- **Goal:** Add per-engine time-exit to paper/live execution for backtest parity
- **Change:** Code change in src/main.py or src/execution/
- **Rationale:** Correctness fix — backtest assumes time-exit, paper/live doesn't enforce it
- **Status:** Awaiting user decision on deployment strategy
- **Dependency:** Independent of filter chain experiments

### PLAN-D: TITAN Activation (multi-step)
- **Goal:** Get TITAN producing trades in real pipeline
- **Steps:** Faz 2 (min_adx reduction), Faz 3 (pullback tolerance), regime threshold review
- **Status:** Parked after Faz 1 showed isolated ADX rising change insufficient
- **Dependency:** Needs user decision on min_adx intent (YAML 35 vs code 22) first
