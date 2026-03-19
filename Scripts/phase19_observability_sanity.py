
import json
import sys
import os
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = REPO_ROOT / "runs/phase19_paper/live_test"
HEARTBEAT_FILE = RUN_DIR / "heartbeat.json"
DECISIONS_CSV = RUN_DIR / "decisions.csv"

def test_heartbeat():
    print(f"Checking {HEARTBEAT_FILE}...")
    if not HEARTBEAT_FILE.exists():
        print("FAIL: Heartbeat file missing.")
        sys.exit(1)
        
    try:
        with open(HEARTBEAT_FILE) as f:
            hb = json.load(f)
            
        req_keys = ["ts_iso", "equity", "health", "counters"]
        for k in req_keys:
            if k not in hb:
                print(f"FAIL: Missing key '{k}' in heartbeat.")
                sys.exit(1)
                
        # Check staleness
        ts_str = hb["ts_iso"]
        hb_ts = datetime.fromisoformat(ts_str)
        delta = (datetime.now() - hb_ts).total_seconds()
        print(f"Heartbeat Age: {delta:.2f}s")
        if delta > 300:
             print("WARN: Heartbeat is quite old (>300s).")
        
        print(f"Health: {hb['health']}")
        print("PASS: Heartbeat Valid.")
        
    except Exception as e:
        print(f"FAIL: JSON Error: {e}")
        sys.exit(1)

def test_csv():
    print(f"Checking {DECISIONS_CSV}...")
    if DECISIONS_CSV.exists():
        with open(DECISIONS_CSV) as f:
            header = f.readline().strip()
            expected = "ts_iso,bar_ts_iso,symbol,regime,mode,decision,direction,score,exp_move,adx,reasons"
            if header != expected:
                print(f"FAIL: Header mismatch.\nFound: {header}\nWant:  {expected}")
                sys.exit(1)
        print("PASS: CSV Header Valid.")
    else:
        print("INFO: Decisions CSV not yet created (acceptable if no bars processed).")

if __name__ == "__main__":
    test_heartbeat()
    test_csv()
