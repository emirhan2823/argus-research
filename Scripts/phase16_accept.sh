#!/bin/bash
set -e

SYMBOL=${1:-BTCUSDT}
START=${2:-2024-02-01}
END=${3:-2024-02-14} # Short for speed

echo "=== Phase 16 Acceptance Test ==="
echo "Target: $SYMBOL ($START -> $END)"

# 1. PID Collision Safety Check (Static Analysis or existing runs?)
# We need to generate a run first.

# Helper for running and capturing
run_and_capture() {
    # 1=Name 2=ExtraArgs
    echo ">> Step: $1" >&2
    OUTFILE="/tmp/argus_run_$1.log"
    # Note: --start_date and --end_date and --symbol are passed from global vars
    # We must explicitly use --data_dir argus_py/data/cache as mandated
    CMD="python3 -m argus_py.runner.cli --symbol $SYMBOL --start_date $START --end_date $END --data_dir argus_py/data/cache --mode backtest --quiet --report $2"
    
    $CMD > "$OUTFILE" 2>&1
    if [ $? -ne 0 ]; then
        echo "FAIL: Run $1 exited with error." >&2
        cat "$OUTFILE" >&2
        exit 1
    fi
    
    # Extract Run Directory safely from logs
    RUN_DIR=$(grep "Logging run to:" "$OUTFILE" | awk '{print $NF}' | tr -d '\r')
    if [ ! -d "$RUN_DIR" ]; then
        echo "FAIL: Could not find run dir in output: $RUN_DIR" >&2
        cat "$OUTFILE" >&2
        exit 1
    fi
    echo "   Run Dir: $RUN_DIR" >&2
    echo "$RUN_DIR"
}

# 1. Baseline Run 1
RUN1=$(run_and_capture "Baseline1" "")
# 2. Baseline Run 2
sleep 1
RUN2=$(run_and_capture "Baseline2" "")

# Hash Helper
hash_run() {
    python3 -c "
import sys, os, pandas as pd, hashlib
try:
    path = os.path.join('$1', 'trades.csv')
    if not os.path.exists(path):
        print('EMPTY')
        sys.exit(0)
    df = pd.read_csv(path)
    if df.empty:
        print('0')
        sys.exit(0)
    # Filter for OPEN to match PositionID count/hash logic, or just all trades for determinism
    # Let's use ALL trades for strict determinism
    df = df.sort_values(by=['Timestamp', 'PositionId', 'Event'])
    raw = ''
    for _, row in df.iterrows():
        raw += f\"{row['Timestamp']}|{row['Side']}|{row['FillPrice']}|{row['Event']};\"
    print(hashlib.sha1(raw.encode()).hexdigest()[:8])
except Exception as e:
    print('ERROR')
"
}

HASH1=$(hash_run $RUN1)
HASH2=$(hash_run $RUN2)

if [ "$HASH1" == "ERROR" ] || [ "$HASH2" == "ERROR" ]; then
   echo "FAIL: Error calculating hash."
   exit 1
fi

if [ "$HASH1" != "$HASH2" ]; then
    echo "FAIL: Determinism Check Failed."
    echo "   Run1 Hash: $HASH1"
    echo "   Run2 Hash: $HASH2"
    exit 1
else
    echo "PASS: Determinism Verified ($HASH1)."
fi

# Verify Collision Safety
echo ">> Step 3: PID Collision Safety"
python3 scripts/verify_pid_collision_safety.py "$RUN1"

# 2. Divergence Check
RUN3=$(run_and_capture "Variant_Adx45" "--min_adx 45.0")
HASH3=$(hash_run $RUN3)

if [ "$HASH1" == "$HASH3" ]; then
    echo "FAIL: Divergence Check Failed."
    echo "   Baseline Hash: $HASH1"
    echo "   Variant Hash:  $HASH3"
    echo "   (They should differ)"
    exit 1
else
    echo "PASS: Divergence Verified ($HASH1 != $HASH3)."
fi

# 3. Grid Check
echo ">> Step 5: Grid Check (Small 6 points)"
python3 scripts/phase16_grid.py --symbol $SYMBOL --start $START --end $END --points 6

echo ""
echo "=== ACCEPTANCE PASSED ==="
