#!/usr/bin/env python3
import sys
import os
import glob
import pandas as pd
import hashlib

def get_scenarios(pack_dir):
    return [d for d in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, d)) and not d.startswith('.')]

def get_fingerprint(scenario_dir):
    """
    Computes fingerprint from calibration_dump.csv if available.
    Keys: EntryTs, ExitTs, Direction, EntryPrice, ExitPrice, Realized, Net
    """
    dump_path = os.path.join(scenario_dir, "calibration_dump.csv")
    if not os.path.exists(dump_path):
        return 0, "NoDump"
        
    df = pd.read_csv(dump_path)
    if df.empty:
        return 0, "Empty"
        
    # Sort
    df = df.sort_values(by=['EntryTs', 'Direction'])
    
    # Hash content
    raw = ""
    for _, row in df.iterrows():
        raw += f"{row['EntryTs']}|{row['ExitTs']}|{row['Direction']}|{row['EntryPrice']:.4f}|{row['ExitPrice']:.4f}|{row['Realized']:.2f}|{row['Net']:.2f};"
        
    sig = hashlib.sha1(raw.encode()).hexdigest()[:8]
    return len(df), sig

def verify(pack1, pack2):
    print(f"Verifying Determinism:\n  Pack1: {pack1}\n  Pack2: {pack2}\n")
    
    sc1 = set(get_scenarios(pack1))
    sc2 = set(get_scenarios(pack2))
    
    if sc1 != sc2:
        print(f"FAIL: Scenario mismatch.\n  Pack1: {sc1}\n  Pack2: {sc2}")
        return False
        
    report = []
    all_pass = True
    
    print("| Scenario | Rows (P1/P2) | Hash (P1/P2) | Match |")
    print("|---|---|---|---|")
    
    for sc in sorted(list(sc1)):
        n1, h1 = get_fingerprint(os.path.join(pack1, sc))
        n2, h2 = get_fingerprint(os.path.join(pack2, sc))
        
        match = (n1 == n2) and (h1 == h2)
        status = "PASS" if match else "FAIL"
        if not match: all_pass = False
        
        print(f"| {sc} | {n1}/{n2} | {h1}/{h2} | {status} |")
        report.append(f"| {sc} | {n1}/{n2} | {h1}/{h2} | {status} |")

    # Generate Report File
    report_path = "runs/phase15_determinism_report.md"
    with open(report_path, "w") as f:
        f.write(f"# Phase 15 Determinism Verification\n")
        f.write(f"Pack 1: {pack1}\nPack 2: {pack2}\n\n")
        f.write("| Scenario | Rows | Hash | Result |\n|---|---|---|---|\n")
        for line in report:
            f.write(line + "\n")
        f.write(f"\n**Final Result**: {'PASS' if all_pass else 'FAIL'}\n")
        
    print(f"\nReport written to {report_path}")
    return all_pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: verify_determinism.py <pack_dir_1> <pack_dir_2>")
        sys.exit(1)
        
    p1 = sys.argv[1]
    p2 = sys.argv[2]
    
    if verify(p1, p2):
        print("SUCCESS: Packs are identical.")
        sys.exit(0)
    else:
        print("FAILURE: Packs differ.")
        sys.exit(1)
