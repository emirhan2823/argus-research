#!/bin/bash
# Validate ExpMove Calibration & Cost Model

SYMBOL="BTCUSDT"
START_DATE="2024-01-01"
END_DATE="2024-01-14"

echo "--- 1. Running Backtest (Adaptive Cost Safety) ---"
python3 -m argus_py.runner.cli \
    --symbol $SYMBOL \
    --data_dir argus_py/data \
    --start_date $START_DATE \
    --end_date $END_DATE \
    --report \
    --quiet \
    --adaptive_cost_safety \
    --safety_percentile 30.0 \
    --exp_cap_mult 1.5

# Get the run dir (last created in runs/)
RUN_DIR=$(ls -dt runs/2* | head -1) # Match date timestamp dirs

echo "Raw Run Dir: $RUN_DIR"

# Create a Pack Structure for Diagnostics
PACK_DIR="runs/val_pack_$(date +%s)"
mkdir -p "$PACK_DIR/A_Scenario"
cp -r "$RUN_DIR/"* "$PACK_DIR/A_Scenario/"

echo ""
echo "--- 2. Running Diagnostics (on $PACK_DIR) ---"
python3 -m argus_py.reporting.diagnostics $PACK_DIR

echo ""
echo "--- 3. Results (Calibration & Cost) ---"
# Extract relevant sections from diagnostics.md
grep -A 10 "## ExpMove Calibration" $PACK_DIR/diagnostics.md
echo ""
grep -A 10 "## Cost Model Verification" $PACK_DIR/diagnostics.md
