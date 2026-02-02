| # Pack Diagnostics: sweep_temporal_dec23_20260202_144708
| Scenario | Net PnL | Grs PnL | Fees | SlipCost | Trades (Ev) | WR% | AvgHold | Sc(p95) | RejCost | Exp/Cost (r) | Exit |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline_Dec23 | -4.31 | 2.62 | 6.93 | 6.93 | 4 (8) | 25.0 | 3434 | 8.4 | 3304 | 65.9/20.0 (r=3.3) | SL:3, TP:1 |
| V5_Adx45_Dec23 | -71.74 | -65.49 | 6.25 | 6.25 | 3 (6) | 0.0 | 2717 | 8.4 | 2149 | 47.5/20.0 (r=2.4) | SL:3 |

## Top Winners (PnL)
| Scenario | Timestamp | Side | PnL | Price | Duration (m) |
|---|---|---|---|---|---|
| Baseline_Dec23 | 1701665760.0 | SELL_TP | 47.40 | 40849.10 | - |


## HomeRun Trade Explanations (Top 10 High Score)
| Timestamp | Score | Thresh | Regime | Slope | ADX | Dir | ExpMove |
|---|---|---|---|---|---|---|---|


## Top Blocked Trades (Cost Filter Rejects)
| Scenario | Timestamp | Score | ExpMove | Cost | Safety |
|---|---|---|---|---|---|
| Baseline_Dec23 | 1702560540.0 | 16.3 | 33.8 | 20.0 | 2.0 |
| V5_Adx45_Dec23 | 1702560540.0 | 16.3 | 33.8 | 20.0 | 2.0 |
| Baseline_Dec23 | 1703569200.0 | 16.1 | 30.3 | 20.0 | 2.0 |
| V5_Adx45_Dec23 | 1703569200.0 | 16.1 | 30.3 | 20.0 | 2.0 |
| Baseline_Dec23 | 1703569080.0 | 15.9 | 28.0 | 20.0 | 2.0 |
| Baseline_Dec23 | 1703569260.0 | 15.9 | 30.4 | 20.0 | 2.0 |
| V5_Adx45_Dec23 | 1703569080.0 | 15.9 | 28.0 | 20.0 | 2.0 |
| V5_Adx45_Dec23 | 1703569260.0 | 15.9 | 30.4 | 20.0 | 2.0 |
| Baseline_Dec23 | 1703568900.0 | 15.5 | 25.5 | 20.0 | 2.0 |
| Baseline_Dec23 | 1703569140.0 | 15.5 | 29.4 | 20.0 | 2.0 |


## ExpMove Calibration & Reliability (Binning & Correlation)
| Metric | Pearson (Linear) | Spearman (Rank) | Notes |
|---|---|---|---|
| Exp vs Realized | -0.25 | N/A | Ground Truth |
| Exp vs Net | -0.25 | N/A | After Cost |

### Reliability (Monotonicity Check)
| Bin (ExpMove) | Count | AvgExp | AvgRealized | HitRate (>Cost) |
|---|---|---|---|---|
| (40.499, 40.72] | 2 | 40.5 | -209.8 | 0.0% |
| (40.72, 41.64] | 1 | 41.6 | -210.2 | 0.0% |
| (41.64, 52.86] | 1 | 41.7 | 389.6 | 100.0% |
| (52.86, 60.3] | 2 | 60.3 | -210.2 | 0.0% |
| (60.3, 121.2] | 1 | 121.2 | -210.2 | 0.0% |


## Cost Model Verification (Detailed)
| Scenario | Est Cost (Fee/Slip/Spread) | Actual (Fee/Slip) | Error (Est-Act) | Act Slip Bps |
|---|---|---|---|---|
| Baseline_Dec23 | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| V5_Adx45_Dec23 | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |


## Directional Analysis (BUY vs SELL)
| Scenario | Direction | Count | WR% | AvgNet | AvgExp | AvgRealized | AvgADX | AvgSlope |
|---|---|---|---|---|---|---|---|---|
| Baseline_Dec23 | BUY | 2 | 50.0% | 69.9 | 41.1 | 89.9 | 44.9 | 10.7 |
| Baseline_Dec23 | SELL | 2 | 0.0% | -230.2 | 90.8 | -210.2 | 63.1 | -74.5 |
| V5_Adx45_Dec23 | BUY | 1 | 0.0% | -229.8 | 40.5 | -209.8 | 49.3 | 9.3 |
| V5_Adx45_Dec23 | SELL | 2 | 0.0% | -230.2 | 51.0 | -210.2 | 55.8 | -56.7 |


## Regime x Direction Matrix (Global Avg Net PnL)
| Regime | BUY (Net) | SELL (Net) | BUY (Count) | SELL (Count) |
|---|---|---|---|---|
| TREND | -30.0 | -230.2 | 3 | 4 |


## Top 20 Toxic BUY Trades (Failure Forensics)
| Scenario | Timestamp | Net | ExpMove | ADX | Slope | Regime |
|---|---|---|---|---|---|---|
| Baseline_Dec23 | 1701796620.0 | -229.8 | 40.5 | 49.3 | 9.3 | TREND |
| V5_Adx45_Dec23 | 1701796620.0 | -229.8 | 40.5 | 49.3 | 9.3 | TREND |
| Baseline_Dec23 | 1701544500.0 | 369.6 | 41.7 | 40.4 | 12.1 | TREND |
