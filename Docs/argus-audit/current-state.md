# ARGUS Current State

Last verified: 2026-03-15 against feature/phase19-5-observability-ui branch HEAD.

## Findings

### STILL OPEN

**SO-1: Paper/Live Exit Parity Gap**
Confidence: HIGH (verified 2026-03-15)
Backtest enforces per-engine time-exit via ENGINE_EXIT_CONFIGS (HYDRA 6 bars, NAUTILUS 12, AEGEAN 8, POSEIDON 24). Paper/live execution has zero time-exit mechanism — no code in src/execution/executor.py, paper_execution.py, or dynamic_exit.py handles time-based position closure. Losing MR trades can remain open indefinitely in paper/live.
Files: src/backtest/exit_policy.py:67-88, src/execution/executor.py, src/main.py (no time-exit in live path)

**SO-2: TITAN Zero-Trade in Real Pipeline**
Confidence: HIGH (verified via Bull 2024 backtest, 2026-03-14)
TITAN produces zero trades in full pipeline backtest (Bull 2024). Real pipeline regime distribution: TRENDING only 14.4% of candles. Within TRENDING, continuation funnel rejects at multiple stages (ADX 37.6%, ADX rising 37.8%, pullback 97%). Forced-TRENDING diagnostic shows TITAN can generate signals when regime is bypassed.
Files: src/engines/titan/engine.py, src/regime/rule_based.py:116-127

**SO-3: Regime Classification Strictness**
Confidence: HIGH (verified 2026-03-15)
TRENDING requires ADX>=32 AND Hurst>=0.58 AND directional alignment (EMA21/MA200 agree). These thresholds are hardcoded in src/regime/rule_based.py:55-56 (constructor defaults). Only 14.4% of Bull 2024 candles qualify.
Files: src/regime/rule_based.py:55-56, 116-127

**SO-4: Luna-Crash Toxic Patterns in Signal Quality**
Confidence: HIGH (verified 2026-03-15)
Five "toxic patterns" in signal_quality.py (lines 390-422) are explicitly labeled as derived from luna_crash analysis. Three of five target shorts specifically:
- Pattern 1: short + volume_ratio > 2.0 → -0.15
- Pattern 3: short + ADX > 40 + vol > 2.0 → -0.10
- Pattern 5: short + ADX 25-40 → -0.08 (penalizes ALL shorts in medium-trend zones)
These are applied universally, not scenario-gated. Separate from the 6 general penalties (alignment -0.10, divergence -0.12, etc.) which are not luna-crash specific.
Files: src/mde/signal_quality.py:390-422

### PARTIALLY OPEN

**PO-1: Config-Code Disconnect**
Confidence: HIGH (verified 2026-03-15)

Progress: TITAN now has 2 fields config-driven (continuation_min_volume, adx_rising_bars) via config.py + main.py wiring. trade_quality.allow_grade_c_in_crypto correctly loaded from YAML.

Still disconnected:
- Engine min_confidence: No engine constructor receives min_confidence from YAML. Code defaults used at runtime. Known drift: AEGEAN code=0.52 vs YAML=0.55, HYDRA code=0.55 vs YAML=0.60. POSEIDON has no YAML section (hardcoded 0.50). TITAN and NAUTILUS happen to align at 0.55 but are not wired.
- TITAN: trend_follow, breakout, partial_tp YAML sections → NOT READ by any Python code
- TITAN: exit_system → Pydantic model exists (TitanExitConfig) but NOT passed to TitanEngine constructor
- NAUTILUS: bb_reversion, funding_reversion, micro_reversion → NOT READ (engine uses hardcoded values)
- NAUTILUS: chop_corr_gap → code module exists but no config binding from YAML
- AEGEAN: channel_multipliers, rsi_smooth_spans, atr_stop_multipliers, rr_ratios → YAML IGNORED, engine uses hardcoded dicts (lines 46-86 in aegean/engine.py)

Files: src/core/config.py:108-117, src/main.py:339-343, config/engines.yaml

**PO-2: Directional Bias Short Suppression**
Confidence: HIGH (verified 2026-03-15)
Non-MR engines (TITAN, AEGEAN, GEMINI, PHOENIX, HERMES) receive x0.45 confidence multiplier when counter-trend in moderate ADX (>20). Hard reject at strong ADX (>30). MR engines (POSEIDON, NAUTILUS, HYDRA) are exempt. This is aggressive but intentional for trend protection. Whether the x0.45 level is optimal is an open question.
Files: src/main.py:966-1050 (directional bias section)

### RESOLVED

**R-1: PHOENIX Leak** (2026-03-04)
PHOENIX was generating 223-692 spurious trades per scenario via 3 bugs. Fixed: removed from router, Orion ALL_ENGINES, and engine fallback.

**R-2: Trailing Stop MR Destruction** (2026-03-02)
Trailing stops destroy MR edge (WR 53%->32%, PF 1.025->0.420). ENGINE_EXIT_CONFIGS set trailing_enabled=False, be_lock_enabled=False for all MR engines.

**R-3: Trade Quality Grade C Crypto** (resolved in current YAML)
allow_grade_c_in_crypto set to true in engines.yaml:235 and correctly loaded via _load_trade_quality_config(). Code default is False but YAML override is active.

### NEEDS RE-VALIDATION

**NR-1: Cascading Filter Strangulation Total Impact**
Previous audit estimated max cumulative penalty of -0.48 confidence from signal quality alone. With allow_grade_c_in_crypto now true (R-3), the effective rejection rate may have changed. The 6 general penalties and 5 toxic patterns are confirmed active, but actual trade pass-through rate needs a fresh backtest to measure. Regime alignment multipliers are also confirmed: POSEIDON x0.90, NAUTILUS/HYDRA x0.70 in TRENDING (not x0.45 as previously stated — that's directional bias).
Files: src/mde/signal_quality.py, src/mde/regime_alignment.py

**NR-2: Engine min_confidence Effective Impact**
AEGEAN (0.52 vs 0.55) and HYDRA (0.55 vs 0.60) have known drift between YAML and code. Code values are used at runtime. Whether this drift causes material trade count differences has not been measured. Could be neutral (few signals near threshold) or significant.

## Architecture Notes
- Pipeline: 8 engines, 9-stage filter chain, 10 gates
- Regime distribution (Bull 2024 scenario): TRENDING 14.4%, RANGING 69.9%, VOLATILE 15.7%
- ENGINE_EXIT_CONFIGS (backtest only): HYDRA 6 bars, NAUTILUS 12, AEGEAN 8, POSEIDON 24, TITAN unlimited+trailing
- Regime classifier: rule-based with consensus voting; default=RANGING when no majority

## Current Bottlenecks
- TITAN continuation funnel: 7 AND conditions with 97% pullback rejection at end
- Regime strictness: only 14.4% TRENDING in Bull 2024 limits TITAN opportunity
- Filter chain: cascading penalties from multiple stages can reduce borderline confidence below engine thresholds

## Current Risks
- Backtest/paper exit mismatch may cause paper results to diverge from backtest expectations
- Luna-crash toxic patterns penalize shorts universally (not just luna-like conditions)
- Config YAML changes to dead sections have no runtime effect — misleading for operators
