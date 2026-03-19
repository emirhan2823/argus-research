import argparse
import csv
import os
from argus_py.data.loader import DataLoader

def run_baselines(data_dir, symbol, start_balance):
    print(f"--- Baselines: {symbol} ${start_balance} ---")
    market = DataLoader.load_from_dir(data_dir)
    bars = market._all_bars
    
    if not bars:
        print("No data found.")
        return

    # 1. No Trade
    no_trade_equity = start_balance
    
    # 2. Buy & Hold
    # Buy at Close of Bar 0
    entry_price = bars[0].close
    qty = start_balance / entry_price
    # Simple friction-less B&H for baseline comparison
    
    results = []
    
    for b in bars:
        bh_val = qty * b.close
        results.append({
            "Timestamp": b.timestamp,
            "Date": b.dt,
            "BuyHold": bh_val,
            "NoTrade": no_trade_equity
        })
        
    final_bh = results[-1]["BuyHold"]
    bh_ret = ((final_bh / start_balance) - 1) * 100
    
    print(f"Buy & Hold Final: ${final_bh:.2f} ({bh_ret:.2f}%)")
    
    # Save
    out_dir = "argus_py/lab/results"
    if not os.path.exists(out_dir): os.makedirs(out_dir)
    
    path = os.path.join(out_dir, "baselines.csv")
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Timestamp", "Date", "BuyHold", "NoTrade"])
        writer.writeheader()
        writer.writerows(results)
        
    print(f"Baselines saved to {path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--start_balance", type=float, default=1000)
    args = parser.parse_args()
    
    run_baselines(args.data_dir, "BTCUSDT", args.start_balance)
