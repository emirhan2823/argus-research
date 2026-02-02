#!/bin/bash
# Validate ExpMove Reliability & Calibration Dump

# Reuse the last validation pack if it exists, otherwise define one.
# For robustness, let's just create a new one using the last run from validate_expmove if available, or run fresh.
# Actually, the user wants "Per-Trade Calibration Dump" so running on existing data is cleaner for speed.

LAST_VAL_PACK=$(ls -dt runs/val_pack_* 2>/dev/null | head -1)

if [ -z "$LAST_VAL_PACK" ]; then
    echo "No validation pack found. Creating one..."
    # Run simple backtest
    python3 -m argus_py.runner.cli --symbol BTCUSDT --data_dir argus_py/data --start_date 2024-01-01 --end_date 2024-01-07 --report --quiet
    RUN_DIR=$(ls -dt runs/20* | head -1)
    LAST_VAL_PACK="runs/val_pack_$(date +%s)"
    mkdir -p "$LAST_VAL_PACK/A_Scenario"
    cp -r "$RUN_DIR/"* "$LAST_VAL_PACK/A_Scenario/"
fi

echo "Running Diagnostics on $LAST_VAL_PACK"
python3 -m argus_py.reporting.diagnostics "$LAST_VAL_PACK"

echo ""
echo "--- Reliability Results ---"
grep -A 20 "## ExpMove Reliability" "$LAST_VAL_PACK/diagnostics.md"

echo ""
echo "--- Cost Verification ---"
grep -A 10 "## Cost Model Verification" "$LAST_VAL_PACK/diagnostics.md"

echo ""
echo "--- Dump Check ---"
if [ -f "$LAST_VAL_PACK/calibration_dump.csv" ]; then
    echo "Calibration Dump exists:"
    head -n 3 "$LAST_VAL_PACK/calibration_dump.csv"
else
    echo "ERROR: calibration_dump.csv NOT found."
fi
