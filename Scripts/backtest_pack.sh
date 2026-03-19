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

# --- CACHE LOGIC ---
DATA_DIR="argus_py/data/cache"
mkdir -p "$DATA_DIR"

# Specific Range File
# Format: {SYMBOL}_1m_{START}_{END}.csv
RANGE_FILE="${SYM}_1m_${START}_${END}.csv"
CACHE_PATH="$DATA_DIR/$RANGE_FILE"

echo "Checking Data Cache for: $RANGE_FILE"
if [ ! -f "$CACHE_PATH" ]; then
    echo ">> Cache Miss. Downloading..."
    python3 -m argus_py.runner.cli \
        --symbol "$SYM" \
        --data_dir "$DATA_DIR" \
        --start_date "$START" \
        --end_date "$END" \
        --download_binance \
        --quiet || { echo "Download Failed"; exit 1; }
        
    echo ">> Download Complete."
else
    echo ">> Cache Hit."
fi

# Force use of Cache Dir
DIR="$DATA_DIR"

# Function to run backtest
run_test() {
    NAME=$1
    shift
    echo ">> Running $NAME..."
    OUT_DIR="$PACK_DIR/$NAME"
    LOG="$PACK_DIR/${NAME}.log"
    
    # Run CLI
    set +e # Allow failure for capture
    python3 -m argus_py.runner.cli \
        --symbol "$SYM" \
        --start_date "$START" \
        --end_date "$END" \
        --data_dir "$DIR" \
        --mode adaptive \
        --quiet \
        --min_warmup 10 \
        "$@" > "$LOG" 2>&1
    RET_CODE=$?
    set -e
    
    if [ $RET_CODE -ne 0 ]; then
        echo "Run $NAME failed (Exit $RET_CODE). Log Tail:"
        tail -n 20 "$LOG"
        exit 1
    fi
        
    # Get ID from log "Log Dir: runs/..."
    RUN_ID=$(grep "Log Dir:" "$LOG" | awk '{print $3}')
    if [ ! -z "$RUN_ID" ]; then
        if [ -d "$RUN_ID" ]; then
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
             echo "  Log ID found ($RUN_ID) but dir missing?!"
        fi
    else
        echo "  Failed to parse Run ID from log."
        tail -n 20 "$LOG"
    fi
}

echo ""
# --- PHASE 3: Refactor & Optimization ---
# Common Args: Normalized Cost (20bps)
# Allow Env Overrides
FEE=${ARGUS_FEE_BPS:-10.0}
SLIP=${ARGUS_SLIPPAGE_BPS:-5.0}
SPREAD=${ARGUS_SPREAD_BPS:-5.0}

echo "FRICTION SETTINGS: Fee=$FEE Slip=$SLIP Spread=$SPREAD"

NORM_COST="--fee_bps $FEE --slippage_bps $SLIP --spread_bps $SPREAD --use_bid_ask --start_balance 10000"

# 1. Baseline (Normalized)
run_test "A_Baseline_Norm" $NORM_COST

echo ""
echo "=== STRATEGY PHASE-3 VARIANTS ==="

# 2. V1: Adx45 (Replaces Legacy SellOnly)
run_test "V1_Adx45" $NORM_COST --min_adx 45.0

# 3. V2: MaxExp 80 (Now Fixed)
run_test "V2_CapExp80" $NORM_COST --max_exp_move_bps 80.0

# 4. VT_1.8_Smart (VolTrap V2)
run_test "VT_1.8_Smart" $NORM_COST --vol_trap_v2 --vol_trap_threshold 1.8

# 5. VT_2.5_Smart
run_test "VT_2.5_Smart" $NORM_COST --vol_trap_v2 --vol_trap_threshold 2.5

# 6. V4_Combo (MaxExp + VT_2.5) -> Buy Enabled
run_test "V4_Combo" $NORM_COST \
  --max_exp_move_bps 80.0 --vol_trap_v2 --vol_trap_threshold 2.5

# 7. V5_Adx45_MaxExp -> Strong Trend + Cap
run_test "V5_Adx45_MaxExp" $NORM_COST \
  --min_adx 45.0 --max_exp_move_bps 80.0

# 8. SMOKE TEST: Precedence Check (MinADX 80)
# Should have ZERO or VERY FEW trades. If identical to Baseline (45), precedence is broken.
run_test "SMOKE_MinAdx80" $NORM_COST --min_adx 80.0

echo "=== DIAGNOSTICS ==="
# Generate Calibration Dump (Backfill logic)
python3 -m argus_py.reporting.backfill --pack "$PACK_DIR" --force

python3 -m argus_py.reporting.diagnostics "$PACK_DIR" || echo "Diagnostics failed"
echo "Report: $PACK_DIR/diagnostics.md"

echo "=== PACK COMPLETE ==="
echo "Results in $PACK_DIR"
