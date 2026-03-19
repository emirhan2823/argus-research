import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Setup
REPO_ROOT = Path(__file__).resolve().parent.parent
TWIN_ROOT = REPO_ROOT / "runs/phase19_twin"

def analyze_daemon(did):
    print(f"\n--- ANALYZING DAEMON: {did} ---")
    
    # Paths
    d_dir = TWIN_ROOT / did
    f_dec = d_dir / "decisions.jsonl"
    f_rej = d_dir / "rejects.csv"
    
    if not f_dec.exists():
        print("No decisions.jsonl found.")
        return
        
    # 1. Load Last N Decisions
    data = []
    with open(f_dec, "r") as f:
        # crude tail
        lines = f.readlines()[-2000:]
        for line in lines:
            try:
                data.append(json.loads(line))
            except: pass
            
    if not data:
        print("Decisions file empty.")
        return
        
    df = pd.DataFrame(data)
    print(f"Loaded {len(df)} decision records.")
    
    # 2. Decision Counts
    if "verdict" in df.columns:
        # verdict is a dict in jsonl usually, check structure
        # In paper_daemon.py: event = ... verdict=verdict (object)
        # But we write it as dict in json dump.
        # Let's see how it's serialized.
        # It seems `verdict` field in json is the Verdict object dict.
        # Extract decision from it.
        try:
             df["decision_val"] = df["verdict"].apply(lambda x: x.get("decision", "UNKNOWN"))
             print("\nDECISION BREAKDOWN:")
             print(df["decision_val"].value_counts())
        except Exception as e:
            print(f"Error parsing verdict: {e}")
            
    # 3. Metrics
    print("\nMETRICS (Last 500):")
    cols = ["scores.adx", "scores.expected_move_bps"]
    # Normalize nested
    if "scores" in df.columns:
        df["adx"] = df["scores"].apply(lambda x: x.get("adx", 0))
        df["exp_move"] = df["scores"].apply(lambda x: x.get("expected_move_bps", 0))
        
        print(df[["adx", "exp_move"]].describe().loc[["min", "50%", "max", "mean"]])
        
    # 4. Rejects Analysis
    if f_rej.exists():
        try:
            df_r = pd.read_csv(f_rej)
            if not df_r.empty:
                print(f"\nREJECTS (Total {len(df_r)}):")
                print(df_r["code"].value_counts())
                
                print("\nSAMPLE REJECTS:")
                print(df_r.tail(5)[["code", "detail"]].to_string(index=False))
            else:
                print("\nrejects.csv exists but is empty.")
        except:
             print("\nError reading rejects.csv")
    else:
        print("\nNo rejects.csv found.")

    # 5. Check for "Lost" Blocks
    # Where decision=BLOCK but no reject logged?
    # Or decision=NO_GO
    # In paper_daemon, NO_GO is usually from Council deliberation being weak.
    # BLOCK is from Router or Gates.
    if "decision_val" in df.columns:
        no_go = df[df["decision_val"] == "NO_GO"]
        print(f"\nNO_GO COUNT: {len(no_go)}")
        if not no_go.empty:
             # Check reasons
             # reasons is a list in jsonl
             df["reasons_str"] = df["reasons"].apply(lambda x: str(x) if x else "[]")
             print("NO_GO Reasons Breakdown:")
             print(df[df["decision_val"] == "NO_GO"]["reasons_str"].value_counts().head(5))

def run():
    analyze_daemon("STRICT")
    analyze_daemon("SOFT")

if __name__ == "__main__":
    run()
