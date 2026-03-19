
import subprocess
import os
import json
import csv
import time
import shutil
from multiprocessing import Pool

# Config
CANDIDATES = [
    {"name": "Adx35_Exp80", "args": ["--min_adx", "35", "--max_exp_move_bps", "80"]},
    {"name": "Adx45_Exp40", "args": ["--min_adx", "45", "--max_exp_move_bps", "40"]}
]

SPLITS = [
    {"id": 1, "in": ("2024-01-01", "2024-02-01"), "out": ("2024-02-01", "2024-03-01")},
    {"id": 2, "in": ("2024-03-01", "2024-04-01"), "out": ("2024-04-01", "2024-05-01")},
    {"id": 3, "in": ("2024-05-01", "2024-06-01"), "out": ("2024-06-01", "2024-07-01")}
]

PROFILES = {
    "Normal": {"fee": 4.0, "slip": 2.0, "spread": 1.0},
    "Stress": {"fee": 8.0, "slip": 4.0, "spread": 2.0}
}

OUT_ROOT = "runs/phase18_robustness"

def run_backtest(task):
    cand, split, prof_name, win_type = task
    prof = PROFILES[prof_name]
    start_dt, end_dt = split[win_type]
    
    run_id = f"{cand['name']}_S{split['id']}_{prof_name}_{win_type.upper()}"
    run_dir = os.path.join(OUT_ROOT, run_id)
    
    cmd = [
        "python3", "-u", "-m", "argus_py.runner.cli",
        "--mode", "backtest",
        "--symbol", "BTCUSDT",
        "--data_dir", "argus_py/data/cache",
        "--start_date", start_dt,
        "--end_date", end_dt,
        # "--output_dir", run_dir, # NOT SUPPORTED
        "--fee_bps", str(prof["fee"]),
        "--slippage_bps", str(prof["slip"]),
        "--spread_bps", str(prof["spread"]),
        "--quiet"
    ] + cand["args"]
    
    result = {
        "run_id": run_id,
        "candidate": cand["name"],
        "split": split["id"],
        "window": win_type,
        "profile": prof_name,
        "run_dir": run_dir,
        "status": "Running",
        "duration": 0
    }
    
    t0 = time.time()
    temp_log = f"{run_id}.log"
    
    try:
        # Run and stream output to file (avoid buffer issues)
        with open(temp_log, "w") as f:
            subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)
        
        # Read log to find dir
        with open(temp_log, "r") as f:
            output = f.read()
        
        # Parse generated directory
        gen_dir = None
        for line in output.splitlines():
            if "Logging run to:" in line:
                parts = line.split("Logging run to:")
                if len(parts) > 1:
                    d = parts[1].strip()
                    if os.path.isdir(d):
                        gen_dir = d
                        break
        
        if gen_dir:
            # Move to target run_dir
            if os.path.exists(run_dir): shutil.rmtree(run_dir)
            shutil.move(gen_dir, run_dir)
            
            # Move log
            shutil.move(temp_log, os.path.join(run_dir, "stdout.log"))
            
            result["status"] = "OK"
        else:
            result["status"] = "FAIL (No Dir)"
            print(f"FAIL {run_id}: No output directory found.")
            # Keep temp log for debug
            shutil.move(temp_log, f"runs/phase18_robustness/{run_id}_FAIL.log")

    except subprocess.CalledProcessError as e:
        result["status"] = "FAIL"
        print(f"FAIL {run_id}: Exit Code {e.returncode}")
        if os.path.exists(temp_log):
             shutil.move(temp_log, f"runs/phase18_robustness/{run_id}_ERR.log")
    except Exception as e:
        result["status"] = f"ERR: {e}"
        print(f"ERR {run_id}: {e}")
        if os.path.exists(temp_log):
             os.remove(temp_log)
        
    result["duration"] = round(time.time() - t0, 1)
    
    # Extract Metrics from decision_log.csv if OK
    metrics = extract_metrics(run_dir)
    result.update(metrics)
    
    pnl = result.get('return_pct', 'N/A')
    print(f"[{result['status']}] {run_id} ({result['duration']}s) -> Return: {pnl}%")
    return result

def extract_metrics(run_dir):
    # Parse decision_log to get Trades, PnL
    # Or just return empty and let Report script handle it
    # Better to have basic stats here for CSV summary
    m = {"trades": 0, "net_pnl_bps": 0.0, "return_pct": 0.0}
    
    try:
        log_path = os.path.join(run_dir, "decision_log.csv")
        if not os.path.exists(log_path): return m
        
        # Simple extraction via csv
        rows = []
        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        trades = [r for r in rows if r.get("Action") in ("BUY", "SELL", "CLOSE")]
        # Count unique PositionIDs? No, trade entries.
        # Just use simple count for now or better yet, read summary JSON if available?
        # Runner doesn't produce JSON summary? It prints it.
        # Let's compute manually from rows if needed, or just let Report script do heavier lifting.
        # Run Report script assumes `decision_log` exists.
        
        # Quick Calc
        total_pnl = sum(float(r.get("RealizedPnL", 0)) for r in rows if r.get("RealizedPnL"))
        m["net_pnl_bps"] = total_pnl # Wait, RealizedPnL unit? Usually BPS in Argus.
        
        # Argus logs RealizedPnL in Basis Points? Check.
        # Yes, usually.
        # Return PCT? approximate from BPS / 100
        m["return_pct"] = round(total_pnl / 100.0, 3)
        m["trades"] = len([r for r in rows if r.get("Action") == "CLOSE"]) # Close events count as completed trades?
        
    except:
        pass
    return m

def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    
    # REDUCED SCOPE: Split 1 Only, Candidate 1 Only (Time Constraint)
    target_tasks = []
    
    # Priority: Adx35_Exp80, Split 1 (Jan/Feb)
    cand = CANDIDATES[0] # Adx35
    split = SPLITS[0]    # Jan-Feb
    
    for prof in PROFILES:
        for w in ["in", "out"]:
            target_tasks.append((cand, split, prof, w))
            
    all_tasks = target_tasks
                    
    print(f"Starting {len(all_tasks)} tasks in PARALLEL (Pool=4)...")
    
    with Pool(processes=4) as p:
        results = p.map(run_backtest, all_tasks)
        
    # Save Summary
    keys = ["run_id", "candidate", "split", "window", "profile", "status", "duration", "return_pct", "trades", "run_dir"]
    sum_path = os.path.join(OUT_ROOT, "runner_summary.csv")
    
    with open(sum_path, "w") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k) for k in keys})
            
    print(f"All done. Summary saved to {sum_path}")

if __name__ == "__main__":
    main()
