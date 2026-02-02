# Argus Run Report
**Run ID:** `20260131_170312_d23c6c`
**Symbol:** BTCUSDT | **Mode:** backtest

## Performance Summary
| Metric | Value |
|---|---|
| Total Return | 92.59% |
| Max Drawdown | 0.09% |
| Final Equity | $1925.88 |
| Total Trades | 48 |
| Win Rate | 97.9% |
| Profit Factor | 513.17 |

## Visualization
![Equity Curve](equity.png)
![Drawdown Curve](drawdown.png)

## Configuration
<details>
<summary>Click to expand config</summary>

```json
{
  "mode": "backtest",
  "symbol": "BTCUSDT",
  "data_dir": "argus_py/data",
  "start_balance": 1000.0,
  "leverage_max": 1.0,
  "sniper": false,
  "close_at_end": true,
  "profile": "AUTO",
  "council_threshold": 0.4,
  "min_conviction": null,
  "chop_floor": null,
  "trend_floor": null,
  "exit_policy": "FIXED_BRACKET",
  "cooldown_bars": 2,
  "auto_capital_mode": true,
  "capital_profile": null,
  "start_date": null,
  "end_date": null,
  "debug": false,
  "max_bars": 500,
  "report": true,
  "lab_grid": false
}
```
</details>

## Signal Analysis
### Block Reasons
| Reason | Count |
|---|---|
| WARMUP | 98 |

**Avg Conviction:** 21.92 | **Max Conviction:** 66.67

## Last 10 Trades
_Error reading trades: Missing optional dependency 'tabulate'.  Use pip or conda to install tabulate._
