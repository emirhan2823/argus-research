#!/bin/bash
set -euo pipefail

# Config: Dec 2023 (1 Month OOS)
SYM="BTCUSDT"
START="2023-12-01"
END="2024-01-01"
DIR="argus_py/data/temporal"

PACK_ID="sweep_temporal_dec23_$(date +%Y%m%d_%H%M%S)"
PACK_DIR="runs/$PACK_ID"
mkdir -p "$PACK_DIR"

echo "=== TEMPORAL SWEEP (BTC DEC 2023) ==="
echo "Pack: $PACK_ID"

NORM_COST="--fee_bps 10.0 --slippage_bps 5.0 --spread_bps 5.0 --use_bid_ask --start_balance 10000"

run_test() {
    NAME=$1
    shift
    echo ">> Running $NAME..."
    python3 -m argus_py.runner.cli \
        --symbol "$SYM" --start_date "$START" --end_date "$END" --data_dir "$DIR" \
        --mode adaptive --quiet $NORM_COST \
        "$@" \
        > "$PACK_DIR/$NAME.log" 2>&1
        
    RUN_ID=$(grep "Log Dir:" "$PACK_DIR/$NAME.log" | awk '{print $3}')
    if [ ! -z "$RUN_ID" ]; then
        mv "$RUN_ID" "$PACK_DIR/$NAME"
        echo "  Saved to $PACK_DIR/$NAME"
    fi
}

run_test "Baseline_Dec23"
run_test "V5_Adx45_Dec23" --min_adx 45.0 --max_exp_move_bps 80.0

echo "=== SWEEP COMPLETE ==="
python3 -m argus_py.reporting.diagnostics "$PACK_DIR"
echo "Report: $PACK_DIR/diagnostics.md"
