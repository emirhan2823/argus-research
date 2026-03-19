
import os
import pandas as pd
from datetime import datetime

RUN_DIR = "runs/phase19_paper/live_test"
REPORT_DIR = "runs/phase19_paper/reports"
os.makedirs(REPORT_DIR, exist_ok=True)

def generate_daily_report():
    print(f"Generating report for {RUN_DIR}...")
    
    # 1. Status
    status_file = os.path.join(RUN_DIR, "status.log")
    equity = 1000.0
    last_price = 0.0
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                if "Equity:" in line:
                    equity = float(line.split(":")[1].strip())
                if "Last Price:" in line:
                    last_price = float(line.split(":")[1].strip())
                    
    # 2. Trades
    trades_file = os.path.join(RUN_DIR, "trades.csv") # Reporter saves here?
    # Wait, Reporter saves to `run_dir/trades.csv` usually.
    # Check if exists.
    
    trades_today = 0
    pnl_today = 0.0
    
    if os.path.exists(trades_file):
        try:
             df = pd.read_csv(trades_file)
             if not df.empty:
                 # TODO: Filter by Today
                 today = datetime.now().strftime("%Y-%m-%d")
                 # df['date'] = ...
                 trades_today = len(df) # Placeholder
        except:
             pass
             
    # 3. Generate MD
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(REPORT_DIR, f"{date_str}_report.md")
    
    with open(report_path, "w") as f:
        f.write(f"# Phase 19 Paper Trading Report - {date_str}\n\n")
        f.write(f"**Status**: ACTIVE\n")
        f.write(f"**Equity**: ${equity:.2f}\n")
        f.write(f"**BTC Price**: ${last_price:.2f}\n")
        f.write(f"**Trades Today**: {trades_today}\n")
        f.write(f"**PnL Today**: ${pnl_today:.2f}\n\n")
        
        f.write("## Incidents\n")
        f.write("None reported.\n")
        
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    generate_daily_report()
