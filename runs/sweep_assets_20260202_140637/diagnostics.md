| # Pack Diagnostics: sweep_assets_20260202_140637
| Scenario | Net PnL | Grs PnL | Fees | SlipCost | Trades (Ev) | WR% | AvgHold | Sc(p95) | RejCost | Exp/Cost (r) | Exit |
|---|---|---|---|---|---|---|---|---|---|---|
| Asset_BNBUSDT | -128.51 | -101.18 | 27.33 | 27.33 | 12 (24) | 33.3 | 1027 | 8.6 | 1761 | 49.7/20.0 (r=2.5) | SL:8, TP:4 |
| Asset_BTCUSDT | 46.35 | 48.80 | 2.45 | 2.45 | 1 (2) | 100.0 | 13 | 8.9 | 288 | 43.3/20.0 (r=2.2) | TP:1 |
| Asset_ETHUSDT | 17.58 | 38.88 | 21.30 | 21.30 | 9 (18) | 44.4 | 1044 | 8.6 | 1602 | 50.5/20.0 (r=2.5) | SL:5, TP:4 |
| Asset_SOLUSDT | 55.14 | 136.30 | 81.16 | 81.16 | 45 (90) | 42.2 | 412 | 10.0 | 535 | 52.5/20.0 (r=2.6) | SL:26, TP:18, EOS:1 |

## Top Winners (PnL)
| Scenario | Timestamp | Side | PnL | Price | Duration (m) |
|---|---|---|---|---|---|
| Asset_SOLUSDT | 1704217260.0 | BUY_TP | 71.60 | 106.90 | - |
| Asset_SOLUSDT | 1704473940.0 | BUY_TP | 48.10 | 96.20 | - |
| Asset_SOLUSDT | 1704775500.0 | SELL_TP | 48.04 | 102.92 | - |
| Asset_SOLUSDT | 1704283260.0 | BUY_TP | 47.86 | 102.15 | - |
| Asset_SOLUSDT | 1704736980.0 | SELL_TP | 47.81 | 97.60 | - |
| Asset_SOLUSDT | 1704396600.0 | SELL_TP | 47.74 | 105.96 | - |
| Asset_ETHUSDT | 1706002140.0 | BUY_TP | 47.60 | 2240.64 | - |
| Asset_ETHUSDT | 1704283740.0 | BUY_TP | 47.60 | 2146.65 | - |
| Asset_BTCUSDT | 1704283680.0 | BUY_TP | 47.60 | 41870.09 | - |
| Asset_ETHUSDT | 1704921960.0 | SELL_TP | 47.35 | 2531.00 | - |


## HomeRun Trade Explanations (Top 10 High Score)
| Timestamp | Score | Thresh | Regime | Slope | ADX | Dir | ExpMove |
|---|---|---|---|---|---|---|---|


## Top Blocked Trades (Cost Filter Rejects)
| Scenario | Timestamp | Score | ExpMove | Cost | Safety |
|---|---|---|---|---|---|
| Asset_SOLUSDT | 1704063060.0 | 19.6 | 36.8 | 20.0 | 2.0 |
| Asset_BNBUSDT | 1704963000.0 | 18.4 | 33.2 | 20.0 | 2.0 |
| Asset_BNBUSDT | 1704263640.0 | 16.9 | 15.7 | 20.0 | 2.0 |
| Asset_SOLUSDT | 1706414640.0 | 16.4 | 36.1 | 20.0 | 2.0 |
| Asset_BNBUSDT | 1704263580.0 | 16.3 | 14.7 | 20.0 | 2.0 |
| Asset_BNBUSDT | 1704962940.0 | 16.0 | 27.1 | 20.0 | 2.0 |
| Asset_BNBUSDT | 1704963060.0 | 16.0 | 35.0 | 20.0 | 2.0 |
| Asset_BNBUSDT | 1704963240.0 | 16.0 | 35.8 | 20.0 | 2.0 |
| Asset_SOLUSDT | 1706414100.0 | 16.0 | 36.9 | 20.0 | 2.0 |
| Asset_SOLUSDT | 1706414220.0 | 16.0 | 37.8 | 20.0 | 2.0 |


## ExpMove Calibration & Reliability (Binning & Correlation)
| Metric | Pearson (Linear) | Spearman (Rank) | Notes |
|---|---|---|---|
| Exp vs Realized | -0.13 | N/A | Ground Truth |
| Exp vs Net | -0.13 | N/A | After Cost |

### Reliability (Monotonicity Check)
| Bin (ExpMove) | Count | AvgExp | AvgRealized | HitRate (>Cost) |
|---|---|---|---|---|
| (39.999, 41.44] | 14 | 40.7 | 41.6 | 42.9% |
| (41.44, 44.16] | 13 | 42.5 | 113.1 | 53.8% |
| (44.16, 51.76] | 13 | 47.0 | 67.1 | 46.2% |
| (51.76, 61.7] | 13 | 56.8 | -25.3 | 30.8% |
| (61.7, 79.8] | 14 | 70.3 | 4.3 | 35.7% |


## Cost Model Verification (Detailed)
| Scenario | Est Cost (Fee/Slip/Spread) | Actual (Fee/Slip) | Error (Est-Act) | Act Slip Bps |
|---|---|---|---|---|
| Asset_BNBUSDT | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| Asset_BTCUSDT | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| Asset_ETHUSDT | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |
| Asset_SOLUSDT | 20.0 (10.0/5.0/5.0) | 20.00 (10.0/10.00) | +0.00 | 10.00 |


## Directional Analysis (BUY vs SELL)
| Scenario | Direction | Count | WR% | AvgNet | AvgExp | AvgRealized | AvgADX | AvgSlope |
|---|---|---|---|---|---|---|---|---|
| Asset_BNBUSDT | BUY | 2 | 0.0% | -229.8 | 63.5 | -209.8 | 52.5 | 0.3 |
| Asset_BNBUSDT | SELL | 10 | 40.0% | 10.0 | 47.0 | 30.0 | 48.0 | -0.3 |
| Asset_BTCUSDT | SELL | 1 | 100.0% | 370.4 | 43.3 | 390.4 | 62.6 | -68.9 |
| Asset_ETHUSDT | BUY | 2 | 50.0% | 69.9 | 44.0 | 89.9 | 46.2 | 3.1 |
| Asset_ETHUSDT | SELL | 7 | 42.9% | 27.2 | 52.4 | 47.2 | 51.8 | -2.7 |
| Asset_SOLUSDT | BUY | 22 | 36.4% | -11.8 | 50.3 | 8.2 | 49.4 | 0.1 |
| Asset_SOLUSDT | SELL | 23 | 47.8% | 53.7 | 54.5 | 73.7 | 47.9 | -0.1 |


## Regime x Direction Matrix (Global Avg Net PnL)
| Regime | BUY (Net) | SELL (Net) | BUY (Count) | SELL (Count) |
|---|---|---|---|---|
| TREND | -22.3 | 46.2 | 26 | 41 |


## Top 20 Toxic BUY Trades (Failure Forensics)
| Scenario | Timestamp | Net | ExpMove | ADX | Slope | Regime |
|---|---|---|---|---|---|---|
| Asset_SOLUSDT | 1704600600.0 | -229.8 | 44.6 | 46.1 | 0.0 | TREND |
| Asset_SOLUSDT | 1704396900.0 | -229.8 | 60.3 | 55.1 | 0.0 | TREND |
| Asset_SOLUSDT | 1705488240.0 | -229.8 | 59.0 | 45.3 | 0.1 | TREND |
| Asset_SOLUSDT | 1705693140.0 | -229.8 | 44.0 | 45.7 | 0.0 | TREND |
| Asset_SOLUSDT | 1706022300.0 | -229.8 | 68.1 | 46.1 | 0.1 | TREND |
| Asset_SOLUSDT | 1704314580.0 | -229.8 | 40.7 | 46.5 | 0.0 | TREND |
| Asset_SOLUSDT | 1704775800.0 | -229.8 | 52.3 | 46.8 | 0.1 | TREND |
| Asset_BNBUSDT | 1704275340.0 | -229.8 | 79.1 | 59.5 | 0.4 | TREND |
| Asset_SOLUSDT | 1705455480.0 | -229.8 | 40.3 | 45.8 | 0.0 | TREND |
| Asset_ETHUSDT | 1704928500.0 | -229.8 | 44.4 | 45.7 | 3.6 | TREND |
| Asset_SOLUSDT | 1706414760.0 | -229.8 | 41.3 | 69.7 | 0.0 | TREND |
| Asset_SOLUSDT | 1704909900.0 | -229.8 | 60.5 | 51.1 | 0.1 | TREND |
| Asset_SOLUSDT | 1705249260.0 | -229.8 | 59.5 | 47.1 | 0.2 | TREND |
| Asset_SOLUSDT | 1705536480.0 | -229.8 | 42.1 | 49.6 | 0.1 | TREND |
| Asset_SOLUSDT | 1705955160.0 | -229.8 | 46.8 | 46.9 | 0.1 | TREND |
| Asset_SOLUSDT | 1704925260.0 | -229.8 | 73.5 | 45.1 | 0.2 | TREND |
| Asset_BNBUSDT | 1705491660.0 | -229.8 | 48.0 | 45.6 | 0.2 | TREND |
| Asset_SOLUSDT | 1704125460.0 | 369.6 | 45.6 | 45.6 | 0.1 | TREND |
| Asset_SOLUSDT | 1704157920.0 | 369.6 | 63.0 | 51.1 | 0.1 | TREND |
| Asset_ETHUSDT | 1704899580.0 | 369.6 | 43.6 | 46.6 | 2.5 | TREND |
