#!/bin/bash
set -euo pipefail

# Defaults
DATA_DIR=${1:-"argus_py/data"}
SYMBOL=${2:-"BTCUSDT"}
START_DATE=${3:-"2024-01-01"}
END_DATE=${4:-"2024-01-05"}
BAL=${5:-"30"}

echo "=== Argus Real BTC Pipeline (Quiet) ==="
echo "DIR: $DATA_DIR | SYM: $SYMBOL | DATE: $START_DATE -> $END_DATE"

# A) Download Only
echo ""
echo "[1/3] Downloading Data (Exit after download)..."
if python3 -m argus_py.runner.cli \
    --download_binance \
    --symbol "$SYMBOL" \
    --start_date "$START_DATE" \
    --end_date "$END_DATE" \
    --data_dir "$DATA_DIR"; then
    echo "Download OK."
else
    echo "ERROR: Download Failed."
    exit 1
fi

# B) Backtest
echo ""
echo "[2/3] Running Backtest (Quiet)..."
# Pass --quiet to suppress trade spam
python3 -m argus_py.runner.cli \
    --symbol "$SYMBOL" \
    --start_date "$START_DATE" \
    --end_date "$END_DATE" \
    --start_balance "$BAL" \
    --mode adaptive \
    --data_dir "$DATA_DIR" \
    --min_warmup 200 \
    --max_bars 100000 \
    --report \
    --quiet

# C) Summary Check
echo ""
echo "[3/3] Pipeline Summary:"
LATEST_RUN=$(ls -dt runs/* | head -n 1)

if [ -d "$LATEST_RUN" ]; then
    echo "Files in $LATEST_RUN:"
    # Check for critical files
    if [ -f "$LATEST_RUN/trades.csv" ] && [ -f "$LATEST_RUN/decision_log.csv" ]; then
        echo "  [OK] trades.csv found"
        echo "  [OK] decision_log.csv found"
        
        # Verify Trade Count
        COUNT=$(wc -l < "$LATEST_RUN/trades.csv" | xargs)
        echo "  Trades Count: $COUNT"
        
        # Verify Return
        if [ -f "$LATEST_RUN/report.md" ]; then
            grep "Total Return" "$LATEST_RUN/report.md" || echo "Return not found in report"
        fi
        
        echo "PIPELINE OK"
    else
        echo "FAIL: Missing critical output files."
        exit 1
    fi
else
    echo "FAIL: No run directory found."
    exit 1
fi

echo "=== DONE ==="
