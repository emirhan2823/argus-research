import pandas as pd
import argparse
import os
import csv
from typing import List, Dict

def save_capital_log(run_dir: str, logs: List[Dict]):
    """
    Saves the list of capital snapshots to capital_evolution.csv
    """
    if not logs: return
    
    cap_path = os.path.join(run_dir, "capital_evolution.csv")
    try:
        with open(cap_path, 'w', newline='') as f:
            fieldnames = ["Timestamp", "Equity", "Profile", "Risk", "LevCap", "Mode", "DD", "WinRate20"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(logs)
        print(f"Capital log saved to: {cap_path}")
    except Exception as e:
        print(f"Error saving capital log: {e}")

def generate_report(run_dir):
    csv_path = os.path.join(run_dir, "capital_evolution.csv")
    if not os.path.exists(csv_path):
        print(f"No capital logs found in {run_dir}")
        return

    df = pd.read_csv(csv_path)
    
    print("\n=== Capital Evolution Report ===")
    print(f"Total Bars: {len(df)}")
    print(f"Start Equity: {df['Equity'].iloc[0]:.2f}")
    print(f"End Equity: {df['Equity'].iloc[-1]:.2f}")
    
    # 1. Profile Distribution
    dist = df['Profile'].value_counts()
    print("\n--- Profile Distribution (Bars) ---")
    print(dist)
    
    # 2. Risk Dynamics
    print("\n--- Risk Stats ---")
    print(f"Avg Risk %: {df['Risk'].mean()*100:.2f}%")
    print(f"Max Risk %: {df['Risk'].max()*100:.2f}%")
    print(f"Min Risk %: {df['Risk'].min()*100:.2f}%")
    
    # 3. Drawdown by Profile
    print("\n--- Max DD by Profile ---")
    profiles = df['Profile'].unique()
    for p in profiles:
        sub = df[df['Profile'] == p]
        max_dd = sub['DD'].max()
        print(f"{p}: {max_dd*100:.2f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    args = parser.parse_args()
    
    generate_report(args.run_dir)
