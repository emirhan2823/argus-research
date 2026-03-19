
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
            # Simple robust read
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

    def get_jsonl_tail(self, filename: str, n: int = 100):
        """Reads last n lines of a JSONL file."""
        fpath = self.run_dir / filename
        if not fpath.exists():
            return pd.DataFrame()
            
        records = []
        try:
            # For efficiency on huge logs, seek might be needed, but start simple
            with open(fpath, "r") as f:
                # Read all lines? Or deque?
                # Deque with maxlen is good for tail
                from collections import deque
                lines = deque(f, maxlen=n)
                
            for line in lines:
                try:
                    records.append(json.loads(line))
                except:
                    continue
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return pd.DataFrame()
            
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame(records)
        if "ts_iso" in df.columns:
             df = df.sort_values("ts_iso", ascending=False)
             
        return df

