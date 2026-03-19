
import sys
import os
from pathlib import Path

# Adjust path to find scripts
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

# Test direct module location
try:
    import Scripts.phase19_readers
    print("PASS: Scripts.phase19_readers found.")
except ImportError:
    print("FAIL: Scripts.phase19_readers not found in path.")
    sys.exit(1)

from Scripts.phase19_readers import Phase19Readers

def test_readers():
    print("Testing Readers...")
    r = Phase19Readers(REPO_ROOT / "runs/phase19_paper/live_test")
    hb = r.get_heartbeat()
    print(f"Heartbeat: {hb is not None}")
    
    dec = r.get_csv_tail("decisions.csv")
    print(f"Decisions columns: {list(dec.columns)}")
    print("PASS: Readers functional.")

if __name__ == "__main__":
    test_readers()
