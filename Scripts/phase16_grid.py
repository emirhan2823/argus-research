#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
import pandas as pd
import hashlib
import argparse

# Configuration
SYMBOL = "BTCUSDT"
START_DATE = "2024-02-01"
END_DATE = "2024-02-14"
DATA_DIR = "argus_py/data/cache"
BASE_CMD = [sys.executable, "-m", "argus_py.runner.cli"]

GRID_ADX = [20.0, 35.0, 50.0]
GRID_EXP = [40.0, 80.0]

def get_fingerprint(run_dir):
    dump = os.path.join(run_dir, "trades.csv")
    if not os.path.exists(dump): return 0, "N/A"
    try:
        df = pd.read_csv(dump)
        if df.empty: return 0, "Empty"
        
        # Sort and Hash (Trades.csv has 'Event', 'Timestamp')
        # We want OPEN events or all fills?
        # Let's simple hash: PositionId, Side, FillPrice
        df = df.sort_values(by=['Timestamp', 'PositionId'])
        raw = ""
        for _, row in df.iterrows():
            raw += f"{row['Timestamp']}|{row['Side']}|{row['FillPrice']};"
        sig = hashlib.sha1(raw.encode()).hexdigest()[:8]
        return len(df[df['Event']=='OPEN']), sig
    except:
        return 0, "Error"

def get_metrics_from_report(run_dir):
    json_path = os.path.join(run_dir, "summary.json")
    if os.path.exists(json_path):
        import json
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            return {
                "net_pnl": float(data.get("net_pnl", 0.0)),
                "return_pct": float(data.get("return_pct", 0.0)),
                "wr_pct": float(data.get("win_rate_pct", 0.0)),
                "avg_hold": float(data.get("avg_hold_minutes", 0.0))
            }
        except: pass
    
    # Fallback/Old method
    return {"net_pnl": 0.0, "return_pct": 0.0, "wr_pct": 0.0, "avg_hold": 0.0}

def run_grid(args):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    grid_root = f"runs/grid_{ts}"
    os.makedirs(grid_root, exist_ok=True)
    
    print(f"Starting Phase 16 Grid: {grid_root}")
    if args.dry_run: print("[DRY RUN MODE]")
    
    summary = []
    points_run = 0
    
    for adx in GRID_ADX:
        for exp in GRID_EXP:
            if args.max_points and points_run >= args.max_points: break
            
            combo_name = f"Adx{int(adx)}_Exp{int(exp)}"
            points_run += 1
            
            print(f">> Running {combo_name} ...")
            
            cmd = BASE_CMD + [
                "--symbol", args.symbol,
                "--start_date", args.start,
                "--end_date", args.end,
                "--data_dir", DATA_DIR,
                "--min_adx", str(adx),
                "--max_exp_move_bps", str(exp),
                "--quiet",
                "--report"
            ]
            
            if args.dry_run:
                print(f"   Cmd: {' '.join(cmd)}")
                summary.append({"Combo": combo_name, "Trades": 0})
                continue
            
            # Run and Capture Output
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                output = result.stdout
            except subprocess.CalledProcessError as e:
                print(f"   FAIL: Run failed with exit code {e.returncode}")
                # print(e.output)
                continue
            
            # Extract Run Directory safely from stdout
            # Look for line: "Logging run to: runs/..."
            run_dir = None
            for line in output.splitlines():
                if "Logging run to:" in line:
                    parts = line.split("Logging run to:")
                    if len(parts) > 1:
                        potential_dir = parts[1].strip()
                        if os.path.isdir(potential_dir):
                            run_dir = potential_dir
                            break
                            
            if not run_dir:
                print("   WARNING: Could not identify run directory from stdout. Skipping metrics.")
                continue

            count, sig = get_fingerprint(run_dir)
            metrics = get_metrics_from_report(run_dir)
            
            row = {
                "min_adx": adx,
                "max_exp_move_bps": exp,
                "trades": count,
                "net_pnl": metrics['net_pnl'],
                "return_pct": metrics['return_pct'],
                "wr_pct": metrics['wr_pct'],
                "avg_hold": metrics['avg_hold'],
                "scenario_fingerprint": sig,
                "run_dir": run_dir
            }
            summary.append(row)
            print(f"   Result: Trades={count}, Hash={sig}")

        if args.max_points and points_run >= args.max_points: break

    # Write Summary
    sum_path = os.path.join(grid_root, "grid_summary.csv")
    pd.DataFrame(summary).to_csv(sum_path, index=False)
    print(f"\nGrid Complete. Summary saved to {sum_path}")
    
    # Check Diversity
    if not args.dry_run:
        hashes = set(s['scenario_fingerprint'] for s in summary)
        print(f"Unique Fingerprints: {len(hashes)} / {len(summary)}")
        if len(hashes) >= 2:
            print("SUCCESS: Sensitivity Confirmed.")
            return 0
        else:
            print("FAILURE: Low Sensitivity (Identical Results).")
            return 1
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", default="2024-02-01")
    parser.add_argument("--end", default="2024-02-14")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--points", dest="max_points", type=int, help="Max grid points to run")
    args = parser.parse_args()
    
    sys.exit(run_grid(args))
