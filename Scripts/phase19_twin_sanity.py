
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime

# Adjust Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from Scripts.paper_daemon import PaperDaemon, DEFAULT_CONFIG
from argus_py.data.market_state import Bar

def test_twin_sanity():
    print("Testing Twin Daemon Logic...")
    
    # 1. Setup Test Env
    test_dir = REPO_ROOT / "runs/phase19_twin/TEST_SANITY"
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    
    cfg = DEFAULT_CONFIG.copy()
    cfg["daemon_id"] = "TEST_SANITY"
    cfg["run_dir"] = test_dir
    cfg["min_adx"] = 30.0
    cfg["run_id"] = "sanity_run"
    
    try:
        d = PaperDaemon(cfg)
        
        # 2. Feed Dummy Bar
        b = Bar(
            timestamp=int(datetime.now().timestamp()),
            open=100, high=110, low=90, close=105, volume=1000
        )
        d.process_bar(b)
        
        # 3. Verify Logs
        if not (test_dir / "decisions.jsonl").exists():
            print("FAIL: decisions.jsonl not created.")
            sys.exit(1)
            
        with open(test_dir / "decisions.jsonl") as f:
            rec = json.loads(f.readline())
            if rec["daemon_id"] != "TEST_SANITY":
                print(f"FAIL: Wrong daemon_id: {rec['daemon_id']}")
                sys.exit(1)
                
        print(f"PASS: Twin Daemon Sanity ({test_dir})")
        
    except Exception as e:
        print(f"FAIL: Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_twin_sanity()
