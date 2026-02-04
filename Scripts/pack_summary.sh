#!/bin/bash
# Safe pack summary printer (No Heredocs)
# Extraction logic uses awk to find headers and print associated tables.

PACK_DIR="$1"

# Auto-detect latest if not provided
if [ -z "$PACK_DIR" ]; then
    PACK_DIR=$(ls -dt runs/pack_* 2>/dev/null | head -n 1)
fi

if [ -z "$PACK_DIR" ]; then
    echo "Error: No pack found."
    exit 1
fi

DIAG_FILE="$PACK_DIR/diagnostics.md"

if [ ! -f "$DIAG_FILE" ]; then
    echo "Error: $DIAG_FILE not found."
    exit 1
fi

echo "Summary for: $PACK_DIR"
echo "========================================"

echo ""
echo "--- Scenario Summary ---"
# Extract the first Scenario table
awk '/^\| Scenario \| Net/ {flag=1} flag && /^\|/ {print} flag && !/^\|/ {flag=0} ' "$DIAG_FILE" | head -n 20

echo ""
echo "--- ExpMove Calibration ---"
# Match "ExpMove Calibration" header and print the following table (Metric/Pearson)
awk '/ExpMove Calibration/ {flag=1; print "Found Header: " $0; next} flag && /^\|/ {print} flag && !/^\|/ && !/^[[:space:]]*$/ {flag=0}' "$DIAG_FILE"

echo ""
echo "--- Gate Breakdown ---"
# Python script to parse decision logs and print table
python3 -c '
import sys, os, csv
from collections import defaultdict

pack_dir = sys.argv[1]
if not os.path.exists(pack_dir): sys.exit(0)

# Find scenarios (directories inside pack)
scenarios = [d for d in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, d))]
results = []

for sc in sorted(scenarios):
    log = os.path.join(pack_dir, sc, "decision_log.csv")
    if not os.path.exists(log): continue
    
    go_count = 0
    final_trade_count = 0
    blocked_counts = defaultdict(int)
    
    try:
        with open(log, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check for GO signals (Proposed)
                # Decision column is now FINAL outcome. 
                # We need to reconstruct "Proposed GO"? 
                # No, if "BlockedReason" is present, it WAS a proposed GO diff blocked.
                # If Decision=GO, it was a GO.
                
                decision = row.get("Decision", "")
                reason = row.get("BlockedReason", "N/A")
                
                is_trade = (decision == "GO")
                is_blocked = (reason != "N/A" and reason != "")
                
                # Logic: Proposed GO = Trade OR Blocked
                if is_trade:
                    go_count += 1
                    final_trade_count += 1
                elif is_blocked:
                    go_count += 1
                    blocked_counts[reason] += 1
                    
        # Format counts
        block_str = " ".join([f"{k}:{v}" for k,v in blocked_counts.items()])
        results.append((sc, go_count, final_trade_count, block_str))
        
    except Exception: pass

print(f"| Scenario | GO (Total) | Final Trades | Blocked Breakdown |")
print(f"|---|---|---|---|")
for r in results:
    print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
' "$PACK_DIR"
