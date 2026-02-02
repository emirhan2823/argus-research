# Argus Run Report
**Run ID:** `20260131_213932_3ebe93`
**Symbol:** BTCUSDT | **Mode:** backtest

## Data Summary
**Bars:** 5760 | **From:** 2024-01-01 00:00:00 | **To:** 2024-01-04 23:59:00
**Price Range:** 40887.99 - 48883.99

## Performance Summary
| Metric | Value |
|---|---|
| Total Return | 1.16% |
| Max Drawdown | 75.25% |
| Final Equity | $1011.62 |
| Total Trades | 8 |
| Win Rate | 25.0% |
| Profit Factor | 1.64 |

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
  "cooldown_bars": 3,
  "auto_capital_mode": true,
  "capital_profile": null,
  "start_date": "2024-01-01",
  "end_date": "2024-01-05",
  "download_binance": true,
  "min_warmup": 200,
  "debug": false,
  "verify_data": false,
  "max_bars": null,
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
| LOW_CONVICTION | 21 |

**Avg Conviction:** 6.64 | **Max Conviction:** 90.00

## Last 10 Trades
_Error reading trades: Missing optional dependency 'tabulate'.  Use pip or conda to install tabulate._
