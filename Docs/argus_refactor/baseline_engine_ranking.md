# Baseline Engine Ranking — Evidence-Based (2026-03-16)

## Methodology

Isolated engine backtests using `--force-engine` flag (added in Phase 1). Each engine was forced as the sole active engine via orchestrator override. Full pipeline filters (signal quality, precision, confluence, trade quality, gates) remained active.

Data: BTC/ETH 15m parquets, 1h timeframe, normal risk profile, 500-bar OHLCV limit.

## CRITICAL FINDING: Only AEGEAN Produces Trades

| Engine | Tested Periods | Total Trades | Status |
| --- | --- | --- | --- |
| **AEGEAN** | Luna 2022, Bear 2022, COVID 2020, Bull 2024 | 100+ | **ONLY engine producing trades** |
| POSEIDON | Luna 2022, Bear 2022, Jun-Aug 2023 | **0** | Zero signals generated |
| NAUTILUS | Jun-Aug 2023 (500 cycles) | **0** | Zero signals generated |
| HYDRA | Jun-Aug 2023 (500 cycles) | **0** | Zero signals generated |
| TITAN | All prior tests | **0** | Zero signals (known — regime funnel) |

**Root cause for zero-trade engines:**
- **POSEIDON:** 9-indicator consortium requires extreme readings (BB %B < 0.15, RSI < 30, etc.) that rarely co-occur on 1h BTCUSDT/ETHUSDT. The consortium voting threshold (NORMAL grade requires >= 45% score) means multiple indicators must agree simultaneously.
- **NAUTILUS:** BB reversion + funding + micro strategies require very specific ranging conditions (ADX < 25) that conflict with actual regime detection.
- **HYDRA:** Scalping thresholds too tight for 1h timeframe (designed for lower TF).
- **TITAN:** Known — regime funnel + pullback rejection cascade.

## AEGEAN Isolated Backtest Results

| Scenario | Period | Trades | WR% | PnL% | MaxDD% | PF | Avg Win | Avg Loss | Expectancy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Luna Crash** | May-Jul 2022 | 16 | 43.8% | **+1.87%** | -0.62% | **3.10** | $39.42 | -$9.90 | +$11.68 |
| **Bear 2022** | Jan-Dec 2022 | 69 | 34.8% | **+0.22%** | -2.18% | **1.04** | $23.28 | -$11.93 | +$0.32 |
| **COVID Crash** | Feb-May 2020 | 24 | 50.0% | **-0.04%** | -1.04% | **0.97** | $13.89 | -$14.25 | -$0.18 |
| **Bull 2024** | Jan-Dec 2024 | 90 | 47.8% | **+4.52%** | -1.43% | **1.81** | $23.52 | -$11.89 | +$5.03 |

### Key Observations

1. **Bull 2024 is now the strongest scenario**: PF 1.81, +4.52% across 90 trades — surprising reversal from prior -146.65% finding
2. **Luna Crash strong**: PF 3.10, best per-trade edge ($11.68 avg) but low trade count (16)
3. **Bear 2022 marginal**: PF 1.04, barely profitable across 69 trades — edge exists but thin
4. **COVID Crash neutral**: PF 0.97, 50% WR — effectively random; no edge in crisis conditions
5. **Aggregate**: 199 trades across 4 scenarios, net +6.57%, weighted PF ~1.5

### Bull 2024 Discrepancy with Prior Findings

Prior profitability-findings.md reported -146.65% on Bull 2024. Current isolated test shows +4.52%.

Possible explanations:
- Prior test may have included multi-engine interference (AEGEAN as confirmation-only for TITAN)
- Phase 1 config binding changes (HYDRA min_confidence 0.55→0.60, AEGEAN now receives config params)
- Prior test may have used different filter settings or ORION orchestrator
- Different risk profile or symbol set

**This discrepancy should be investigated** but does not invalidate the current isolated result.

## Engine Status Summary

### AEGEAN — Current Sole Working Engine

**Verdict: KEEP as production baseline (by default — it's the only option)**

Strengths:
- Only engine that produces trades in the full pipeline
- Profitable in crash/volatile scenarios (Luna +1.87%, PF 3.10)
- Adapts to multiple regimes via RSI + MOM-LRC channel switching

Weaknesses:
- Marginal in bear markets (PF 1.04)
- Expected to lose heavily in bull markets (shorts in uptrend)
- Thin statistical edge (24-69 trades per year)
- Not a "golden baseline" — it's a survival baseline

### POSEIDON — Architecture-Only, Zero Performance

**Verdict: CANNOT be baseline. Zero trades = zero evidence.**

The sophisticated 9-indicator consortium is elegant but non-functional in the full pipeline. The signal generation threshold is too strict — individual indicator votes rarely combine to produce a sufficient consensus score.

**Required to activate:** Either (a) lower consortium thresholds significantly, or (b) test on lower timeframes (15m/5m) where extreme readings are more common, or (c) redesign the voting threshold system.

### TITAN — Zero Trades, Known Issue

**Verdict: QUARANTINED from ranking until activated**

Needs: regime threshold relaxation (ADX/Hurst), pullback tolerance increase, or fundamental signal path redesign.

### NAUTILUS, HYDRA — Zero Trades

**Verdict: QUARANTINED from ranking until activated**

Likely same class of problem as POSEIDON — thresholds too strict for 1h BTC/ETH.

## RSL2 Gate Bug Impact on Ranking

The RSL2 gate bug (PHOENIX-only gate) does NOT invalidate these ranking conclusions because:
1. None of the tested scenarios triggered RSL level 2 (all ran at RSL 0)
2. Even if RSL2 were reached, it would only block signals — it wouldn't generate false trades

## Recommendations

### Immediate Priority

1. **AEGEAN is the baseline by elimination**, not by excellence. Accept this reality.
2. **Investigate POSEIDON activation** — the 9-indicator consortium might work with:
   - Lower grade thresholds (NORMAL from 45% to 35%)
   - Lower individual indicator extremity requirements
   - 15m timeframe testing
3. **TITAN activation** should follow POSEIDON investigation — same class of problem.

### Next Steps

| Priority | Action | Rationale |
| --- | --- | --- |
| 1 | POSEIDON threshold analysis | Determine minimum viable thresholds for trade generation |
| 2 | TITAN pullback tolerance + regime threshold | Only trend engine, critical for bull markets |
| 3 | RSL2 gate bug fix | Correctness issue, blocks all signals at RSL 2 |
| 4 | main.py decomposition | Architecture hygiene, does not affect trading behavior |
| 5 | Walk-forward validation | Validate AEGEAN's thin edge with proper OOS testing |

### Whether TITAN Zero-Trade Should Be Investigated Next

**YES.** TITAN is the only trend-following engine. In Bull 2024 (the scenario where AEGEAN loses most heavily due to short bias), TITAN could provide critical diversification. Activating TITAN is likely the highest-impact single change for overall system performance.

### Whether main.py Decomposition Should Begin Immediately

**NO.** Decomposition is architecture hygiene. The urgent problem is that 4 of 5 engines produce zero trades. Fix the signal generation bottleneck first, then decompose the pipeline.
