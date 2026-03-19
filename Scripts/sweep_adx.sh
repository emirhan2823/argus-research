#!/bin/bash
set -euo pipefail

SYM="BTCUSDT"
START="2024-01-01"
END="2024-02-01"
DIR="argus_py/data"
PACK_ID="sweep_adx_$(date +%Y%m%d_%H%M%S)"
PACK_DIR="runs/$PACK_ID"
mkdir -p "$PACK_DIR"

echo "=== ADX SWEEP (30-60) ==="
echo "Pack: $PACK_ID"

NORM_COST="--fee_bps 10.0 --slippage_bps 5.0 --spread_bps 5.0 --use_bid_ask --start_balance 10000"

run_sweep() {
    ADX=$1
    NAME="Adx_${ADX}"
    echo ">> Running $NAME (MinADX $ADX)..."
    python3 -m argus_py.runner.cli \
        --symbol "$SYM" --start_date "$START" --end_date "$END" --data_dir "$DIR" \
        --mode adaptive --quiet $NORM_COST \
        --min_adx "$ADX" --max_exp_move_bps 80.0 \
        > "$PACK_DIR/$NAME.log" 2>&1
        
    RUN_ID=$(grep "Log Dir:" "$PACK_DIR/$NAME.log" | awk '{print $3}')
    if [ ! -z "$RUN_ID" ]; then
        mv "$RUN_ID" "$PACK_DIR/$NAME"
        echo "  Saved to $PACK_DIR/$NAME"
    fi
}

for val in 30 35 40 45 50 55 60; do
    run_sweep "$val"
done

echo "=== SWEEP COMPLETE ==="
python3 -m argus_py.reporting.diagnostics "$PACK_DIR"
echo "Report: $PACK_DIR/diagnostics.md"
