import argparse
import subprocess
import glob
import json
import os
import shutil
from datetime import datetime, timedelta
import pandas as pd
import time

class WalkForwardOptimizer:
    def __init__(self, data_dir, symbol, start_balance, data_range_start, data_range_end, train_days=14, test_days=7):
        self.data_dir = data_dir
        self.symbol = symbol
        self.start_balance = start_balance
        self.train_days = train_days
        self.test_days = test_days
        
        # Parse Dates
        self.start_dt = datetime.strptime(data_range_start, "%Y-%m-%d")
        self.end_dt = datetime.strptime(data_range_end, "%Y-%m-%d")
        
        # Grid Params
        self.profiles = ["BALANCED", "DEFENSIVE"] 
        self.thresholds = [0.3, 0.4, 0.5]
        
    def run(self):
        print(f"--- Walk-Forward: {self.start_dt.date()} to {self.end_dt.date()} ---")
        
        curr = self.start_dt
        oos_results = []
        
        while curr + timedelta(days=self.train_days + self.test_days) <= self.end_dt:
            # Define Windows
            train_end = curr + timedelta(days=self.train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_days)
            
            t_s_str = curr.strftime("%Y-%m-%d")
            t_e_str = train_end.strftime("%Y-%m-%d")
            test_s_str = test_start.strftime("%Y-%m-%d")
            test_e_str = test_end.strftime("%Y-%m-%d")
            
            print(f"\n>> Window: Train[{t_s_str}:{t_e_str}] -> Test[{test_s_str}:{test_e_str}]")
            
            # 1. OPTIMIZE (Grid Search on Train)
            best_params = self.optimize(t_s_str, t_e_str)
            print(f"   Best Params: {best_params}")
            
            # 2. VALIDATE (Run on Test)
            res = self.run_epoch(test_s_str, test_e_str, best_params, is_test=True)
            
            if res:
                oos_results.append({
                    "TestStart": test_s_str,
                    "TestEnd": test_e_str,
                    "Profile": best_params['profile'],
                    "Threshold": best_params['threshold'],
                    "Return": res.get('total_return_pct', 0.0),
                    "MaxDD": res.get('max_drawdown_pct', 0.0),
                    "Trades": res.get('total_trades', 0),
                    "FinalEq": res.get('final_equity', 0.0)
                })
            
            # Step forward
            curr = curr + timedelta(days=self.test_days)

        self.save_results(oos_results)

    def optimize(self, start_date, end_date):
        best_score = -9999
        best_cfg = {"profile": "BALANCED", "threshold": 0.4}
        
        for p in self.profiles:
            for t in self.thresholds:
                res = self.run_epoch(start_date, end_date, {"profile": p, "threshold": t})
                if res:
                    # Score = Return / (DD + 0.1) 
                    ret = res.get('total_return_pct', 0.0)
                    dd = res.get('max_drawdown_pct', 0.0)
                    score = ret # Simple Return maximization for now
                    
                    if score > best_score:
                        best_score = score
                        best_cfg = {"profile": p, "threshold": t}
        return best_cfg

    def run_epoch(self, start_date, end_date, params, is_test=False):
        # Run CLI
        cmd = [
            "python3", "argus_py/runner/cli.py",
            "--symbol", self.symbol,
            "--data_dir", self.data_dir,
            "--start_balance", str(self.start_balance),
            "--mode", "adaptive",
            "--profile", params['profile'],
            "--council_threshold", str(params['threshold']),
            "--start_date", start_date,
            "--end_date", end_date,
            "--close_at_end", "true"
        ]
        
        # Suppress output during optimization
        capture = True 
        try:
            subprocess.run(cmd, check=True, capture_output=capture)
        except subprocess.CalledProcessError:
            return None
            
        # Parse result
        # Find latest run
        list_of_files = glob.glob('runs/*')
        if not list_of_files: return None
        latest_run = max(list_of_files, key=os.path.getctime)
        
        summary_path = os.path.join(latest_run, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                return json.load(f)
        return None

    def save_results(self, results):
        df = pd.DataFrame(results)
        if not df.empty:
            path = f"argus_py/lab/walkforward_results_{datetime.now().strftime('%Y%m%d')}.csv"
            df.to_csv(path, index=False)
            print(f"\nWalk-Forward Complete. Results saved to {path}")
            
            # Total Performance
            total_ret = ((df['FinalEq'] / self.start_balance) - 1).sum() # Rough approx of appended returns
            print(f"Cumulative Sum of Period Returns: {total_ret*100:.2f}%")
            print(df.to_string())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start_balance", type=float, default=1000)
    parser.add_argument("--start_date", required=True)
    parser.add_argument("--end_date", required=True)
    parser.add_argument("--train_days", type=int, default=14)
    parser.add_argument("--test_days", type=int, default=7)
    
    args = parser.parse_args()
    
    wf = WalkForwardOptimizer(
        args.data_dir, 
        args.symbol, 
        args.start_balance, 
        args.start_date, 
        args.end_date,
        args.train_days,
        args.test_days
    )
    wf.run()
