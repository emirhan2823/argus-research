
import pandas as pd
import sys

# Load dump
df = pd.read_csv("runs/pack_20260202_133137/calibration_dump.csv")

# Filter Baseline to see raw trades
df = df[df['Scenario'] == 'A_Baseline_Norm']

winning_sells = df[(df['Direction'] == 'SELL') & (df['Net'] > 0)]
losing_buys = df[(df['Direction'] == 'BUY') & (df['Net'] < 0)]

print("--- Winning SELLs (Baseline) ---")
print(winning_sells[['EntryTs', 'Net', 'Slope', 'ADX', 'ExpMove']].describe())

print("\n--- Losing BUYs (Baseline) ---")
print(losing_buys[['EntryTs', 'Net', 'Slope', 'ADX', 'ExpMove']].describe())

if not winning_sells.empty:
    print("\nSample Win SELL:")
    print(winning_sells.iloc[0])
if not losing_buys.empty:
    print("\nSample Lose BUY:")
    print(losing_buys.iloc[0])
