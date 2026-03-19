
import sys
import os
import time
from pathlib import Path

# Adjust path to find scripts
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))
sys.path.append(str(REPO_ROOT))

# Mock Bar to avoid import issues if possible, but better import real
from argus_py.data.market_state import Bar
from paper_daemon import PaperDaemon, CONFIG

def test_regime_signatures():
    print("--- Test Regime Signature ---")
    
    # Override Run Dir
    cfg = CONFIG.copy()
    cfg["run_dir"] = str(REPO_ROOT / "runs/phase19_paper/sanity_test")
    cfg["lookback_init"] = 60 # Short warmup
    
    daemon = PaperDaemon(cfg)
    
    # Mock fetch_klines to return dummy bars
    def mock_fetch(limit=100):
        # Generate dummy bars
        bars = []
        now = time.time()
        base = 50000.0
        for i in range(limit):
            # Create some movement for ADX
            open_p = base + (i % 10) * 10
            close_p = open_p + 5
            high_p = close_p + 5
            low_p = open_p - 5
            
            b = Bar(
                timestamp=now - (limit-i)*60,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=100.0
            )
            bars.append(b)
        return bars
    
    daemon.fetch_klines = mock_fetch
    
    print("Warming up...")
    daemon.warmup()
    
    print("Processing bar...")
    bar = Bar(
        timestamp=time.time(),
        open=50100.0,
        high=50120.0,
        low=50090.0,
        close=50110.0,
        volume=150.0
    )
    
    try:
        daemon.process_bar(bar)
        print("PASS: process_bar executed without error.")
    except TypeError as e:
        print(f"FAIL: TypeError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: Other Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_regime_signatures()
