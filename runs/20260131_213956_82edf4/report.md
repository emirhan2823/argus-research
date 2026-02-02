# Argus Run Report
**Run ID:** `20260131_213956_82edf4`
**Symbol:** BTCUSDT | **Mode:** adaptive

## Data Summary
**Bars:** 10000 | **From:** 2024-01-07 09:00:00 | **To:** 2024-01-14 07:39:00
**Price Range:** 41750.07 - 48883.99

## Performance Summary
| Metric | Value |
|---|---|
| Total Return | -7.01% |
| Max Drawdown | 153.04% |
| Final Equity | $27.90 |
| Total Trades | 5 |
| Win Rate | 40.0% |
| Profit Factor | 0.28 |

## Visualization
![Equity Curve](equity.png)
![Drawdown Curve](drawdown.png)

## Configuration
<details>
<summary>Click to expand config</summary>

```json
{
  "mode": "adaptive",
  "symbol": "BTCUSDT",
  "data_dir": "argus_py/data",
  "start_balance": 30.0,
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
  "start_date": null,
  "end_date": null,
  "download_binance": false,
  "min_warmup": 200,
  "debug": false,
  "verify_data": false,
  "max_bars": 10000,
  "report": true,
  "lab_grid": false
}
```
</details>

## Signal Analysis
### Block Reasons
| Reason | Count |
|---|---|
| LOW_CONVICTION | 336 |
| WARMUP | 98 |

**Avg Conviction:** 11.54 | **Max Conviction:** 90.00

## Last 10 Trades
_Error reading trades: Missing optional dependency 'tabulate'.  Use pip or conda to install tabulate._
