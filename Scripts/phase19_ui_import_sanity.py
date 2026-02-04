
import sys
import os
from pathlib import Path

# Fix Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

print(f"Repo Root: {REPO_ROOT}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not Set')}")

try:
    print("Attempting: from Scripts.phase19_readers import Phase19Readers")
    from Scripts.phase19_readers import Phase19Readers
    print(f"PASS: Imported readers from {Phase19Readers.__module__}")
    
    print("Attempting: import Scripts.phase19_dashboard")
    import Scripts.phase19_dashboard
    print(f"PASS: Imported dashboard module.")
    
except ImportError as e:
    print(f"FAIL: ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL: Other Error: {e}")
    sys.exit(1)
    
sys.exit(0)
