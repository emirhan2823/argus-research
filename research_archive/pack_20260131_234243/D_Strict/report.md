# Argus Run Report
**Run ID:** `20260131_234351_60665c`
**Symbol:** BTCUSDT | **Mode:** adaptive

## Data Summary
**Bars:** 5761 | **From:** 2024-01-01 00:00:00 | **To:** 2024-01-05 00:00:00
**Price Range:** 40887.99 - 45874.92

## Performance Summary
| Metric | Value |
|---|---|
| Total Return | 0.00% |
| Max Drawdown | 13.01% |
| Final Equity | $10000.17 |
| Total Trades | 7 |
| Win Rate | 42.9% |
| Profit Factor | 1.08 |

## Visualization
![Equity Curve](equity.png)
![Drawdown Curve](drawdown.png)

## Parameters
| Param | Value |
|---|---|
| Fee (bps) | 10.0 |
| Slippage (bps) | 5.0 |
| Spread (bps) | 5.0 |
| Use Bid/Ask | True |
| Max Risk Cap | 0.5% |
| Liq Margin | 20.0% |

<details>
<summary>Full Config JSON</summary>

```json
{
  "mode": "adaptive",
  "symbol": "BTCUSDT",
  "data_dir": "argus_py/data",
  "start_balance": 10000.0,
  "leverage_max": 1.0,
  "sniper": false,
  "close_at_end": true,
  "profile": "AUTO",
  "council_threshold": 0.4,
  "min_conviction": null,
  "chop_floor": null,
  "trend_floor": null,
  "exit_policy": "FIXED_BRACKET",
  "cooldown_bars": 30,
  "auto_capital_mode": true,
  "capital_profile": null,
  "start_date": "2024-01-01",
  "end_date": "2024-01-10",
  "download_binance": false,
  "min_warmup": 10,
  "debug": false,
  "verify_data": false,
  "quiet": true,
  "max_bars": null,
  "report": true,
  "lab_grid": false,
  "fee_bps": 10.0,
  "slippage_bps": 5.0,
  "spread_bps": 5.0,
  "funding_bps_per_8h": 0.0,
  "use_bid_ask": true,
  "max_risk_per_trade_pct": 0.5,
  "max_notional_pct_of_equity": 100.0,
  "liq_safety_margin_pct": 20.0
}
```
</details>

### Top Winners
_Analysis Error: Missing optional dependency 'tabulate'.  Use pip or conda to install tabulate._
## Signal Analysis
### Block Reasons
| Reason | Count |
|---|---|
| WARMUP | 98 |
| LOW_CONVICTION | 33 |

**Avg Conviction:** 6.30 | **Max Conviction:** 66.67

## Last 10 Trades
_Error reading trades: Missing optional dependency 'tabulate'.  Use pip or conda to install tabulate._
