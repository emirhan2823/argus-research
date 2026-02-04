#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
import pandas as pd
import hashlib
import argparse
import json
import time

# Configuration
DATA_DIR = "argus_py/data/cache"
# Patch 1: Explicitly force mode=backtest
BASE_CMD = [sys.executable, "-m", "argus_py.runner.cli", "--mode", "backtest"]

# Phase 17 Target Grid
# min_adx: [0, 15, 25, 35, 45, 55, 65]
# max_exp_move_bps: [20, 40, 60, 80, 120, 160]
GRID_ADX = [0.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0]
GRID_EXP = [20.0, 40.0, 60.0, 80.0, 120.0, 160.0]

WINDOWS = {
    "INSAMPLE": {"start": "2024-02-01", "end": "2024-03-15"},
    "OUTSAMPLE": {"start": "2024-03-15", "end": "2024-04-15"}
}

def get_fingerprint(run_dir):
    dump = os.path.join(run_dir, "trades.csv")
    if not os.path.exists(dump): return 0, "N/A"
    try:
        df = pd.read_csv(dump)
        if df.empty: return 0, "Empty"
        
        # Patch 3: Fingerprint Consistency (Trades count & Hash from SAME event set)
        df = df.sort_values(by=["Timestamp", "PositionId", "Event"], kind="mergesort")
        
        if 'Event' in df.columns:
            open_df = df[df['Event'] == 'OPEN']
        else:
            # Fallback if no Event col, though Argus usually has it
            open_df = df
            
        # Hash raw string: Timestamp|Side|FillPrice;
        raw = ""
        for _, row in open_df.iterrows():
            raw += f"{row['Timestamp']}|{row['Side']}|{row['FillPrice']};"
            
        sig = hashlib.sha1(raw.encode()).hexdigest()[:8]
        return len(open_df), sig
    except Exception as e:
        print(f"Fingerprint Error: {e}")
        return 0, "Error"

def get_metrics_from_report(run_dir):
    json_path = os.path.join(run_dir, "summary.json")
    metrics = {"net_pnl": None, "return_pct": None, "wr_pct": None, "avg_hold": None}
    
    # 1. Try Loading JSON
    if os.path.exists(json_path):
        import json
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            # Map known keys. Only set if present and not None.
            val = data.get("total_pnl", data.get("net_pnl"))
            if val is not None: metrics["net_pnl"] = float(val)

            val = data.get("total_return_pct", data.get("return_pct"))
            if val is not None: metrics["return_pct"] = float(val)

            # Win Rate
            val = data.get("win_rate", data.get("win_rate_pct"))
            if val is not None:
                wr = float(val)
                if wr <= 1.0 and wr > 0.0: wr *= 100.0
                metrics["wr_pct"] = wr
            
            # Avg Hold
            val = data.get("avg_hold_minutes")
            if val is not None: metrics["avg_hold"] = float(val)
        except: pass
        
    # 2. Fallback via trades.csv (Optional, skip for now to avoid complexity/fake data)
    return metrics

def run_grid_phase17(args):
    # Always define ts first
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Setup Output Directory
    if args.outdir:
        grid_root = args.outdir
    else:
        grid_root = f"runs/phase17_grid_{ts}"
    
    os.makedirs(grid_root, exist_ok=True)
    
    # Patch 4: Configurable Symbol usage
    print(f"Starting Phase 17 Grid: {grid_root}")
    print(f"Target: {args.symbol}")
    if args.dry_run: print("[DRY RUN MODE]")
    if args.resume: print("[RESUME MODE]")
    
    summary = []
    
    # Select Window
    if args.window not in WINDOWS:
        print(f"Error: Window {args.window} unknown. Options: {list(WINDOWS.keys())}")
        return 1
        
    w_cfg = WINDOWS[args.window]
    start_dt = w_cfg["start"]
    end_dt = w_cfg["end"]
    sum_path = os.path.join(grid_root, f"grid_summary_{args.window}.csv")
    
    # Resume Logic
    completed_combos = set()
    if args.resume and os.path.exists(sum_path):
        try:
            existing_df = pd.read_csv(sum_path)
            # Load existing rows into summary
            summary = existing_df.to_dict('records')
            for row in summary:
                c_name = row.get('combo')
                # PATCH: Only mark as completed if status is OK (case-insensitive)
                status = str(row.get('status', '')).upper()
                if c_name and status == "OK":
                    completed_combos.add(c_name)
            print(f"Resuming: Found {len(completed_combos)} OK points (will re-run FAIL points).")
        except Exception as e:
            print(f"Warning: Could not load resume file {sum_path}: {e}")

    print(f"Window: {args.window} ({start_dt} -> {end_dt})")
    
    points_run = 0
    total_points = len(GRID_ADX) * len(GRID_EXP)
    
    for adx in GRID_ADX:
        for exp in GRID_EXP:
            if args.max_points and points_run >= args.max_points: break
            
            combo_name = f"Adx{int(adx)}_Exp{int(exp)}"
            
            if combo_name in completed_combos:
                print(f">> Skipping {combo_name} (Already Done)")
                continue

            print(f">> [{points_run+1}/{total_points}] Running {combo_name} ...")
            
            cmd = BASE_CMD + [
                "--symbol", args.symbol,
                "--start_date", start_dt,
                "--end_date", end_dt,
                "--data_dir", DATA_DIR,
                "--min_adx", str(adx),
                "--max_exp_move_bps", str(exp),
                "--quiet",
                "--report"
            ]
            
            if args.dry_run:
                summary.append({"Combo": combo_name, "Adx": adx, "Exp": exp})
                points_run += 1
                continue
                
            # Status Tracking
            run_status = "OK"
            error_reason = None
            error_hint = None
            
            # Run and Capture
            start_time = time.time()
            try:
                # Patch 2: Capture stdout + stderr (combined processing)
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                duration = time.time() - start_time
                output = (result.stdout or "") + "\n" + (result.stderr or "")
            except subprocess.CalledProcessError as e:
                run_status = "FAIL"
                duration = time.time() - start_time # Record real duration even on fail
                output = (e.stdout or "") + "\n" + (e.stderr or "")
                
                # Analyze Error
                if "Dataset Range Mismatch" in output:
                    error_reason = "Cache Miss"
                    error_hint = "Run scripts/verify_dataset_coverage.py to fix."
                    
                    # Regex Parse Mismatch Summary
                    # Example: "Requested: 2024-03-15 -> 2024-04-15 ... Dataset: 2024-01-01 -> 2024-03-15"
                    import re
                    req_match = re.search(r"Requested:\s*([\d-]+(?:\s*[\d:]+)?)\s*->\s*([\d-]+(?:\s*[\d:]+)?)", output)
                    ds_match = re.search(r"Dataset:\s*([\d-]+(?:\s*[\d:]+)?)\s*->\s*([\d-]+(?:\s*[\d:]+)?)", output)
                    
                    details = []
                    if req_match: details.append(f"Req[{req_match.group(1)}..{req_match.group(2)}]")
                    if ds_match: details.append(f"Has[{ds_match.group(1)}..{ds_match.group(2)}]")
                    
                    if details:
                         print(f"   [MISMATCH]: {' vs '.join(details)}")

                else:
                    error_reason = f"Exit Code {e.returncode}"
                    error_hint = "Check logs."
                
                print(f"   FAIL: {error_reason}")
                
                # Log Head/Tail for debugging
                out_len = len(output)
                if out_len > 2400:
                    head = output[:1200]
                    tail = output[-1200:]
                    print(f"   --- LOG HEAD ---\n{head}\n   ...\n   --- LOG TAIL ---\n{tail}\n   ----------------")
                else:
                    print(f"   --- LOG ---\n{output}\n   -----------")

            # Extract Run Directory safely
                
            # Extract Run Directory safely
            run_dir = None
            if run_status == "OK":
                for line in output.splitlines():
                    if "Logging run to:" in line:
                        parts = line.split("Logging run to:")
                        if len(parts) > 1:
                            potential_dir = parts[1].strip()
                            if os.path.isdir(potential_dir):
                                run_dir = potential_dir
                                break
            
            if run_status == "OK" and not run_dir:
                run_status = "FAIL"
                error_reason = "Run Dir Not Found"
                print("   WARNING: Could not identify run directory from output.")
                
            count = 0
            sig = "N/A"
            metrics = {"net_pnl": None, "return_pct": None, "wr_pct": None, "avg_hold": None}

            if run_status == "OK" and run_dir:
                count, sig = get_fingerprint(run_dir)
                metrics = get_metrics_from_report(run_dir)
            
            row = {
                "window": args.window,
                "combo": combo_name,
                "min_adx": adx,
                "max_exp_move_bps": exp,
                "trades": count,
                "net_pnl": metrics['net_pnl'],
                "return_pct": metrics['return_pct'],
                "wr_pct": metrics['wr_pct'],
                "avg_hold": metrics['avg_hold'],
                "scenario_fingerprint": sig,
                "duration_sec": round(duration, 1),
                "run_dir": run_dir,
                "status": run_status,
                "error_reason": error_reason,
                "error_hint": error_hint
            }
            summary.append(row)
            
            # Print result
            if run_status == "OK":
                pnl_str = f"{metrics['return_pct']}%" if metrics['return_pct'] is not None else "N/A"
                print(f"   Result: Trades={count}, PnL={pnl_str}, Hash={sig}")
            
            points_run += 1

            # Incremental Save (Robustness)
            pd.DataFrame(summary).to_csv(sum_path, index=False)

    # Final Save
    pd.DataFrame(summary).to_csv(sum_path, index=False)
    print(f"\nGrid Complete. Summary saved to {sum_path}")
    
    # Generate Metadata (Corrected)
    meta = {
        "timestamp": ts,
        "window": args.window,
        "start_date": start_dt,
        "end_date": end_dt,
        "points_completed_total": len(summary),
        "success_count": len([r for r in summary if r.get('status') == 'OK']),
        "fail_count": len([r for r in summary if r.get('status') == 'FAIL']),
        "symbol": args.symbol,
        "grid_adx": GRID_ADX,
        "grid_exp": GRID_EXP
    }
    with open(os.path.join(grid_root, f"metadata_{args.window}.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Patch 4: Configurable Symbol
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol to backtest")
    parser.add_argument("--window", default="INSAMPLE", help="INSAMPLE or OUTSAMPLE")
    parser.add_argument("--outdir", default=None, help="Specific output directory (required for resume)")
    parser.add_argument("--resume", action="store_true", help="Resume from existing summary csv in outdir")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--points", dest="max_points", type=int, help="Max grid points to run")
    args = parser.parse_args()
    
    sys.exit(run_grid_phase17(args))