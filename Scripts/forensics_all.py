
import pandas as pd
import sys

# Load dump
df = pd.read_csv("runs/pack_20260202_133137/calibration_dump.csv")
df = df[df['Scenario'] == 'A_Baseline_Norm']

print("--- All Trades (Baseline) ---")
print(df[['Direction', 'Net', 'ADX', 'Slope']].to_string())
