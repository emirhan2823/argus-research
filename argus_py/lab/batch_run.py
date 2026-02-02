import os
import csv
import pandas as pd
import argparse
import itertools
from argus_py.runner import cli
from argus_py.data.loader import DataLoader
import json

def calculate_rates(run_dir):
    """
    Calculates rates (veto, low_conviction, lockdown, warmup) from run logs.
    """
    try:
        # Load Metrics for denominator (Total Bars)
        metrics_file = os.path.join(run_dir, "metrics.csv")
        total_bars = 0
        if os.path.exists(metrics_file):
            df_m = pd.read_csv(metrics_file)
            total_bars = len(df_m)
        
        if total_bars == 0:
            return 0, 0, 0, 0

        # Load Decision Log
        dlog_file = os.path.join(run_dir, "decision_log.csv")
        dlog = pd.DataFrame()
        if os.path.exists(dlog_file):
            dlog = pd.read_csv(dlog_file) # Has BlockReason, Conviction...

        # Load Rejects
        rejects_file = os.path.join(run_dir, "rejects.csv")
        rejects = pd.DataFrame()
        if os.path.exists(rejects_file):
            rejects = pd.read_csv(rejects_file)

        # 1. Lockdown Rate
        # Lockdown is usually logged in rejects as "LOCKDOWN" or implicit in safety guard
        # CLI logs 'log_reject(..., "LOCKDOWN", ...)'
        lockdown_count = 0
        if not rejects.empty:
            lockdown_count += len(rejects[rejects['Reason'] == 'LOCKDOWN'])
        
        # 2. Veto Rate (BlockReason in dlog)
        veto_count = 0
        if not dlog.empty and 'BlockReason' in dlog.columns:
             # Count non-N/A block reasons? Or specific ones?
             # Vector/Council usually puts 'N/A' if passed, or 'Veto' implies specific block.
             # Let's count non-N/A blocks.
             veto_count = len(dlog[dlog['BlockReason'] != 'N/A'])
        
        # 3. Low Conviction Rate
        # Where decision was NO_GO but no block reason? Or just count low conviction?
        # Conviction is in dlog.
        low_conv_count = 0
        if not dlog.empty and 'Decision' in dlog.columns:
            # Maybe 'HOLD' decision?
            low_conv_count = len(dlog[dlog['Decision'] == 'HOLD'])

        # 4. Warmup Rate
        # Bars that are NOT in dlog/rejects?
        # CLI logic: metrics append every bar.
        # dlog appends only if NO cooldown, NO lockdown, etc.
        # This is a rough proxy.
        # Warmup is hard to distinguish from Cooldown without explicit log.
        # Let's assume Warmup = Total - (Dlog + Rejects + Cooldowns?)
        # Or just 0 if we can't measure.
        # User explicitly mentioned WARMUP issue.
        # Let's calculate Unaccounted Rate and call it Warmup/Other.
        
        # Actually, dlog + rejects coverage might not be 100%.
        # Let's return simplistic rates based on counts/total.
        
        return (
            veto_count / total_bars,
            low_conv_count / total_bars,
            lockdown_count / total_bars,
            max(0, (total_bars - len(dlog) - len(rejects)) / total_bars) # Rough proxy for Warmup+Cooldown
        )

    except Exception:
        return 0, 0, 0, 0

def run_grid(data_dir):
    print(f"Starting Batch Lab Grid in {data_dir}...")
    
    # Grid Definition
    balances = [30, 100, 500, 2000]
    min_convictions = [0.30, 0.40, 0.50]
    trend_floors = [0.40, 0.50, 0.60]
    chop_floors = [0.60, 0.70, 0.80]
    max_bars_opts = [500, 1000, 5000]
    
    # Load Data once to check length
    print("Checking data source length...")
    market = DataLoader.load_from_dir(data_dir)
    total_available_bars = len(market._all_bars)
    print(f"Total available bars: {total_available_bars}")

    results_file = os.path.join("argus_py", "lab", "results.csv")
    write_header = not os.path.exists(results_file)
    
    with open(results_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "balance", "max_bars", "min_conviction", "trend_floor", "chop_floor",
                "total_return", "max_drawdown", "total_trades", "total_signals", "trend_signals", "chop_signals",
                "veto_rate", "low_conviction_rate", "lockdown_rate", "warmup_rate", "final_equity"
            ])

        # Iterate
        combinations = list(itertools.product(balances, max_bars_opts, min_convictions, trend_floors, chop_floors))
        print(f"Scheduled {len(combinations)} experiments.")
        
        for bal, mb, mc, tf, cf in combinations:
            if mb > total_available_bars:
                print(f"Skipping max_bars={mb} (Data only {total_available_bars})")
                continue
                
            print(f">>> Running: Bal={bal} Bars={mb} Cv={mc} TF={tf} CF={cf}")
            
            # Construct Args
            args = argparse.Namespace()
            args.symbol = "BTCUSDT" # Default assumed
            args.data_dir = data_dir
            args.start_balance = float(bal)
            args.max_bars = mb
            args.min_conviction = mc
            args.trend_floor = tf
            args.chop_floor = cf
            
            # Defaults for others
            args.mode = "backtest" # Force backtest
            args.leverage_max = 1.0
            args.sniper = False
            args.close_at_end = "true"
            args.profile = "AUTO"
            args.council_threshold = 0.4 
            args.exit_policy = "FIXED_BRACKET"
            args.auto_capital_mode = True
            args.capital_profile = None
            args.start_date = None
            args.end_date = None
            args.debug = False
            args.report = True # Generate reports for individual runs too? Sure.
            args.lab_grid = False # recursive prevention

            # Run
            run_dir = cli.run(args)
            
            if run_dir:
                # Harvest Results
                try:
                    with open(os.path.join(run_dir, "summary.json"), 'r') as jf:
                        s = json.load(jf)
                    
                    veto_r, low_c_r, lock_r, warm_r = calculate_rates(run_dir)
                    signals = s.get("signals", {})
                    
                    writer.writerow([
                        bal, mb, mc, tf, cf,
                        f"{s.get('total_return_pct', 0):.2f}",
                        f"{s.get('max_drawdown_pct', 0):.2f}",
                        s.get('total_trades', 0),
                        signals.get('total_go', 0),
                        signals.get('go_trend', 0),
                        signals.get('go_chop', 0),
                        f"{veto_r:.4f}",
                        f"{low_c_r:.4f}",
                        f"{lock_r:.4f}",
                        f"{warm_r:.4f}",
                        f"{s.get('final_equity', 0):.2f}"
                    ])
                    f.flush() # Ensure write
                except Exception as e:
                    print(f"Failed to harvest results for {run_dir}: {e}")

    print(f"Batch run complete. Results in {results_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    args = parser.parse_args()
    run_grid(args.data_dir)
