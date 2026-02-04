#!/usr/bin/env python3
import sys
import os
import pandas as pd

def check_collisions(pack_dir):
    print(f"Checking PID collisions in: {pack_dir}")
    
    
    # Check if single run (has trades.csv directly)
    if os.path.exists(os.path.join(pack_dir, "trades.csv")):
        scenarios = ["."]
    else:
        scenarios = [d for d in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, d)) and not d.startswith(".")]
    
    if not scenarios:
        print("No scenarios found.")
        return 0
        
    any_fail = False
    
    for sc in scenarios:
        trades_path = os.path.join(pack_dir, sc, "trades.csv")
        if not os.path.exists(trades_path):
            continue
            
        try:
            df = pd.read_csv(trades_path)
            if df.empty: continue
            
            # Filter for OPEN events
            opens = df[df['Event'] == 'OPEN']
            if opens.empty: continue
            
            # Check duplicates in PositionId
            dupes = opens[opens.duplicated(subset=['PositionId'], keep=False)]
            
            if not dupes.empty:
                print(f"FAIL: {sc} has {len(dupes)} PID collisions!")
                print(dupes[['Timestamp', 'Symbol', 'Side', 'Price', 'PositionId']].head())
                any_fail = True
            else:
                print(f"PASS: {sc} ({len(opens)} opens) - Unique PIDs.")
                
        except Exception as e:
            print(f"Error reading {sc}: {e}")
            
    if any_fail:
        return 1
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_pid_collision_safety.py <pack_dir>")
        sys.exit(1)
        
    sys.exit(check_collisions(sys.argv[1]))
