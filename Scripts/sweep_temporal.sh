#!/bin/bash
set -euo pipefail

# Config
SYM="BTCUSDT"
START="2023-07-01"
END="2024-01-01"
# Use Temporal Data Dir
DIR="argus_py/data/temporal"

PACK_ID="sweep_temporal_$(date +%Y%m%d_%H%M%S)"
PACK_DIR="runs/$PACK_ID"
mkdir -p "$PACK_DIR"

echo "=== TEMPORAL SWEEP (BTC 2023 H2) ==="
echo "Pack: $PACK_ID"
echo "Data: $DIR (Range: $START -> $END)"

NORM_COST="--fee_bps 10.0 --slippage_bps 5.0 --spread_bps 5.0 --use_bid_ask --start_balance 10000"

run_test() {
    NAME=$1
    shift
    echo ">> Running $NAME..."
    python3 -u -m argus_py.runner.cli \
        --symbol "$SYM" --start_date "$START" --end_date "$END" --data_dir "$DIR" \
        --mode adaptive --quiet $NORM_COST \
        "$@" \
        > "$PACK_DIR/$NAME.log" 2>&1
        
    RUN_ID=$(grep "Log Dir:" "$PACK_DIR/$NAME.log" | awk '{print $3}')
    if [ ! -z "$RUN_ID" ]; then
        mv "$RUN_ID" "$PACK_DIR/$NAME"
        echo "  Saved to $PACK_DIR/$NAME"
    else
        echo "  Failed (Check Log)"
    fi
}

# 1. Baseline
run_test "Baseline_2023H2"

# 2. V5 AdxGate (OOS Test)
run_test "V5_Adx45_2023H2" --min_adx 45.0 --max_exp_move_bps 80.0

echo "=== SWEEP COMPLETE ==="
python3 -m argus_py.reporting.diagnostics "$PACK_DIR"
echo "Report: $PACK_DIR/diagnostics.md"
