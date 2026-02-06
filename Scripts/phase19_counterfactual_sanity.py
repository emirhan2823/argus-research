import pandas as pd
import numpy as np
import sys
import shutil
from pathlib import Path

# Setup Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from Scripts.phase19_counterfactual import evaluate

def run_sanity():
    print("--- RUNNING SANITY CHECK ---")
    
    # Mock Data
    dates = pd.date_range(start="2025-01-01 00:00", periods=5, freq="1min")
    
    # 1. STRICT with garbage/None reasons
    strict_records = []
    reasons = ["MIN_ADX", None, np.nan, 123, "ROUTER_DEFENSE"]
    
    for i in range(5):
        strict_records.append({
            "ts_iso": dates[i].isoformat(),
            "bar_ts_iso": dates[i].isoformat(),
            "symbol": "BTCUSDT",
            "decision": "BLOCK",
            "block_reason_primary": reasons[i],
            "ts_align": dates[i].timestamp()
        })
        
    df_strict = pd.DataFrame(strict_records) # No set_index yet
    
    # 2. SOFT with GO (to trigger divergence)
    soft_records = []
    for i in range(5):
        soft_records.append({
            "ts_iso": dates[i].isoformat(),
            "bar_ts_iso": dates[i].isoformat(),
            "symbol": "BTCUSDT",
            "decision": "GO",
            "direction": "LONG",
            "ts_align": dates[i].timestamp()
        })
        
    df_soft = pd.DataFrame(soft_records)
    
    # Mock Filesystem
    # We will hijack the load_decisions in phase19_counterfactual using monkeypatch 
    # OR better, since we can't easily monkeypatch imported module without reloading, 
    # we will write these to a temp dir and point REPO_ROOT/TWIN_ROOT to it? 
    # Easier: Just Monkeypatch the function in the instance or module space before calling evaluate.
    
    import Scripts.phase19_counterfactual as pc
    
    original_load = pc.load_decisions
    
    def mock_load(daemon_id, n=1000):
        if daemon_id == "STRICT":
            return df_strict.set_index("ts_align")
        else:
            return df_soft.set_index("ts_align")
            
    pc.load_decisions = mock_load
    
    # Also fetch_klines needs to return something valid or empty.
    # If fetch_klines returns empty, shadows won't populate but it shouldn't crash.
    # Let's mock it to return some prices.
    
    def mock_klines(symbol="BTCUSDT", interval="1m", limit=1500):
        df = pd.DataFrame({
            "open_time": [d.timestamp()*1000 for d in dates],
            "close": [50000.0 + i for i in range(5)]
        })
        df["ts"] = df["open_time"].apply(lambda x: int(x)/1000.0)
        return df.set_index("ts")
    
    pc.fetch_klines = mock_klines
    
    try:
        pc.evaluate()
        print("\nSANITY PASS: evaluate() completed without crash.")
    except Exception as e:
        print(f"\nSANITY FAIL: evaluate() crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Restore (optional if process dies anyway)
        pc.load_decisions = original_load

if __name__ == "__main__":
    run_sanity()
