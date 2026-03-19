# BTC/ETH Profitability Analysis

## Scope & Caveats
All performance numbers below are from **specific backtest scenarios** with specific configurations. They represent point-in-time measurements, not general system truths. Results are sensitive to regime distribution, filter settings, and engine parameters active at time of testing.

## Bull 2024 Scenario (current tested setup, as of 2026-03-14)

Configuration at time of test:
- Engines: POSEIDON (primary MR), TITAN v2 (primary trend), AEGEAN (confirmation-only)
- Filter chain: full 9-stage pipeline active
- adx_rising_bars: 1 (experiment value), continuation_min_volume: 0.8 (experiment value)
- allow_grade_c_in_crypto: true (YAML setting)

Results:
- BTC/ETH combined: -146.65% total return
- LONG: -59.33%, SHORT: -87.32%
- Trade breakdown: 84 AEGEAN trades, 0 TITAN trades
- Regime: TRENDING 14.4%, RANGING 69.9%, VOLATILE 15.7%

Note: These results reflect AEGEAN-only performance since TITAN produced zero trades. TITAN activation would change results significantly.

## Other Scenario Reference Points (from earlier testing rounds)
- Luna Crash (AEGEAN-only): +21.70%, PF 1.86 — best scenario for MR
- Bear 2022 (AEGEAN-only): +1.07%, PF 1.01 — marginal
- COVID crash: -42% — AEGEAN struggles in crash-TRENDING regime
- Bull 2024 (AEGEAN-only, earlier round): -26% — shorts in bull cause losses

These are from different configuration snapshots and may not be directly comparable.

## Root Causes (ranked by estimated impact)

### 1. TITAN Inactivity (HIGHEST IMPACT)
TITAN v2 is designed for TRENDING regime but produces zero trades in real pipeline. This means the system has no trend-following capability in production. In a Bull 2024 scenario, this forces all trading through MR engines which are structurally disadvantaged in sustained uptrends.

Contributing factors:
- Regime classification strict: ADX>=32 + Hurst>=0.58 → only 14.4% TRENDING
- Continuation funnel: 7 AND conditions (ADX, ADX rising, EMA alignment, MA200 alignment, structure, ATR percentile, volume) each independently rejects
- Pullback requirement: 97% of signals surviving all 7 conditions fail pullback check
- TITAN min_adx: YAML says 35, engine hardcodes 22 — intent unclear, neither value tested in full pipeline

### 2. Filter Chain Over-Rejection (HIGH IMPACT)
Nine-stage pipeline applies cascading penalties. Cumulative effect can reduce a 0.70 initial confidence to below engine thresholds:
- Signal quality: 6 general penalties (max -0.48 total) + 5 luna-crash toxic patterns (max -0.55 additional for shorts)
- Directional bias: x0.45 for non-MR counter-trend signals (ADX>20), hard reject at ADX>30
- Regime alignment: NAUTILUS/HYDRA x0.70 in TRENDING, POSEIDON x0.90
- Trade quality: Grade C rejection was active (now resolved — allow_grade_c_in_crypto: true)

Impact partially mitigated by R-3 (Grade C crypto enable). Full impact needs re-measurement.

### 3. Paper/Live Time-Exit Gap (MEDIUM IMPACT, correctness issue)
Not a direct profitability cause in backtest, but backtest results cannot be replicated in paper/live because MR time-exits (6-24 bars) are not enforced. This means paper performance will diverge from backtest projections.

### 4. Short-Side Disadvantage in Bull Markets (MEDIUM, partially market-driven)
Bull 2024: SHORT -87.32% vs LONG -59.33%. Three amplifying factors:
- Inherent bull market disadvantage for shorts (market-driven, not fixable)
- Luna-crash toxic patterns penalize shorts -0.08 to -0.15 (code-driven, fixable)
- Directional bias x0.45 suppresses counter-trend signals (intentional, tunable)

## Prioritized Hypotheses for Improvement

| # | Hypothesis | Type | Risk | Dependency |
|---|-----------|------|------|------------|
| 1 | Grade C crypto enable | YAML-only | Low | **Already applied** (engines.yaml:235) — needs backtest validation |
| 2 | Grade B threshold 0.65 to 0.58 | YAML-only | Low | Independent |
| 3 | Signal quality penalty reduction (~40%) | Code change | Medium | Independent, measure after #1-2 |
| 4 | Paper time-exit enforcement | Code change | Low (correctness fix) | Independent |
| 5 | TITAN min_adx clarification + regime threshold | Config+code | Medium | Needs user decision on intent |
| 6 | Luna-crash toxic pattern review | Code change | Medium | Independent |

## Open Questions (need user decision before implementation)
1. TITAN min_adx intent: YAML 35 vs engine code 22 — which represents the desired behavior?
2. Engine min_confidence: standardize on YAML values or keep code defaults?
3. Directional bias x0.45: keep as-is, relax to x0.60, or make config-driven?
4. Filter chain approach: relax one stage at a time (bottom-up) or simplify/remove stages (top-down)?
5. Dead YAML config sections: are these a future roadmap to be wired, or abandoned specs to be cleaned up?
6. Luna-crash toxic patterns: keep, soften, or gate behind a scenario flag?
