
import json
import pandas as pd
import time
from pathlib import Path
from datetime import datetime

class Phase19Readers:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.heartbeat_file = run_dir / "heartbeat.json"
        
    def get_heartbeat(self):
        """Reads heartbeat.json safely."""
        if not self.heartbeat_file.exists():
            return None
            
        try:
            with open(self.heartbeat_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
        except Exception as e:
            print(f"Error reading heartbeat: {e}")
            return None

    def get_csv_tail(self, filename: str, n: int = 100):
        """Reads last n lines of a CSV safely."""
        fpath = self.run_dir / filename
        if not fpath.exists():
            return pd.DataFrame()
            
        try:
            # Read header
            with open(fpath, "r") as f:
                header_line = f.readline().strip()
                if not header_line:
                    return pd.DataFrame()
                columns = header_line.split(",")

            # Read tail efficiently? For 100 lines pandas is fine.
            # Avoid reading huge files if logs grow.
            # But normally pandas read_csv is mostly optimized.
            # To be safe against huge files:
            # mmap or seek? Let's just use pandas for simplicity -> robust against partial writes?
            # Actually, `pd.read_csv` might fail on malformed lines (interrupted write).
            # We use `on_bad_lines='skip'`.
            
            df = pd.read_csv(fpath, on_bad_lines='skip')
            
            # Sort / Tail
            if "ts_iso" in df.columns:
                df = df.sort_values("ts_iso", ascending=False)
            
            return df.head(n)
            
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return pd.DataFrame()

