| # Pack Diagnostics: val_pack_1770018235
| Scenario | Net PnL | Grs PnL | Fees | SlipCost | Trades (Ev) | WR% | AvgHold | Sc(p95) | RejCost | Exp/Cost (r) | Exit |
|---|---|---|---|---|---|---|---|---|---|---|
| A_Scenario | 17.06 | 18.59 | 1.53 | 0.76 | 8 (16) | 50.0 | 379 | 8.9 | 202 | 58.5/7.0 (r=8.3) | SL:4, TP:3, EOS:1 |

## Top Winners (PnL)
| Scenario | Timestamp | Side | PnL | Price | Duration (m) |
|---|---|---|---|---|---|
| A_Scenario | 1704283740.0 | BUY_TP | 15.07 | 41246.37 | - |
| A_Scenario | 1704283260.0 | BUY_TP | 9.95 | 43489.05 | - |
| A_Scenario | 1704183600.0 | SELL_TP | 9.84 | 45761.24 | - |
| A_Scenario | 1704402001.0 | SELL_EOS | 1.49 | 44160.47 | - |


## HomeRun Trade Explanations (Top 10 High Score)
| Timestamp | Score | Thresh | Regime | Slope | ADX | Dir | ExpMove |
|---|---|---|---|---|---|---|---|


## Top Blocked Trades (Cost Filter Rejects)
| Scenario | Timestamp | Score | ExpMove | Cost | Safety |
|---|---|---|---|---|---|
| A_Scenario | 1704132900.0 | 12.7 | 11.3 | 7.0 | 2.0 |
| A_Scenario | 1704132780.0 | 11.9 | 9.9 | 7.0 | 2.0 |
| A_Scenario | 1704132960.0 | 11.7 | 12.4 | 7.0 | 2.0 |
| A_Scenario | 1704132840.0 | 11.6 | 9.8 | 7.0 | 2.0 |
| A_Scenario | 1704064860.0 | 11.2 | 13.5 | 7.0 | 2.0 |
| A_Scenario | 1704133260.0 | 11.1 | 13.2 | 7.0 | 2.0 |
| A_Scenario | 1704151920.0 | 11.1 | 12.9 | 7.0 | 2.0 |
| A_Scenario | 1704132720.0 | 11.0 | 9.1 | 7.0 | 2.0 |
| A_Scenario | 1704133080.0 | 11.0 | 13.0 | 7.0 | 2.0 |
| A_Scenario | 1704151740.0 | 11.0 | 12.1 | 7.0 | 2.0 |


## ExpMove Reliability (Binning & Correlation)
| Metric | Pearson (Linear) | Spearman (Rank) | Notes |
|---|---|---|---|
| Exp vs Realized | -0.39 | N/A | Ground Truth |
| Exp vs Net | -0.39 | N/A | After Cost |

### Reliability (Monotonicity Check)
| Bin (ExpMove) | Count | AvgExp | AvgRealized | HitRate (>Cost) |
|---|---|---|---|---|
| (14.199, 14.64] | 2 | 14.3 | 259.7 | 100.0% |
| (14.64, 23.4] | 1 | 15.0 | 398.1 | 100.0% |
| (23.4, 45.32] | 2 | 29.3 | -202.0 | 0.0% |
| (45.32, 104.16] | 1 | 94.2 | 398.1 | 100.0% |
| (104.16, 160.4] | 2 | 135.6 | -202.0 | 0.0% |


## Cost Model Verification (Detailed)
| Scenario | Est Cost (Fee/Slip/Spread) | Actual (Fee/Slip) | Error (Est-Act) | Act Slip Bps |
|---|---|---|---|---|
| A_Scenario | 7.0 (4.0/2.0/1.0) | 6.00 (4.0/2.00) | +1.00 | 2.00 |

    
## Retroactive Calibration (Backfill)
Generated from 8 trades.

| Metric | Pearson | Spearman |
|---|---|---|
| Exp vs Realized | -0.39 | -0.61 |
| Exp vs Net | -0.39 | -0.61 |

### Reliability Bins
| Bin (ExpMove) | Count | AvgRealized | HitRate |
|---|---|---|---|
| (14.199, 14.64] | 2 | 259.7 | 100.0% |
| (14.64, 23.4] | 1 | 398.1 | 100.0% |
| (23.4, 45.32] | 2 | -202.0 | 0.0% |
| (45.32, 104.16] | 1 | 398.1 | 100.0% |
| (104.16, 160.4] | 2 | -202.0 | 0.0% |

