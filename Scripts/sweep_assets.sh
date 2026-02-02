#!/bin/bash
set -euo pipefail

START="2024-01-01"
END="2024-02-01"
DIR="argus_py/data"
PACK_ID="sweep_assets_$(date +%Y%m%d_%H%M%S)"
PACK_DIR="runs/$PACK_ID"
mkdir -p "$PACK_DIR"

echo "=== ASSET SWEEP (BTC, ETH, SOL, BNB) ==="
echo "Pack: $PACK_ID"

NORM_COST="--fee_bps 10.0 --slippage_bps 5.0 --spread_bps 5.0 --use_bid_ask --start_balance 10000"

run_asset() {
    SYM=$1
    NAME="Asset_${SYM}"
    echo ">> Running $NAME (V5 Adx45)..."
    python3 -m argus_py.runner.cli \
        --symbol "$SYM" --start_date "$START" --end_date "$END" --data_dir "$DIR" \
        --mode adaptive --quiet $NORM_COST \
        --min_adx 45.0 --max_exp_move_bps 80.0 \
        > "$PACK_DIR/$NAME.log" 2>&1
        
    RUN_ID=$(grep "Log Dir:" "$PACK_DIR/$NAME.log" | awk '{print $3}')
    if [ ! -z "$RUN_ID" ]; then
        mv "$RUN_ID" "$PACK_DIR/$NAME"
        echo "  Saved to $PACK_DIR/$NAME"
    fi
}

for sym in BTCUSDT ETHUSDT SOLUSDT BNBUSDT; do
    run_asset "$sym"
done

echo "=== SWEEP COMPLETE ==="
python3 -m argus_py.reporting.diagnostics "$PACK_DIR"
echo "Report: $PACK_DIR/diagnostics.md"
