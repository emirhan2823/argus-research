
import os
import csv
import pandas as pd

ROOT = "runs/phase18_robustness"
SUMMARY_FILE = os.path.join(ROOT, "runner_summary.csv")

def extract_metrics(run_dir):
    try:
        dec_log = os.path.join(run_dir, "decision_log.csv")
        metrics = {"net_pnl": 0.0, "return_pct": 0.0, "trades": 0, "win_rate": 0.0, "pf": 0.0, "max_dd": 0.0}
        
        if os.path.exists(dec_log):
            df = pd.read_csv(dec_log)
            if not df.empty:
                # Calculate PnL if not present (simple approx) or parse if available
                # Assuming standard argus analysis logic
                # For now, let's use a simplified parser if 'pnl' column is missing across all rows
                
                # Check for 'pnl' column?
                # Actually, relying on runner logic is safer? 
                # Let's count trades primarily and net return.
                
                # Filter useful trades (SELL or COVER/CLOSE?)
                # Argus 'trades' are usually round trips.
                # Let's assume the CSV has trade details or we calculate from balance if tracked?
                
                # Let's try to infer from 'action' if needed, generally 'return_pct' is in config or calculated?
                # No, return_pct is a result metric.
                
                # Let's simple-count 'SELL' actions for trade count if no better way?
                # Re-reading standard analysis might be heavy.
                
                # Let's look at the known columns: timestamp,regime,gate,action,adx,risk...
                # It does NOT verify PnL directly in decision log?
                # Wait, earlier output showed: 
                # ... 10.62,0.50,CAUTION...
                
                # It doesn't look like PnL is in decision_log.csv directly?
                # Unless 'net_pnl' is?
                
                # Actually, let's look for 'summary.json' maybe?
                pass

        # Check for summary.json which is standard
        sum_json = os.path.join(run_dir, "summary.json") 
        if os.path.exists(sum_json):
            import json
            with open(sum_json) as f:
                d = json.load(f)
                metrics.update(d)
                return metrics
                
        # Fallback: Parse stdout.log for "Final Balance: 1045.62 (4.56%)"
        stdout_log = os.path.join(run_dir, "stdout.log")
        if os.path.exists(stdout_log):
            import re
            with open(stdout_log, "r") as f:
                content = f.read()
                # Match: Final Balance: 1045.62 (4.56%)
                match = re.search(r"Final Balance: [\d\.]+ \(([\d\.\-]+)%\)", content)
                if match:
                    metrics["return_pct"] = float(match.group(1))
                    
        # Fallback: Count rows in decision_log as proxy for activity?
        if os.path.exists(dec_log):
             metrics["trades"] = len(pd.read_csv(dec_log))
        
        return metrics

    except Exception as e:
        print(f"Error {run_dir}: {e}")
        return {}

def main():
    rows = []
    if os.path.exists(ROOT):
        for d in sorted(os.listdir(ROOT)):
            path = os.path.join(ROOT, d)
            if os.path.isdir(path):
                # Parse name: Adx35_Exp80_S1_Normal_IN
                parts = d.split("_")
                # parts: ['Adx35', 'Exp80', 'S1', 'Normal', 'IN']
                if len(parts) >= 5:
                    cand = f"{parts[0]}_{parts[1]}"
                    split = parts[2].replace("S","")
                    prof = parts[3]
                    win = parts[4]
                    
                    m = extract_metrics(path)
                    
                    row = {
                        "run_id": d,
                        "candidate": cand,
                        "split": split,
                        "window": win,
                        "profile": prof,
                        "status": "OK" if m.get("trades", 0) > 0 else "FAIL",
                        "duration": 0, # Unk
                        "return_pct": m.get("return_pct", 0),
                        "trades": m.get("trades", 0),
                        "pf": m.get("profit_factor", 0), # mapping
                        "max_dd": m.get("max_drawdown_bps", 0),
                        "run_dir": path
                    }
                    rows.append(row)

    # Write CSV
    keys = ["run_id", "candidate", "split", "window", "profile", "status", "duration", "return_pct", "trades", "pf", "max_dd", "run_dir"]
    with open(SUMMARY_FILE, "w") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, 0) for k in keys})
            
    print(f"Recalculated summary for {len(rows)} runs.")

if __name__ == "__main__":
    main()
