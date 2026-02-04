#!/usr/bin/env python3
import sys
import os
import pandas as pd
import hashlib

def get_scenarios(pack_dir):
    return [d for d in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, d)) and not d.startswith('.')]

def get_trades(scenario_dir):
    dump_path = os.path.join(scenario_dir, "calibration_dump.csv")
    if not os.path.exists(dump_path):
        return pd.DataFrame()
    return pd.read_csv(dump_path)

def compute_hash(df):
    if df.empty: return "Empty"
    # Key columns for identity
    cols = ['EntryTs', 'ExitTs', 'Direction', 'EntryPrice', 'ExitPrice']
    # Ensure they exist
    for c in cols:
        if c not in df.columns: return "MissingCols"
    
    df_sorted = df.sort_values(by=cols)
    raw = ""
    for _, row in df_sorted.iterrows():
        raw += f"{row['EntryTs']}|{row['Direction']};"
    return hashlib.sha1(raw.encode()).hexdigest()[:8]

def check_divergence(pack_dir, baseline_name="A_Baseline_Norm"):
    print(f"Checking Divergence in: {pack_dir}")
    print(f"Baseline: {baseline_name}")
    
    baseline_dir = os.path.join(pack_dir, baseline_name)
    if not os.path.exists(baseline_dir):
        print(f"Error: Baseline {baseline_name} not found.")
        return 1
        
    base_df = get_trades(baseline_dir)
    base_count = len(base_df)
    base_hash = compute_hash(base_df)
    
    print(f"Baseline Trades: {base_count}")
    print(f"Baseline Hash: {base_hash}")
    
    scenarios = get_scenarios(pack_dir)
    divergence_found = False
    
    print(f"\n{'Scenario':<25} | {'Trades':<6} | {'Hash':<10} | {'Status'}")
    print("-" * 60)
    
    for sc in sorted(scenarios):
        if sc == baseline_name: continue
        
        sc_dir = os.path.join(pack_dir, sc)
        sc_df = get_trades(sc_dir)
        sc_count = len(sc_df)
        sc_hash = compute_hash(sc_df)
        
        is_identical = (sc_hash == base_hash)
        
        status = "IDENTICAL (FAIL)" if is_identical else "DIVERGENT (PASS)"
        if not is_identical:
            divergence_found = True
            
        print(f"{sc:<25} | {sc_count:<6} | {sc_hash:<10} | {status}")
        
    print("-" * 60)
    
    if divergence_found:
        print("\nSUCCESS: At least one scenario diverged from baseline.")
        return 0
    else:
        print("\nFAILURE: All scenarios match baseline exactly.")
        return 2

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pack_divergence_check.py <pack_dir> [baseline_name]")
        sys.exit(1)
        
    pack = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "A_Baseline_Norm"
    
    sys.exit(check_divergence(pack, base))
