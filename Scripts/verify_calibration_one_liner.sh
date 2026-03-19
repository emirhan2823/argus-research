#!/bin/bash
# Safe Verification Script (No Heredocs)
# Usage: ./scripts/verify_calibration_one_liner.sh [pack_path]

PACK_DIR="$1"

# Auto-detect latest if not provided
if [ -z "$PACK_DIR" ]; then
    PACK_DIR=$(ls -dt runs/pack_* 2>/dev/null | head -n 1)
fi

if [ -z "$PACK_DIR" ]; then
    echo "Error: No pack found in runs/ and no argument provided."
    exit 1
fi

echo "Verifying Pack: $PACK_DIR"

# Check Calibration Dump (Baseline usually has most trades)
DUMP_FILE="$PACK_DIR/A_Baseline/calibration_dump.csv"

if [ ! -f "$DUMP_FILE" ]; then
    echo "Error: $DUMP_FILE not found."
    echo "Tip: Run ./scripts/backfill_calibration.sh --pack \"$PACK_DIR\" --force"
    exit 1
fi

echo "Found: $DUMP_FILE"
echo "--- First 3 Rows ---"
head -n 3 "$DUMP_FILE"

echo ""
echo "--- Column Verification (Python One-Liner) ---"
# Python One-Liner to parse CSV properly
python3 -c "
import csv, sys
try:
    with open('$DUMP_FILE') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 3: break
            print(f\"Row {i+1}: Score={row.get('Score','N/A')} Safety={row.get('SafetyFactor','N/A')} Exp={row.get('ExpMove','N/A')} Cost={row.get('Cost','N/A')} Real={row.get('Realized','N/A')}\")
except Exception as e:
    print(f'Error parsing CSV: {e}')
"
