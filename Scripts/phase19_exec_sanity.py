import pandas as pd
import sys
from pathlib import Path
import json

# --- CONFIG ---
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

TWIN_ROOT = REPO_ROOT / "runs/phase19_twin"

def check_daemon(daemon_id):
    print(f"\nScanning {daemon_id}...")
    dec_path = TWIN_ROOT / daemon_id / "decisions.csv"
    trades_path = TWIN_ROOT / daemon_id / "trades.csv"
    rejects_path = TWIN_ROOT / daemon_id / "rejects.csv"
    
    if not dec_path.exists():
        print(f"FAIL: {dec_path} not found.")
        return False
        
    try:
        # Load last 200 decisions to be safe
        df = pd.read_csv(dec_path)
        if len(df) > 200:
            df = df.tail(200)
    except Exception as e:
        print(f"FAIL: Could not read decisions.csv: {e}")
        return False

    # Filter for GO
    gos = df[df["decision"] == "GO"]
    if gos.empty:
        print("INFO: No GO decisions in last 200 rows. Nothing to verify execution-wise.")
        return True
        
    print(f"Found {len(gos)} GO decisions in last 200 rows. Verifying execution traces...")
    
    # Load Trades and Rejects
    trades = pd.DataFrame()
    rejects = pd.DataFrame()
    
    if trades_path.exists():
        try:
            trades = pd.read_csv(trades_path)
            # Filter non-header? pandas handles header.
        except: pass
        
    if rejects_path.exists():
        try:
            rejects = pd.read_csv(rejects_path)
        except: pass
        
    # Check coverage
    # For every GO, we expect either a Trade (OPEN/REJECTED) or a Reject (EXEC_REJECT) 
    # matched by approximate timestamp?
    # Actually, simplistic check: Do we have ANY trades or execution rejects logged AFTER the first GO?
    
    if trades.empty and rejects.empty:
        print("FAIL: GO decisions exist but NO trades and NO rejects found!")
        return False
        
    # More specific check
    # Check for "REJECTED" event in trades
    rejected_trades = trades[trades["event"] == "REJECTED"] if "event" in trades.columns else pd.DataFrame()
    exec_rejects = rejects[rejects["code"] == "EXEC_REJECT"] if "code" in rejects.columns else pd.DataFrame()
    
    print(f"  Trades Total: {len(trades)}")
    print(f"  Rejected Trades (Audit): {len(rejected_trades)}")
    print(f"  Rejects Log (EXEC_REJECT): {len(exec_rejects)}")
    
    if len(trades) == 0 and len(rejects) == 0:
         print("FAIL: Still seeing zero execution artifacts despite GOs.")
         return False
         
    print("PASS: Execution artifacts detected.")
    return True

if __name__ == "__main__":
    print("=== Phase 19 Execution Sanity Check ===")
    r1 = check_daemon("STRICT")
    r2 = check_daemon("SOFT")
    
    if r1 and r2:
        print("\nOVERALL: PASS")
        sys.exit(0)
    else:
        print("\nOVERALL: FAIL")
        sys.exit(1)
