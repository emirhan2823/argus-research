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
echo "--- Reliability Bins ---"
# Match "Reliability (Monotonicity Check)" and print following table
awk '/Reliability \(Monotonicity Check\)/ {flag=1; print "Found Header: " $0; next} flag && /^\|/ {print} flag && !/^\|/ && !/^[[:space:]]*$/ {flag=0}' "$DIAG_FILE"
