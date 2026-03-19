
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from Scripts.phase19_readers import Phase19Readers

def test():
    r = Phase19Readers(REPO_ROOT / "runs/phase19_paper/live_test")
    hb = r.get_heartbeat()
    print(f"Heartbeat Health: {hb['health'] if hb else 'None'}")
    
    dec = r.get_csv_tail('decisions.csv')
    print(f"Decisions Columns: {list(dec.columns)}")

if __name__ == "__main__":
    test()
