
import os
import sys
import pandas as pd
import numpy as np
import json
import argparse
from typing import List, Dict, Any

def calculate_spearman(df: pd.DataFrame, col1: str, col2: str):
    """
    Robust Spearman Rank Correlation calculation without scipy dependency.
    """
    try:
        rank1 = df[col1].rank()
        rank2 = df[col2].rank()
        return rank1.corr(rank2)
    except:
        return np.nan

def process_pack(pack_dir: str, force: bool = False):
    print(f"Processing Pack: {pack_dir}")
    scenarios = [d for d in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, d))]
    
    all_calibration_rows = []
    
    for sc in sorted(scenarios):
        sc_dir = os.path.join(pack_dir, sc)
        tp = os.path.join(sc_dir, "trades.csv")
        dl = os.path.join(sc_dir, "decision_log.csv")
        cfg_p = os.path.join(sc_dir, "config.json")
        dump_path = os.path.join(sc_dir, "calibration_dump.csv") # Per scenario? Or Pack root? User said "Scenario klasörlerinde calibration_dump.csv üret"
        
        # Check overwrite
        if os.path.exists(dump_path) and not force:
            print(f"  [SKIP] {sc}: calibration_dump.csv exists (use --force to overwrite)")
            # Try to read it to add to aggregate?
            try:
                sdf = pd.read_csv(dump_path)
                all_calibration_rows.extend(sdf.to_dict('records'))
            except: pass
            continue
            
        if not (os.path.exists(tp) and os.path.exists(dl)):
            continue
            
        try:
            df_t = pd.read_csv(tp)
            df_d = pd.read_csv(dl)
            
            # Load Config for Cost Fallback
            c_fee, c_slip, c_spread = 4.0, 2.0, 1.0 # Defaults
            if os.path.exists(cfg_p):
                with open(cfg_p) as cf: 
                    c = json.load(cf)
                    c_fee = c.get('fee_bps', 4.0)
                    c_slip = c.get('slippage_bps', 2.0)
                    c_spread = c.get('spread_bps', 1.0)
            def_cost = c_fee + c_slip + c_spread
            use_bid_ask = False # Assume simple for now unless in config
            
            # --- Matching Logic ---
            entries = df_t[df_t['Event'] == 'OPEN'].copy()
            exits = df_t[df_t['Event'] == 'CLOSE'].copy()
            
            # Map exits by ID
            pid_map = {}
            if 'PositionId' in exits.columns:
                for _, row in exits.iterrows():
                    pid_map[row['PositionId']] = row
            
            scenario_rows = []
            
            for _, row in entries.iterrows():
                # 1. Match Decision
                match = None
                
                # A. Try Exact PositionId match (if exists in DL)
                if 'PositionId' in df_d.columns and 'PositionId' in row:
                     # Not usually in DL yet? Assuming no.
                     pass 
                
                # B. Try Timestamp Match (Exact or Window)
                ts_trade = row['Timestamp']
                
                # Filter DL by approx time (+- 60s)
                # DL usually logged BEFORE trade. 
                # Trade Ts = Execution Time. Decision Ts = Bar Close Time.
                # Usually identical in backtest (within microseconds).
                
                candidates = df_d[
                    (df_d['Timestamp'] >= ts_trade - 65.0) & 
                    (df_d['Timestamp'] <= ts_trade + 5.0)
                ]
                
                if not candidates.empty:
                    # Filter by Direction/Symbol if possible
                    # Symbol is implicit in Scenario usually.
                    # Direction check
                    side_map = {'BUY': 'BUY', 'SELL': 'SELL'} # Trade Side -> Decision Dir
                    if row['Side'] in side_map:
                        target_dir = side_map[row['Side']]
                        candidates = candidates[candidates['Direction'] == target_dir]
                    
                    if not candidates.empty:
                        # Take closest or last
                        match = candidates.iloc[-1]
                
                if match is not None:
                    # Extract Metrics
                    exp_move = match['ExpMove'] if 'ExpMove' in match else np.nan
                    cost = match['Cost'] if 'Cost' in match else def_cost
                    
                    # Exit Info
                    pid = row['PositionId'] if 'PositionId' in row else "unknown"
                    exit_price = row['Price'] # Default to entry if open?
                    exit_ts = row['Timestamp']
                    
                    if pid in pid_map:
                        exit_row = pid_map[pid]
                        exit_price = exit_row['Price']
                        exit_ts = exit_row['Timestamp']
                    
                    # Realized
                    entry_price = row['Price']
                    direction = 1 if row['Side'] == 'BUY' else -1
                    realized_bps = ((exit_price - entry_price) / entry_price) * 10000.0 * direction
                    
                    # Net
                    net_bps = realized_bps - cost
                    
                    # Score/SafetyFactor from DL
                    score_val = match['Score'] if 'Score' in match else np.nan
                    sf_val = match['SafetyFactor'] if 'SafetyFactor' in match else np.nan
                    
                    data = {
                        "Scenario": sc,
                        "PositionId": pid,
                        "EntryTs": row['Timestamp'],
                        "ExitTs": exit_ts,
                        "Direction": row['Side'], # Trade Side
                        "EntryPrice": entry_price,
                        "ExitPrice": exit_price,
                        "ExpMove": exp_move,
                        "Cost": cost,
                        "Realized": realized_bps,
                        "Net": net_bps,
                        "Slope": match.get('AegeanSlope', np.nan),
                        "ADX": match.get('OrionADX', np.nan),
                        "Regime": match.get('Regime', 'N/A'),
                        "Score": score_val,
                        "SafetyFactor": sf_val
                    }
                    scenario_rows.append(data)
            
            if scenario_rows:
                # Save Scenarion Dump
                sdf = pd.DataFrame(scenario_rows)
                print(f"  [OK] {sc}: Generated {len(sdf)} calibration rows.")
                sdf.to_csv(dump_path, index=False)
                all_calibration_rows.extend(scenario_rows)
            else:
                 print(f"  [WARN] {sc}: No matched trades found.")
                 
        except Exception as e:
            print(f"  [ERR] {sc}: {str(e)}")

    # Update Diagnostics if we have data
    if all_calibration_rows:
        update_diagnostics(pack_dir, all_calibration_rows)

def update_diagnostics(pack_dir, rows):
    diag_path = os.path.join(pack_dir, "diagnostics.md")
    df = pd.DataFrame(rows)
    # Drop rows where ExpMove is NaN (cannot calibrate)
    valid_df = df.dropna(subset=['ExpMove', 'Realized'])
    
    if valid_df.empty:
        print("  [INFO] No valid ExpMove/Realized pairs for diagnostics update.")
        return

    # 1. Correlations
    corr_p_real = valid_df['ExpMove'].corr(valid_df['Realized'], method='pearson')
    corr_s_real = calculate_spearman(valid_df, 'ExpMove', 'Realized')
    
    corr_p_net = valid_df['ExpMove'].corr(valid_df['Net'], method='pearson')
    corr_s_net = calculate_spearman(valid_df, 'ExpMove', 'Net')
    
    # 2. Binning
    bins_md = ""
    try:
        valid_df['Bin'] = pd.qcut(valid_df['ExpMove'], q=5, duplicates='drop')
        grouped = valid_df.groupby('Bin', observed=True)
        stats = grouped.agg({'ExpMove': 'count', 'Realized': 'mean', 'Cost': 'mean'})
        # Hitrates map
        def calc_hr(g): return (len(g[g['Realized'] > g['Cost']]) / len(g)) * 100.0
        hitrates = grouped.apply(calc_hr)
        
        bins_md += "| Bin (ExpMove) | Count | AvgRealized | HitRate |\n|---|---|---|---|\n"
        for i, row in stats.iterrows():
            bins_md += f"| {i} | {int(row['ExpMove'])} | {row['Realized']:.1f} | {hitrates[i]:.1f}% |\n"
    except Exception as e:
        bins_md = f"Error generating bins: {e}\n"

    # Append to MD
    new_section = f"""
    
## ExpMove Calibration (Retroactive Backfill)
Generated from {len(valid_df)} trades.

| Metric | Pearson | Spearman |
|---|---|---|
| Exp vs Realized | {corr_p_real:.2f} | {corr_s_real:.2f} |
| Exp vs Net | {corr_p_net:.2f} | {corr_s_net:.2f} |

### Reliability Bins
{bins_md}
"""
    # Append
    with open(diag_path, 'a') as f:
        f.write(new_section)
    print(f"Updated {diag_path} with Backfill Metrics.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", help="Path to specific Pack dir")
    parser.add_argument("--all", action="store_true", help="Process all packs in runs/")
    parser.add_argument("--force", action="store_true", help="Overwrite existing dump files")
    
    args = parser.parse_args()
    
    if args.pack:
        process_pack(args.pack, args.force)
    elif args.all:
        import glob
        runs = glob.glob("runs/pack_*") + glob.glob("runs/2*") # timestamped dirs
        # Filter for directories
        runs = [r for r in runs if os.path.isdir(r)]
        for r in runs:
            process_pack(r, args.force)
