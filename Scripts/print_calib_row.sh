#!/bin/bash
# Safe calibration row printer (No Heredocs)
# Usage: ./scripts/print_calib_row.sh [pack_path]

PACK_DIR="$1"

# Auto-detect latest if not provided
if [ -z "$PACK_DIR" ]; then
    PACK_DIR=$(ls -dt runs/pack_* 2>/dev/null | head -n 1)
fi

if [ -z "$PACK_DIR" ]; then
    echo "Error: No pack found in runs/ and no argument provided."
    exit 1
fi

DUMP_FILE="$PACK_DIR/A_Baseline/calibration_dump.csv"

if [ ! -f "$DUMP_FILE" ]; then
    echo "Error: $DUMP_FILE not found."
    echo "Did you run: ./scripts/backfill_calibration.sh --pack \"$PACK_DIR\" --force"
    exit 1
fi

echo "Source: $DUMP_FILE"
# Python One-Liner to parse and print first data row
python3 -c "
import csv
try:
    with open('$DUMP_FILE') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i == 0:
                print(f\"Row 1: Score={row.get('Score','N/A')} Safety={row.get('SafetyFactor','N/A')} Exp={row.get('ExpMove','N/A')} Cost={row.get('Cost','N/A')} Real={row.get('Realized','N/A')}\")
                break
except Exception as e:
    print(f'Error: {e}')
"
