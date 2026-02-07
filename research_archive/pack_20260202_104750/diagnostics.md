| # Pack Diagnostics: pack_20260202_104750
| Scenario | Net PnL | Grs PnL | Fees | SlipCost | Trades (Ev) | WR% | AvgHold | Sc(p95) | RejCost | Exp/Cost (r) | Exit |
|---|---|---|---|---|---|---|---|---|---|---|
| A_Baseline | 44.40 | 51.70 | 7.30 | 3.65 | 9 (18) | 44.4 | 274 | 8.9 | 487 | 52.5/7.0 (r=7.5) | SL:5, TP:3, EOS:1 |
| B1_Sens_Slip0 | 29.52 | 36.98 | 7.46 | 0.75 | 4 (8) | 50.0 | 1002 | 8.9 | 277 | 66.8/11.0 (r=6.1) | SL:2, TP:2 |
| B2_Sens_Spr0 | -49.92 | -38.72 | 11.20 | 2.24 | 6 (12) | 16.7 | 501 | 8.9 | 383 | 60.6/12.0 (r=5.1) | SL:5, TP:1 |
| B_HeavyRealism | -11.44 | -3.92 | 7.52 | 7.52 | 3 (6) | 33.3 | 77 | 8.9 | 868 | 94.0/20.0 (r=4.7) | SL:2, TP:1 |
| C_RiskCapped | -11.44 | -3.92 | 7.52 | 7.52 | 3 (6) | 33.3 | 77 | 8.9 | 868 | 94.0/20.0 (r=4.7) | SL:2, TP:1 |
| D_Strict | 17.41 | 22.40 | 4.99 | 4.99 | 2 (4) | 50.0 | 104 | 8.9 | 1059 | 49.1/20.0 (r=2.5) | TP:1, SL:1 |
| E_EdgeFiltered | -71.74 | -65.49 | 6.25 | 6.25 | 3 (6) | 0.0 | 936 | 8.9 | 358 | 41.2/20.0 (r=2.1) | SL:3 |
| F_HomeRun_Pctl | -71.74 | -65.49 | 6.25 | 6.25 | 3 (6) | 0.0 | 933 | 8.9 | 128 | 40.8/20.0 (r=2.0) | SL:3 |
| F_Legacy60_Mult3 | 0.00 | 0.00 | 0.00 | 0.00 | 0 (0) | 0.0 | 0 | 8.9 | 0 | 0.0/0.0 (r=0.0) |  |
| G_HomeRun_Strict_Pctl | 49.31 | 58.05 | 8.74 | 8.74 | 3 (6) | 66.7 | 14 | 8.9 | 14 | 95.1/20.0 (r=4.8) | TP:2, SL:1 |
| H_HomeRun_p90 | 17.41 | 22.40 | 4.99 | 4.99 | 2 (4) | 50.0 | 13 | 8.9 | 0 | 99.5/20.0 (r=5.0) | TP:1, SL:1 |

## Top Winners (PnL)
| Scenario | Timestamp | Side | PnL | Price | Duration (m) |
|---|---|---|---|---|---|
| A_Baseline | 1704283740.0 | BUY_TP | 49.70 | 41246.37 | - |
| A_Baseline | 1704283260.0 | BUY_TP | 49.46 | 43066.59 | - |
| A_Baseline | 1704183600.0 | SELL_TP | 49.22 | 45761.24 | - |
| B1_Sens_Slip0 | 1704283680.0 | BUY_TP | 48.55 | 41812.80 | - |
| B2_Sens_Spr0 | 1704283680.0 | BUY_TP | 48.43 | 41812.80 | - |
| G_HomeRun_Strict_Pctl | 1704283740.0 | BUY_TP | 47.82 | 41246.33 | - |
| B_HeavyRealism | 1704283680.0 | BUY_TP | 47.60 | 42003.80 | - |
| C_RiskCapped | 1704283680.0 | BUY_TP | 47.60 | 42003.80 | - |
| D_Strict | 1704283680.0 | BUY_TP | 47.60 | 42003.80 | - |
| G_HomeRun_Strict_Pctl | 1704283260.0 | BUY_TP | 47.60 | 42768.42 | - |


## HomeRun Trade Explanations (Top 10 High Score)
| Timestamp | Score | Thresh | Regime | Slope | ADX | Dir | ExpMove |
|---|---|---|---|---|---|---|---|
| 2024-01-03 15:12:00 | 28.6 | 11.8 | TREND | -114.8 | 75.0 | SELL | 160.4 |
| 2024-01-03 15:11:00 | 28.4 | 18.0 | TREND | -112.6 | 76.0 | SELL | 161.4 |
| 2024-01-03 15:04:00 | 21.5 | 11.8 | TREND | -71.8 | 71.8 | SELL | 94.2 |
| 2024-01-03 14:55:00 | 19.5 | 18.0 | TREND | -68.9 | 62.6 | SELL | 37.5 |
| 2024-01-03 14:27:00 | 13.5 | 11.8 | TREND | -21.9 | 65.9 | SELL | 30.8 |
| 2024-01-02 03:25:00 | 11.3 | 6.0 | TREND | 14.3 | 59.0 | BUY | 26.0 |
| 2024-01-02 03:25:00 | 11.3 | 8.9 | TREND | 14.3 | 59.0 | BUY | 26.0 |
| 2024-01-03 15:27:00 | 11.1 | 8.9 | TREND | -31.5 | 41.0 | SELL | 70.0 |
| 2024-01-03 22:03:00 | 10.8 | 6.0 | TREND | -19.8 | 49.8 | SELL | 26.3 |
| 2024-01-03 22:03:00 | 10.8 | 8.9 | TREND | -19.8 | 49.8 | SELL | 26.3 |


## Top Blocked Trades (Cost Filter Rejects)
| Scenario | Timestamp | Score | ExpMove | Cost | Safety |
|---|---|---|---|---|---|
| B_HeavyRealism | 1704282900.0 | 19.5 | 37.5 | 20.0 | 2.0 |
| C_RiskCapped | 1704282900.0 | 19.5 | 37.5 | 20.0 | 2.0 |
| D_Strict | 1704282900.0 | 19.5 | 37.5 | 20.0 | 2.0 |
| B_HeavyRealism | 1704282960.0 | 18.2 | 39.8 | 20.0 | 2.0 |
| C_RiskCapped | 1704282960.0 | 18.2 | 39.8 | 20.0 | 2.0 |
| D_Strict | 1704282960.0 | 18.2 | 39.8 | 20.0 | 2.0 |
| B_HeavyRealism | 1704281340.0 | 15.9 | 32.7 | 20.0 | 2.0 |
| C_RiskCapped | 1704281340.0 | 15.9 | 32.7 | 20.0 | 2.0 |
| D_Strict | 1704281340.0 | 15.9 | 32.7 | 20.0 | 2.0 |
| B_HeavyRealism | 1704281400.0 | 15.4 | 35.7 | 20.0 | 2.0 |


## ExpMove Calibration (Prediction vs Reality)
| Scenario | AvgExp | AvgRealized | AvgNet | Corr(Exp, Real) | Corr(Exp, Net) | HitRate% (Real>Cost) |
|---|---|---|---|---|---|---|
| A_Baseline | 52.5 | 33.9 | 26.9 | -0.25 | -0.25 | 44.4% |
| B1_Sens_Slip0 | 66.8 | 99.0 | 88.0 | -0.46 | -0.46 | 50.0% |
| B2_Sens_Spr0 | 60.6 | -102.0 | -114.0 | -0.10 | -0.10 | 16.7% |
| B_HeavyRealism | 94.0 | -10.0 | -30.0 | -0.63 | -0.63 | 33.3% |
| C_RiskCapped | 94.0 | -10.0 | -30.0 | -0.63 | -0.63 | 33.3% |
| D_Strict | 49.1 | 90.1 | 70.1 | 1.00 | 1.00 | 50.0% |
| E_EdgeFiltered | 41.2 | -210.1 | -230.1 | -0.50 | -0.50 | 0.0% |
| F_HomeRun_Pctl | 40.8 | -210.1 | -230.1 | -0.51 | -0.51 | 0.0% |
| G_HomeRun_Strict_Pctl | 95.1 | 190.2 | 170.2 | -0.87 | -0.87 | 66.7% |
| H_HomeRun_p90 | 99.5 | 90.1 | 70.1 | -1.00 | -1.00 | 50.0% |


## Cost Model Verification
| Scenario | EstCost | ActualSlip (if avail) | EstError |
|---|---|---|---|
| A_Baseline | 7.0 | 2.00 | 1.00 |
| B1_Sens_Slip0 | 11.0 | 1.00 | 6.00 |
| B2_Sens_Spr0 | 12.0 | 2.00 | 6.00 |
| B_HeavyRealism | 20.0 | 10.00 | 6.00 |
| C_RiskCapped | 20.0 | 10.00 | 6.00 |
| D_Strict | 20.0 | 10.00 | 6.00 |
| E_EdgeFiltered | 20.0 | 10.00 | 6.00 |
| F_HomeRun_Pctl | 20.0 | 10.00 | 6.00 |
| F_Legacy60_Mult3 | 20.0 | nan | nan |
| G_HomeRun_Strict_Pctl | 20.0 | 10.00 | 6.00 |
| H_HomeRun_p90 | 20.0 | 10.00 | 6.00 |

    
## Retroactive Calibration (Backfill)
Generated from 38 trades.

| Metric | Pearson | Spearman |
|---|---|---|
| Exp vs Realized | -0.27 | -0.29 |
| Exp vs Net | -0.28 | -0.29 |

### Reliability Bins
| Bin (ExpMove) | Count | AvgRealized | HitRate |
|---|---|---|---|
| (14.199, 24.5] | 9 | -32.6 | 33.3% |
| (24.5, 32.92] | 6 | -8.4 | 33.3% |
| (32.92, 54.56] | 8 | 243.3 | 75.0% |
| (54.56, 104.16] | 7 | -36.3 | 28.6% |
| (104.16, 161.4] | 8 | -206.0 | 0.0% |

