import os
import subprocess
import glob
import json
import csv
import argparse
from datetime import datetime
import pandas as pd

class GridSearchRunner:
    def __init__(self, data_dir, symbol="BTCUSDT", start_balance=1000):
        self.data_dir = data_dir
        self.symbol = symbol
        self.start_balance = start_balance
        self.results = []
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def run_config(self, profile, threshold, exit_policy):
        config_id = f"{profile}_{threshold}_{exit_policy}"
        print(f"--- Running Config: {config_id} ---")
        
        cmd = [
            "python3", "argus_py/runner/cli.py",
            "--symbol", self.symbol,
            "--data_dir", self.data_dir,
            "--start_balance", str(self.start_balance),
            "--mode", "adaptive",
            "--profile", profile,
            "--council_threshold", str(threshold),
            "--exit_policy", exit_policy,
            "--close_at_end", "true"
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running {config_id}: {e}")
            return

        # Parse Logic
        list_of_files = glob.glob('runs/*') 
        latest_run = max(list_of_files, key=os.path.getctime)
        
        summary_path = os.path.join(latest_run, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                data = json.load(f)
                
            self.results.append({
                "ConfigID": config_id,
                "Profile": profile,
                "Threshold": threshold,
                "ExitPolicy": exit_policy,
                "ReturnPct": data.get("total_return_pct"),
                "MaxDD": data.get("max_drawdown_pct"),
                "Trades": data.get("total_trades"),
                "WinRate": data.get("win_rate"),
                "ProfitFactor": data.get("profit_factor"),
                "FinalEquity": data.get("final_equity"),
                "RunDir": latest_run
            })

    def save_results(self):
        filename = f"runs/grid_compare_{self.experiment_id}.csv"
        df = pd.DataFrame(self.results)
        if not df.empty:
            df.sort_values(by="ReturnPct", ascending=False, inplace=True)
            df.to_csv(filename, index=False)
            print(f"\nGrid Search Complete. Results saved to {filename}")
            print(df.to_string(index=False))
        else:
             print("No results collected.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start_balance", type=float, default=1000)
    args = parser.parse_args()
    
    runner = GridSearchRunner(args.data_dir, args.symbol, args.start_balance)
    
    # Define Grid
    profiles = ["DEFENSIVE", "BALANCED", "DEGEN"]
    thresholds = [0.3, 0.4, 0.6]
    policies = ["FIXED_BRACKET", "TRAILING_STOP"]
    
    # Run Grid
    for p in profiles:
        for t in thresholds:
            for pol in policies:
                 runner.run_config(p, t, pol)
                 
    runner.save_results()
