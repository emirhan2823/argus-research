#!/usr/bin/env python3
import os
import sys
import argparse
import datetime
import re

def parse_date(d_str):
    return datetime.datetime.strptime(d_str, "%Y-%m-%d").date()

def verify_coverage(symbol, start, end, data_dir):
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    
    # Pattern: SYMBOL_1m_START_END.csv
    # e.g. BTCUSDT_1m_2024-01-01_2024-02-01.csv
    pattern = re.compile(rf"{symbol}_1m_(\d{{4}}-\d{{2}}-\d{{2}})_(\d{{4}}-\d{{2}}-\d{{2}})\.csv")
    
    if not os.path.exists(data_dir):
        print(f"Error: Data directory not found: {data_dir}")
        return 2

    files = os.listdir(data_dir)
    covered = False
    found_ranges = []

    for f in files:
        match = pattern.match(f)
        if match:
            f_start = parse_date(match.group(1))
            f_end = parse_date(match.group(2))
            found_ranges.append((f_start, f_end))
            
    # Sort by start date
    found_ranges.sort()
    
    # Merge overlapping intervals
    merged = []
    if found_ranges:
        curr_start, curr_end = found_ranges[0]
        for next_start, next_end in found_ranges[1:]:
            if next_start <= curr_end: # Overlap or contiguous
                curr_end = max(curr_end, next_end)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged.append((curr_start, curr_end))
    
    # Check coverage
    covered = False
    for m_start, m_end in merged:
        if m_start <= start_dt and m_end >= end_dt:
            covered = True
            break
            
    if covered:
        print(f"PASS: Range {start} -> {end} covered by cache union.")
        return 0
    
    print(f"Missing coverage: {start} -> {end}")
    print("Available coverage (merged):")
    if not merged:
        print("  (No cache files found for this symbol)")
    else:
        for s, e in merged:
            print(f"  {s} -> {e}")

    print(f"\nExpected coverage: {symbol}_1m_{start}_{end} (or union of files)")
    
    # Check for downloader
    print("\nSuggested Action:")
    try:
        # Ensure we can import from root
        root_dir = os.getcwd()
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        import importlib.util
        if importlib.util.find_spec("argus_py.data.binance_downloader"):
             print(f"  python3 -m argus_py.data.binance_downloader --symbol {symbol} --start_date {start} --end_date {end} --output_dir {data_dir}")
        else:
             print("  (Downloader module not found. Search for ingestion scripts: rg -n 'downloader|ingest|cache' .)")
    except Exception as e:
         print(f"  (Downloader check failed: {e}. Search manually: rg -n 'downloader|ingest|cache' .)")
    
    return 2

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start_date", required=True)
    parser.add_argument("--end_date", required=True)
    parser.add_argument("--data_dir", default="argus_py/data/cache")
    args = parser.parse_args()
    
    sys.exit(verify_coverage(args.symbol, args.start_date, args.end_date, args.data_dir))
