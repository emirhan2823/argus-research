
import os
import sys
import pandas as pd
import glob

RUNS_DIR = "runs"

def get_latest_pack(prefix):
    packs = glob.glob(os.path.join(RUNS_DIR, f"{prefix}*"))
    if not packs: return None
    # Sort by creation time (name usually contains timestamp, so sort by name works too)
    return sorted(packs)[-1]

def parse_diagnostics(pack_dir):
    # We can parse diagnostics.md or just look at summary.json inside each run
    # Let's parse diagnostics.md for the summary table
    diag_path = os.path.join(pack_dir, "diagnostics.md")
    if not os.path.exists(diag_path): return []
    
    rows = []
    with open(diag_path, 'r') as f:
        in_table = False
        headers = []
        for line in f:
            line = line.strip()
            if "| Scenario |" in line:
                in_table = True
                headers = [h.strip() for h in line.split('|') if h.strip()]
                continue
            if in_table and line.startswith("|--"): continue
            if in_table and line.startswith("|"):
                # Table row
                parts = [p.strip() for p in line.split('|') if p] # Don't strip empty strings if they are valid cols?
                # Actually split('|') might produce empty first/last if line starts/ends with |
                # The regex approach is better but let's be simple.
                
                # Check if it looks like a row
                if len(parts) >= len(headers):
                    row = {headers[i]: parts[i] for i in range(len(headers))}
                    rows.append(row)
                else:
                    # End of table?
                    pass
            elif in_table and not line:
                break
    return rows

def print_result_table(title, rows, cols=None):
    if not rows:
        print(f"\n### {title}: No Data")
        return

    if cols is None:
        cols = ["Scenario", "Net PnL", "Trades (Ev)", "WR%"]
        
    print(f"\n### {title}")
    # Markdown Table
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    print(header)
    print(sep)
    
    for r in rows:
        # Clean up keys if needed (Scenario vs # Scenario)
        # diagnostics.md has "| Scenario |..."
        vals = [r.get(c, "-") for c in cols]
        print("| " + " | ".join(vals) + " |")

def main():
    print("# Robustness Report (V5 AdxGate)\n")
    
    # 1. ADX Sweep
    pack_adx = get_latest_pack("sweep_adx")
    if pack_adx:
        rows = parse_diagnostics(pack_adx)
        print_result_table("1. Parameter Stability (ADX 30-60)", rows)
        print(f"\n*Source: {pack_adx}*")
        
    # 2. Asset Sweep
    pack_asset = get_latest_pack("sweep_assets")
    if pack_asset:
        rows = parse_diagnostics(pack_asset)
        print_result_table("2. Cross-Asset Generalization (Jan 2024)", rows)
        print(f"\n*Source: {pack_asset}*")

    # 3. Temporal Sweep
    pack_temp = get_latest_pack("sweep_temporal")
    if pack_temp:
        rows = parse_diagnostics(pack_temp)
        print_result_table("3. Temporal Robustness (BTC 2023 H2)", rows)
        print(f"\n*Source: {pack_temp}*")

if __name__ == "__main__":
    main()
