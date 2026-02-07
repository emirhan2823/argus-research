| # Pack Diagnostics: pack_20260202_133137
| Scenario | Net PnL | Grs PnL | Fees | SlipCost | Trades (Ev) | WR% | AvgHold | Sc(p95) | RejCost | Exp/Cost (r) | Exit |
|---|---|---|---|---|---|---|---|---|---|---|
| A_Baseline_Norm | -25.77 | -17.02 | 8.76 | 8.76 | 4 (8) | 25.0 | 101 | 8.9 | 830 | 86.5/20.0 (r=4.3) | SL:3, TP:1 |
| V1_SellOnly | -11.44 | -3.92 | 7.52 | 7.52 | 3 (6) | 33.3 | 78 | 8.9 | 402 | 99.9/20.0 (r=5.0) | SL:2, TP:1 |
| V2_CapExp80 | -11.33 | -3.87 | 7.47 | 7.47 | 3 (6) | 33.3 | 127 | 8.9 | 828 | 50.6/20.0 (r=2.5) | SL:2, TP:1 |
| V4_Combo | 17.41 | 22.40 | 4.99 | 4.99 | 2 (4) | 50.0 | 105 | 8.9 | 485 | 52.8/20.0 (r=2.6) | TP:1, SL:1 |
| VT_1.8_Smart | -25.77 | -17.02 | 8.76 | 8.76 | 4 (8) | 25.0 | 101 | 8.9 | 826 | 86.5/20.0 (r=4.3) | SL:3, TP:1 |
| VT_2.5_Smart | -25.77 | -17.02 | 8.76 | 8.76 | 4 (8) | 25.0 | 101 | 8.9 | 830 | 86.5/20.0 (r=4.3) | SL:3, TP:1 |

## Top Winners (PnL)
| Scenario | Timestamp | Side | PnL | Price | Duration (m) |
|---|---|---|---|---|---|
| A_Baseline_Norm | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |
| V1_SellOnly | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |
| V2_CapExp80 | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |
| V4_Combo | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |
| VT_1.8_Smart | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |
| VT_2.5_Smart | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |


## HomeRun Trade Explanations (Top 10 High Score)
| Timestamp | Score | Thresh | Regime | Slope | ADX | Dir | ExpMove |
|---|---|---|---|---|---|---|---|


## Top Blocked Trades (Cost Filter Rejects)
| Scenario | Timestamp | Score | ExpMove | Cost | Safety |
|---|---|---|---|---|---|
| A_Baseline_Norm | 1704281340.0 | 15.9 | 30.6 | 20.0 | 2.0 |
| V1_SellOnly | 1704281340.0 | 15.9 | 30.6 | 20.0 | 2.0 |
| V2_CapExp80 | 1704281340.0 | 15.9 | 30.6 | 20.0 | 2.0 |
| V4_Combo | 1704281340.0 | 15.9 | 30.6 | 20.0 | 2.0 |
| VT_1.8_Smart | 1704281340.0 | 15.9 | 30.6 | 20.0 | 2.0 |
| VT_2.5_Smart | 1704281340.0 | 15.9 | 30.6 | 20.0 | 2.0 |
| A_Baseline_Norm | 1704281400.0 | 15.4 | 33.5 | 20.0 | 2.0 |
| V1_SellOnly | 1704281400.0 | 15.4 | 33.5 | 20.0 | 2.0 |
| V2_CapExp80 | 1704281400.0 | 15.4 | 33.5 | 20.0 | 2.0 |
| V4_Combo | 1704281400.0 | 15.4 | 33.5 | 20.0 | 2.0 |


## ExpMove Calibration & Reliability (Binning & Correlation)
| Metric | Pearson (Linear) | Spearman (Rank) | Notes |
|---|---|---|---|
| Exp vs Realized | -0.56 | N/A | Ground Truth |
| Exp vs Net | -0.56 | N/A | After Cost |

### Reliability (Monotonicity Check)
| Bin (ExpMove) | Count | AvgExp | AvgRealized | HitRate (>Cost) |
|---|---|---|---|---|
| (43.299, 46.3] | 10 | 44.5 | 150.3 | 60.0% |
| (46.3, 79.42] | 2 | 62.3 | -210.2 | 0.0% |
| (79.42, 114.34] | 4 | 105.1 | -210.2 | 0.0% |
| (114.34, 151.3] | 4 | 151.3 | -210.2 | 0.0% |


## Cost Model Verification (Detailed)
| Scenario | Est Cost (Fee/Slip/Spread) | Actual (Fee/Slip) | Error (Est-Act) | Act Slip Bps |
|---|---|---|---|---|
| A_Baseline_Norm | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| V1_SellOnly | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| V2_CapExp80 | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| V4_Combo | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| VT_1.8_Smart | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| VT_2.5_Smart | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |


## Directional Analysis (BUY vs SELL)
| Scenario | Direction | Count | WR% | AvgNet | AvgExp | AvgRealized | AvgADX | AvgSlope |
|---|---|---|---|---|---|---|---|---|
| A_Baseline_Norm | BUY | 1 | 0.0% | -229.8 | 46.3 | -209.8 | 35.8 | 37.0 |
| A_Baseline_Norm | SELL | 3 | 33.3% | -30.0 | 99.9 | -10.0 | 59.9 | -71.0 |
| V1_SellOnly | SELL | 3 | 33.3% | -30.0 | 99.9 | -10.0 | 59.9 | -71.0 |
| V2_CapExp80 | BUY | 1 | 0.0% | -229.8 | 46.3 | -209.8 | 35.8 | 37.0 |
| V2_CapExp80 | SELL | 2 | 50.0% | 70.1 | 52.8 | 90.1 | 47.5 | -38.6 |
| V4_Combo | SELL | 2 | 50.0% | 70.1 | 52.8 | 90.1 | 47.5 | -38.6 |
| VT_1.8_Smart | BUY | 1 | 0.0% | -229.8 | 46.3 | -209.8 | 35.8 | 37.0 |
| VT_1.8_Smart | SELL | 3 | 33.3% | -30.0 | 99.9 | -10.0 | 59.9 | -71.0 |
| VT_2.5_Smart | BUY | 1 | 0.0% | -229.8 | 46.3 | -209.8 | 35.8 | 37.0 |
| VT_2.5_Smart | SELL | 3 | 33.3% | -30.0 | 99.9 | -10.0 | 59.9 | -71.0 |


## Regime x Direction Matrix (Global Avg Net PnL)
| Regime | BUY (Net) | SELL (Net) | BUY (Count) | SELL (Count) |
|---|---|---|---|---|
| TREND | -229.8 | -5.0 | 4 | 16 |


## Top 20 Toxic BUY Trades (Failure Forensics)
| Scenario | Timestamp | Net | ExpMove | ADX | Slope | Regime |
|---|---|---|---|---|---|---|
| A_Baseline_Norm | 1704297900.0 | -229.8 | 46.3 | 35.8 | 37.0 | TREND |
| V2_CapExp80 | 1704297900.0 | -229.8 | 46.3 | 35.8 | 37.0 | TREND |
| VT_1.8_Smart | 1704297900.0 | -229.8 | 46.3 | 35.8 | 37.0 | TREND |
| VT_2.5_Smart | 1704297900.0 | -229.8 | 46.3 | 35.8 | 37.0 | TREND |
