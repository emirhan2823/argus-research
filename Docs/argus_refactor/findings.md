# ARGUS Audit Findings (2026-03-15)

## 1. Config/Code Drift (CRITICAL)

### Detected Drift

| Parameter | engines.yaml | config.py Default | engine.py Default | Active Value | Impact |
| --- | --- | --- | --- | --- | --- |
| TITAN min_adx | 35 | 25.0 | 22.0 | 22.0 (config ignored) | TITAN uses lower threshold than intended |
| TITAN continuation_min_volume | 0.8 | 1.2 | 1.2 | 0.8 (config read) | Correct -- config wins |
| TITAN adx_rising_bars | 1 | 3 | 3 | 1 (config read) | Correct -- config wins |
| HYDRA min_confidence | 0.60 | N/A (no model) | 0.55 | 0.55 (config ignored) | HYDRA accepts lower-confidence signals than intended |
| NAUTILUS max_adx | 25 | 22.0 | 25.0 | 25.0 (config ignored) | Pydantic default wrong but engine correct |

### Root Cause

`EnginesConfig` only has pydantic models for: titan, nautilus, phoenix, hermes, atlas, confluence_filter.

Missing typed models for: HYDRA, AEGEAN, POSEIDON, GEMINI, precision_filter, trade_quality, adaptive_confidence.

Engine constructors are called with zero or minimal config params:
- POSEIDON: `PoseidonEngine()` -- zero params
- AEGEAN: `AegeanEngine()` -- zero params
- HYDRA: `HydraEngine()` -- zero params (inline in router dict)
- NAUTILUS: `NautilusEngine()` -- zero params
- HERMES: `HermesEngine()` -- zero params
- TITAN: `TitanEngine(min_volume_expansion=..., adx_rising_bars=...)` -- 2 of 14 params
- GEMINI: fully config-driven (3/3 params)

## 2. Dead Code: PHOENIX Engine

PHOENIX is imported but never instantiated. Full reference inventory in `Docs/argus_refactor/phoenix_quarantine.md`.

Key impact: `gates.py:103` allows only PHOENIX at RSL level >= 2, effectively blocking ALL signals at RSL 2 (since PHOENIX never produces signals).

## 3. RSL2 Gate Bug

**Location:** `src/mde/gates.py:103`

**Current behavior:** At RSL level >= 2, only ENGINE_PHOENIX is allowed through the gate. Since PHOENIX is never instantiated, no signals pass.

**Expected behavior:** At RSL 2 (defensive mode), conservative/safe engines should still be allowed to trade.

**Fix options (for future phase):**
- A) Replace PHOENIX with POSEIDON (most conservative single-engine approach)
- B) Expand to MR engine set: POSEIDON + NAUTILUS + HYDRA (defensive = MR only, no trend)
- C) Remove the line entirely (RSL 3+ already blocks everything)

## 4. Working vs Broken Components

### Working

- **POSEIDON:** 9-indicator MR consortium, validated exit behavior (trailing disabled), active in VOLATILE + RANGING. Most sophisticated engine.
- **AEGEAN:** Hybrid RSI + MOM-LRC, active in all regimes as confirmation engine. Produced 84 trades in Bull 2024 backtest.
- **NAUTILUS:** Ranging MR specialist (BB + funding + micro reversion). Active in RANGING.
- **HYDRA:** Scalping engine (BB + RSI). Active in RANGING.
- **HERMES:** Sentiment overlay, veto and position management. Active.
- **GEMINI:** Pairs trading (correlation). Optional, fully config-driven.
- **Filter chain:** Well-centralized in src/mde/, 6 independent modules + gates.
- **Regime system:** Rule-based + validator + state machine with hysteresis. Working correctly.
- **SONAR scanner:** Multi-exchange universe discovery, trend scoring, top-2 allocation. Working but basic.

### Broken/Degraded

- **TITAN:** Active but produces ZERO trades. Root cause: regime TRENDING requires ADX >= 32 + Hurst >= 0.58 (only 14.4% of time), then TITAN's 7-condition continuation funnel + pullback requirement reject 97%+ of remaining signals.
- **PHOENIX:** Dead code -- never instantiated, quarantined.
- **Config binding:** 5 of 7 active engines have zero config binding.
- **Paper/live time-exit:** Not implemented (backtest has it).

## 5. Performance Data (from existing backtest artifacts)

### AEGEAN-Only Performance (from profitability-findings.md)

| Scenario | Return | PF | Notes |
| --- | --- | --- | --- |
| Luna Crash | +21.70% | 1.86 | Best scenario for MR |
| Bear 2022 | +1.07% | 1.01 | Marginal |
| COVID Crash | -42% | N/A | Struggles in crash TRENDING |
| Bull 2024 | -26% | N/A | Shorts in uptrend cause losses |

### Bull 2024 Full Pipeline (AEGEAN + no TITAN)

- BTC/ETH combined: -146.65% total return
- LONG: -59.33%, SHORT: -87.32%
- 84 AEGEAN trades, 0 TITAN trades
- Regime distribution: TRENDING 14.4%, RANGING 69.9%, VOLATILE 15.7%

### Key Observations

- No POSEIDON-specific backtest data available in existing artifacts (POSEIDON was added later and hasn't been backtested in isolation)
- No NAUTILUS or HYDRA specific backtest data available
- TITAN has never produced trades in any pipeline run
- AEGEAN is the only engine with meaningful trade history

## 6. Overfitting Risks

- Luna-crash toxic patterns in signal_quality.py are scenario-specific penalties that may hurt performance in other scenarios
- Filter chain 9-stage cascade can compound small penalties into large rejections
- Exit configs are hardcoded per-engine, not validated via walk-forward
- No systematic OOS testing for current parameter values

## 7. Code Quality Risks

- main.py at ~4862 lines is a significant maintenance burden
- 3-layer orchestration (EngineOrchestrator + Orion + Router) has overlapping responsibilities
- Engine-specific logic scattered in main.py instead of encapsulated in engines
- Some inline imports inside functions (e.g., confluence_filter at line 1273)
