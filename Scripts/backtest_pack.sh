#!/bin/bash
set -euo pipefail

SYM=${1:-"BTCUSDT"}
START=${2:-"2024-01-01"}
END=${3:-"2024-01-05"}
DIR=${4:-"argus_py/data"}

# Create Pack output dir
PACK_ID="pack_$(date +%Y%m%d_%H%M%S)"
PACK_DIR="runs/$PACK_ID"
mkdir -p "$PACK_DIR"

echo "=== ARGUS BACKTEST PACK ==="
echo "Pack ID: $PACK_ID"
echo "Range: $START -> $END"

# Function to run backtest
run_test() {
    NAME=$1
    shift
    echo ">> Running $NAME..."
    OUT_DIR="$PACK_DIR/$NAME"
    LOG="$PACK_DIR/${NAME}.log"
    
    python3 -m argus_py.runner.cli \
        --symbol "$SYM" \
        --start_date "$START" \
        --end_date "$END" \
        --data_dir "$DIR" \
        --mode adaptive \
        --quiet \
        --min_warmup 10 \
        "$@" > "$LOG" 2>&1 || echo "Run $NAME failed (see log)"
        
    # Get ID from log "Log Dir: runs/..."
    # Actually the CLI prints "Log Dir: ..."
    # We can grep it.
    RUN_ID=$(grep "Log Dir:" "$LOG" | awk '{print $3}')
    if [ ! -z "$RUN_ID" ]; then
        # Move run to inside pack dir for organization
        mv "$RUN_ID" "$OUT_DIR"
        echo "  Saved to $OUT_DIR"
        
        # Extract stats
        if [ -f "$OUT_DIR/summary.json" ]; then
            RET=$(grep "Total Return" "$OUT_DIR/report.md" | head -n 1 | awk -F'|' '{print $3}')
            TRADES=$(wc -l < "$OUT_DIR/trades.csv")
            echo "  Return: $RET | Trades: $TRADES"
        fi
    else
        echo "  Failed to parse Run ID"
    fi
}

echo ""
# --- PHASE 3: Refactor & Optimization ---
# Common Args: Normalized Cost (20bps)
NORM_COST="--fee_bps 10.0 --slippage_bps 5.0 --spread_bps 5.0 --use_bid_ask --start_balance 10000"

# 1. Baseline (Normalized)
run_test "A_Baseline_Norm" $NORM_COST

echo ""
echo "=== STRATEGY PHASE-3 VARIANTS ==="

# 2. V1: Sell Only
run_test "V1_SellOnly" $NORM_COST --disable_buy

# 3. V2: MaxExp 80 (Now Fixed)
run_test "V2_CapExp80" $NORM_COST --max_exp_move_bps 80.0

# 4. VT_1.8_Smart (VolTrap V2)
run_test "VT_1.8_Smart" $NORM_COST --vol_trap_v2 --vol_trap_threshold 1.8

# 5. VT_2.5_Smart
run_test "VT_2.5_Smart" $NORM_COST --vol_trap_v2 --vol_trap_threshold 2.5

# 6. V4_Combo (Sell + MaxExp + VT_2.5)
run_test "V4_Combo" $NORM_COST \
  --disable_buy --max_exp_move_bps 80.0 --vol_trap_v2 --vol_trap_threshold 2.5

# 7. V5_Adx45 (Global Strong Trend + MaxExp) -> No Direction Bias Needed?
run_test "V5_Adx45" $NORM_COST \
  --min_adx 45.0 --max_exp_move_bps 80.0

echo "=== DIAGNOSTICS ==="
# Generate Calibration Dump (Backfill logic)
python3 -m argus_py.reporting.backfill --pack "$PACK_DIR" --force

python3 -m argus_py.reporting.diagnostics "$PACK_DIR" || echo "Diagnostics failed"
echo "Report: $PACK_DIR/diagnostics.md"

echo "=== PACK COMPLETE ==="
echo "Results in $PACK_DIR"
