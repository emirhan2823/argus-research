# TopHunter Short (Paper-Only) - Strategy Spec

## 1. Scope

- Strategy ID: `TOPHUNTER_SHORT_V1`
- Mode: `paper-only`
- Timeframe: signal generation on `1h`
- Purpose: capture downside continuation after bearish structure break.

## 2. Core Logic

### 2.1 V1 Trigger (Structure Break)

Short trigger fires when:

1. A valid `1h` pivot swing-low is identified.
2. Price closes below that pivot swing-low level.

Definition (implementation-oriented):

- Pivot swing-low window: `left=2`, `right=2` candles (configurable).
- `pivot_low_price = low[i]` where `low[i] < low[i-1], low[i-2], low[i+1], low[i+2]`.
- Break confirmation: `close[t] < pivot_low_price` on a closed `1h` candle.

### 2.2 Regime Filter

- Entry allowed only if `ADX(14) < 20` on `1h`.
- If `ADX >= 20`, signal is rejected (`REJECT_REGIME_ADX`).

## 3. Entry / Stop / TP Rules

| Item | Rule |
|---|---|
| Entry | Market short at next bar open after confirmed break |
| Stop | `max(last_pivot_high, entry + 1.2 * ATR(14))` |
| TP1 | `entry - 1.0R` (optional partial 50%) |
| TP2 | `entry - 2.0R` (full close if TP1 skipped, otherwise remainder) |
| Time Stop | Close if `bars_held >= 24` (1h bars) |

Where:

- `R = stop_distance = stop_price - entry_price` (for short).

## 4. Risk Caps (Paper-Only)

| Risk Control | Value |
|---|---|
| Max risk per trade | `0.5%` of paper equity |
| Max daily strategy loss | `1.5%` equity |
| Max concurrent TopHunter positions | `1` |
| Cooldown after loss | `3` closed bars |
| Hard disable | If kill-switch level is `HARD` or `HALT`, no new entries |

## 5. Execution Notes

- Required telemetry tags:
  - `strategy_id=TOPHUNTER_SHORT_V1`
  - `trigger_type=SWING_LOW_BREAK`
  - `regime_filter=ADX_LT_20`
- Required reject codes:
  - `REJECT_REGIME_ADX`
  - `REJECT_COOLDOWN`
  - `REJECT_RISK_CAP`
  - `REJECT_KILL_SWITCH`

## 6. Validation Plan (Before Any Live Consideration)

1. Unit test pivot detection edge cases (flat lows, duplicate lows, missing candles).
2. Backtest with realistic costs (fees/slippage/latency assumptions from Year-2 plan).
3. Paper soak minimum `200` TopHunter-tagged trades.
4. Gate metrics:
   - Max DD from TopHunter sleeve `<= 3%`
   - Win rate `>= 40%`
   - Profit factor `>= 1.2`

## 7. TODO Implementation Checklist

- [ ] Add strategy module under `argus_py/models/` or `argus_py/strategy/`.
- [ ] Wire ADX<20 regime gate into decision path.
- [ ] Add telemetry fields to `decisions.csv` / `trades.csv`.
- [ ] Add dedicated audit slice: `reports/year2/tophunter_short_audit.md`.
- [ ] Keep execution strictly paper-only until Year-2 gate approval.

