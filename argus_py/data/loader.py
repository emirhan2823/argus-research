import csv
import glob
import os
from datetime import datetime
from typing import List
from .market_state import Bar, MarketState

class DataLoader:
    @staticmethod
    def load_csv(filepath: str) -> List[Bar]:
        """
        Loads bars from a CSV file.
        Expected format: timestamp,open,high,low,close,volume
        """
        bars = []
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            # Check header
            header = next(reader, None)
            
            # Simple heuristic: if first col is not numeric, assume it's header.
            # But standard Binance format usually doesn't have header if raw,
            # or has specific headers. We'll assume NO header if first row parses,
            # OR standard header.
            # Safe bet: Try parsing header.
            
            # Rewind if it looked like data
            # Ideally we stick to strict contract.
            # Let's assume standard Argus/Binance format:
            # timestamp (ms), open, high, low, close, volume, ...
            
            if header and not header[0].replace('.','',1).isdigit():
                # It was a header
                pass
            else:
                 # It was data, reset
                f.seek(0)
                reader = csv.reader(f)

            for row in reader:
                if len(row) < 6: continue
                try:
                    ts = float(row[0])
                    # If ms timestamp, convert to seconds
                    if ts > 1000000000000:
                        ts /= 1000.0
                        
                    bars.append(Bar(
                        timestamp=ts,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5])
                    ))
                except ValueError:
                    continue
        
        # Sort by time
        bars.sort(key=lambda b: b.timestamp)
        return bars

    @staticmethod
    def load_from_dir(directory: str, pattern: str = "*.csv", max_bars: int = None, symbol: str = None, strict_symbol: bool = False) -> MarketState:
        """Loads all CSVs in directory, merges them, and returns MarketState"""
        # Prevent silent fallback to sample data for realistic backtests
        all_bars = []
        # Case-insensitive pattern match if possible, but pattern is usually *.csv
        files = glob.glob(os.path.join(directory, pattern))
        
        source_files = []
        symbol_resolved = None
        
        if symbol:
            filtered_files = []
            target_sym = symbol.upper()
            
            # 1. Exact Match / Stem Match (Priority 1)
            for f in files:
                basename = os.path.basename(f)
                file_stem = os.path.splitext(basename)[0].upper()
                
                if (file_stem == target_sym) or \
                   (file_stem.startswith(target_sym + "_")) or \
                   (target_sym in file_stem):
                    filtered_files.append(f)
            
            # 2. If filtered list empty, try glob wildcards relative to dir (Priority 2)
            if not filtered_files:
                 # Case-insensitive wildcard match
                 # e.g. *BTCUSDT*.csv
                 for f in files:
                     if target_sym in os.path.basename(f).upper():
                         filtered_files.append(f)

            # 3. STRICT Logic with Fallback
            if not filtered_files:
                # Check specific "BTCUSDT.csv"
                exact_path = os.path.join(directory, f"{target_sym}.csv")
                if os.path.exists(exact_path):
                     filtered_files = [exact_path]
                else:
                     if strict_symbol:
                         # STRICT MODE: No fallback allowed at all. Must find specific symbol files.
                         raise FileNotFoundError(f"Strict Load Error: No CSV for {symbol} found in {directory}. Expected *{target_sym}*.csv")

                     # Check if exactly one CSV exists in dir (Fallback)
                     all_csvs = [f for f in files if "SAMPLE" not in os.path.basename(f).upper()]
                     if len(all_csvs) == 1:
                         print(f"WARNING: Symbol {symbol} not found. Falling back to {os.path.basename(all_csvs[0])}")
                         filtered_files = [all_csvs[0]]
                     else:
                         raise FileNotFoundError(f"Load Error: No CSV for {symbol} and multiple/no candidates in {directory}.")
            
            # STRICT FILTERING: Remove "friends" if strict_symbol is True
            # User wants: "yalnızca tam eşleşen dosyayı yükle... friends merge etme"
            # If we found multiple files (e.g. BTCUSDT.csv and BTCUSDT_2024.csv), strict might usually imply EXACT match only.
            # But commonly strict means "Don't load ETH if I asked for BTC".
            # The prompt says: "yalnızca tam eşleşen dosyayı yükle: örn BTCUSDT.csv veya BTCUSDT_*.csv (ama “friends merge” yapma)"
            # Wait, "friends merge" usually referred to merging monthly files INTO the main one.
            # Actually, the logic above `filtered_files.append(f)` collects ALL matches.
            # If strict_symbol is True, we should probably ONLY look for EXACT match `BTCUSDT.csv` OR explicitly strict pattern?
            # Prompt: "Loader’ın extra dosyaları merge etmesini engelle (strict mode)"
            # "yalnızca tam eşleşen dosyayı yükle... örn BTCUSDT.csv veya BTCUSDT_*.csv"
            # Okay, so loading multiple splits (monthly files) IS allowed if they match the symbol.
            # What is disallowed is "friends"?
            # Ah, looking at previous logs: "Loaded ... from ... (and merged friends)."
            # This implies `all_bars.extend(new_bars)` is merging them.
            # If I have `BTCUSDT.csv` and `BTCUSDT_2024.csv`, they are both in `filtered_files`.
            # I think the requirement "Loader’ın extra dosyaları merge etmesini engelle" means:
            # IF `BTCUSDT.csv` exists, use ONLY that one. Don't merge others.
            # Let's implement this preference.
            
            if strict_symbol and filtered_files:
                 # Prefer exact match if available
                 exact_match = next((f for f in filtered_files if os.path.splitext(os.path.basename(f))[0].upper() == target_sym), None)
                 if exact_match:
                     filtered_files = [exact_match]
                 # Else, if request was BTCUSDT, but we only have BTCUSDT_*.csv, we keep them (probably monthly files).
                 # That seems consistent with "strict 'symbol file only'".
                 # BUT prompt says "yalnızca tam eşleşen dosyayı yükle".
                 # If I have 10 monthly files, and no single file, I should probably load them all?
                 # No, prompt says: "örn BTCUSDT.csv veya BTCUSDT_*.csv (ama “friends merge” yapma)"
                 # This phrasing is tricky. "Merge friends" sounds like "merging unrelated stuff".
                 # But in Argus context, it matches files starting with Symbol.
                 # Let's assume strict means: Just load `filtered_files` as strictly matched above. 
                 # AND if exact match exists, prioritize it and discard others to avoid duplicates if they overlap?
                 pass

            files = filtered_files
            
        source_files = files
        if files:
             # Basic resolved symbol from first file
             symbol_resolved = os.path.splitext(os.path.basename(files[0]))[0].upper()
             
             if "SAMPLE" in symbol_resolved:
                 print("WARNING: It looks like you are using SAMPLE data. Results may be fake.")

        for f in files:
            new_bars = DataLoader.load_csv(f)
            all_bars.extend(new_bars)
        
        # Dedup and Sort
        # Dedup by timestamp
        unique_bars = {b.timestamp: b for b in all_bars}
        sorted_bars = sorted(unique_bars.values(), key=lambda b: b.timestamp)
        
        # Sanity Checks
        DataLoader._validate_data(sorted_bars)
        
        if max_bars and len(sorted_bars) > max_bars:
            sorted_bars = sorted_bars[-max_bars:]
            
        merged_count = len(sorted_bars)
        if merged_count > 0:
             # Just use first source for log
             src = os.path.basename(source_files[0]) if source_files else "Unknown"
             count_msg = f"Loaded {merged_count} bars from {src}"
             if len(source_files) > 1:
                  count_msg += f" (and {len(source_files)-1} merged files)"
             print(count_msg)
             
        return MarketState(sorted_bars, source_files=source_files, symbol_requested=symbol, symbol_resolved=symbol_resolved)

    @staticmethod
    def _validate_data(bars: List[Bar]):
        if not bars: return
        
        # Check Monotonicity
        if len(bars) > 1:
            if bars[-1].timestamp < bars[0].timestamp:
                 print("WARNING: Data timestamps not monotonic!")
        
        # Check Prices
        errors = 0
        for b in bars:
            if b.close <= 0 or b.high < b.low:
                errors += 1
        
        if errors > 0:
             print(f"WARNING: Found {errors} bars with invalid prices (<=0 or H<L)")
