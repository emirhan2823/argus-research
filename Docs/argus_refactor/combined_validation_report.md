# Combined Validation Report: AEGEAN vs TITAN vs Combined (2026-03-16)

## Methodology

- **Fixed-size position sizing** (--no-compound): All backtests use initial_balance ($10,000) for sizing, eliminating compounding distortion
- **Isolated engine mode** (--force-engine): AEGEAN and TITAN tested in isolation
- **Combined mode** (--force-engines AEGEAN,TITAN): Both engines active as standalone (no confirmation-only)
- **4 scenarios**: Luna Crash 2022, Bear 2022, Bull 2024, COVID Crash 2020
- **Symbols**: BTCUSDT, ETHUSDT
- **Timeframe**: 1h candles
- **Fees**: 0.04% taker

## Results

### Full Comparison Table

| Scenario | Config | Trades | WR% | PnL% | MaxDD% | PF | Expectancy% | Long | Short |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Luna 2022 | AEGEAN | 13 | 61.5% | -0.01% | -0.05% | 0.78 | -0.0009% | - | - |
| Luna 2022 | TITAN | 16 | 50.0% | +0.04% | 0.00% | 30.08 | +0.0024% | - | - |
| Luna 2022 | **Combined** | **25** | **56.0%** | **+0.01%** | **-0.05%** | **1.16** | **+0.0003%** | 12 | 13 |
| Bear 2022 | AEGEAN | 76 | 52.6% | -0.17% | -0.22% | 0.34 | -0.0023% | - | - |
| Bear 2022 | TITAN | 46 | 52.2% | +0.14% | 0.00% | 80.56 | +0.0031% | - | - |
| Bear 2022 | **Combined** | **112** | **52.7%** | **-0.10%** | **-0.15%** | **0.55** | **-0.0009%** | 42 | 70 |
| Bull 2024 | AEGEAN | 80 | 63.7% | +2.79% | -0.08% | 30.10 | +0.0349% | - | - |
| Bull 2024 | TITAN | 40 | 55.0% | +1.54% | -0.05% | 15.96 | +0.0385% | - | - |
| Bull 2024 | **Combined** | **111** | **61.3%** | **+3.91%** | **-0.06%** | **31.64** | **+0.0352%** | 67 | 44 |
| COVID 2020 | AEGEAN | 26 | 46.2% | -0.10% | -0.11% | 0.14 | -0.0040% | - | - |
| COVID 2020 | TITAN | 7 | 57.1% | +0.00% | -0.01% | 1.04 | +0.0001% | - | - |
| COVID 2020 | **Combined** | **32** | **50.0%** | **-0.10%** | **-0.11%** | **0.24** | **-0.0032%** | 12 | 20 |

### Aggregate Summary

| Config | Total Trades | Net PnL% | Positive Scenarios | Best Scenario |
| --- | --- | --- | --- | --- |
| AEGEAN only | 195 | +2.51% | 1/4 (Bull only) | Bull +2.79% |
| TITAN only | 109 | +1.72% | 3/4 (all except COVID ~0) | Bear +0.14% |
| **Combined** | **280** | **+3.72%** | **2/4** | **Bull +3.91%** |

## Key Findings

### 1. TITAN is the more consistent engine

TITAN achieves positive or breakeven PnL in **all 4 scenarios** (worst case: COVID +0.00%). AEGEAN is profitable only in Bull 2024 but produces more trades.

### 2. Combined mode produces genuine additive value

**Bull 2024 combined (+3.91%) > AEGEAN alone (+2.79%) + TITAN alone (+1.54%)**

This is NOT simple addition -- the combined PnL is close to AEGEAN+TITAN sum (4.33%) but slightly lower due to max concurrent position limits (3). The combined mode captures opportunities from both engines without significant cannibalization.

### 3. Bear market remains the weak point

Both engines struggle in Bear 2022. AEGEAN loses (-0.17%), TITAN barely positive (+0.14%). Combined moderates the loss (-0.10%) but doesn't solve it. This suggests:
- Neither engine has strong bear-market alpha
- Bear regime may need a dedicated strategy or reduced activity

### 4. COVID crisis is consistently negative for AEGEAN

AEGEAN loses in COVID across all configurations. TITAN breaks even. Combined inherits AEGEAN's loss. Crisis periods should likely trigger reduced position sizing or activity pause.

### 5. Trade overlap analysis

| Scenario | AEGEAN trades | TITAN trades | Combined trades | Expected sum | Cannibalization |
| --- | --- | --- | --- | --- | --- |
| Luna 2022 | 13 | 16 | 25 | 29 | 14% blocked |
| Bear 2022 | 76 | 46 | 112 | 122 | 8% blocked |
| Bull 2024 | 80 | 40 | 111 | 120 | 8% blocked |
| COVID 2020 | 26 | 7 | 32 | 33 | 3% blocked |

Cannibalization is low (3-14%) -- mostly from max_concurrent_positions=3 limit. The engines operate on different regime windows with minimal overlap.

### 6. PnL magnitude context

All PnL values are small (< 4%) because:
- Fixed-size mode uses initial capital only (no compounding leverage)
- Position size is small fraction of equity (risk-managed)
- These are per-scenario returns, not annual compound returns
- The important signal is **direction and consistency**, not magnitude

## Engine Behavioral Profile

| Dimension | AEGEAN | TITAN |
| --- | --- | --- |
| Strategy type | Hybrid MR (RSI + MOM-LRC) | Trend (continuation + reversal) |
| Active regime | All regimes | TRENDING only (~15% of time) |
| Trade frequency | High (76-80/year) | Moderate (40-46/year) |
| Win rate | Higher in Bull (64%), drops in stress | More consistent (50-57%) |
| MaxDD behavior | Larger in Bear (-0.22%) | Near zero across all scenarios |
| Strength | Bull market alpha (+2.79%) | All-weather consistency, low DD |
| Weakness | Bear/crisis losses | Low trade count in crisis |

## Recommendation

### TITAN: PROMOTE to Active Engine

Evidence:
- Positive PnL in 3/4 scenarios (4th is breakeven)
- Lowest MaxDD of any configuration
- Additive to AEGEAN in Bull (+1.12% incremental)
- 3-14% cannibalization is acceptable

### AEGEAN: RETAIN as Primary Engine

Evidence:
- Highest absolute PnL in Bull 2024 (+2.79%)
- Highest trade count (more opportunities)
- But: needs bear/crisis protection (loses in 3/4 scenarios)

### Combined AEGEAN+TITAN: RECOMMENDED Active Roster

Evidence:
- Best aggregate PnL (+3.72%) across all 4 scenarios
- Best Bull performance (+3.91%, PF 31.64)
- Moderate cannibalization (8-14%)
- Combined WR 55-61% in favorable conditions

### Risk Notes

1. **Bear market exposure**: Combined still loses in Bear 2022 (-0.10%). Consider adding regime-based position size reduction.
2. **COVID/crisis**: AEGEAN drags combined negative. Consider crisis detection + activity pause.
3. **Trade count**: TITAN produces 7-46 trades per scenario -- statistically fragile for short periods.
4. **PnL scale**: Returns are small in fixed-size mode. Real-world compounding + leverage will amplify both gains and losses.

## RSL2 Gate Bug Impact

The RSL2 gate bug (references PHOENIX engine set) does NOT affect these results:
- No scenario triggered RSL level 2
- But in live trading, RSL2 would incorrectly block TITAN if risk level rises
- **Fix required before paper/live activation**

## Next Steps

| Priority | Action | Rationale |
| --- | --- | --- |
| 1 | Fix RSL2 gate bug | Blocks TITAN at defensive risk level |
| 2 | Enable AEGEAN+TITAN in paper mode | Validate with real-time data |
| 3 | Add bear regime position size reduction | Largest remaining loss source |
| 4 | Investigate POSEIDON threshold tuning | Third engine candidate |
| 5 | Begin main.py decomposition | Architecture hygiene |
