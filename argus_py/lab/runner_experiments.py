import os
import subprocess
import glob
import json
import csv
import argparse
from datetime import datetime

class ExperimentRunner:
    def __init__(self, data_dir, symbol="BTCUSDT"):
        self.data_dir = data_dir
        self.symbol = symbol
        self.results = []
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def run_scenario(self, start_balance, profile, mode="adaptive"):
        print(f"--- Running Scenario: ${start_balance} [{profile}] Mode:{mode} ---")
        
        # Command construction
        cmd = [
            "python3", "argus_py/runner/cli.py",
            "--symbol", self.symbol,
            "--data_dir", self.data_dir,
            "--start_balance", str(start_balance),
            "--mode", mode,
            "--profile", profile,
            "--close_at_end", "true"
        ]
        
        # Run
        try:
            subprocess.run(cmd, check=True, capture_output=True) # Capture output to keep console clean? Or let it stream?
            # Let's let it stream errors but capture output if we want.
            # actually better to just check return code.
        except subprocess.CalledProcessError as e:
            print(f"Error running scenario: {e}")
            return

        # Find latest run
        # Ideally CLI returns the run dir, but subprocess makes it hard.
        # We assume latest run in 'runs/' is ours.
        # Potential race condition if parallel, but this is sequential.
        
        list_of_files = glob.glob('runs/*') 
        latest_run = max(list_of_files, key=os.path.getctime)
        
        # Parse Summary
        summary_path = os.path.join(latest_run, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                data = json.load(f)
                
            self.results.append({
                "Scenario": f"${start_balance}_{profile}_{mode}",
                "Balance": start_balance,
                "Profile": profile,
                "Mode": mode,
                "FinalEquity": data.get("final_equity"),
                "ReturnPct": data.get("total_return_pct"),
                "MaxDD": data.get("max_drawdown_pct"),
                "Trades": data.get("total_trades"),
                "WinRate": data.get("win_rate"),
                "RunDir": latest_run
            })
        else:
            print(f"Warning: No summary.json found in {latest_run}")

    def save_report(self):
        filename = f"argus_py/lab/experiments_{self.experiment_id}.csv"
        keys = ["Scenario", "Balance", "Profile", "Mode", "FinalEquity", "ReturnPct", "MaxDD", "Trades", "WinRate", "RunDir"]
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.results)
            
        print(f"\nExperiment Report saved to: {filename}")
        
        # Print Table
        print(f"{'Scenario':<25} | {'Ret %':<8} | {'MDD %':<8} | {'Trades':<6} | {'FinalEq':<10}")
        print("-" * 75)
        for r in self.results:
            print(f"{r['Scenario']:<25} | {r['ReturnPct'] if r['ReturnPct'] else 0.0:<8.2f} | {r['MaxDD'] if r['MaxDD'] else 0.0:<8.4f} | {r['Trades']:<6} | {r['FinalEquity']:<10.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    args = parser.parse_args()
    
    runner = ExperimentRunner(args.data_dir)
    
    # E0/E1/E2/E3 Mixed Scenarios
    
    # 1. $30 Small Cap Survival
    runner.run_scenario(30, "DEGEN", "adaptive")
    runner.run_scenario(30, "BALANCED", "adaptive")
    
    # 2. $1000 Growth
    runner.run_scenario(1000, "BALANCED", "adaptive")
    runner.run_scenario(1000, "DEFENSIVE", "adaptive")
    
    # 3. Mode Comparison ($1000)
    runner.run_scenario(1000, "BALANCED", "conservative") # Hypothertical mode if supported logic exists
    
    runner.save_report()
