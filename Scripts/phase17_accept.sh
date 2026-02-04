#!/bin/bash
set -e

echo "=== Phase 17 Acceptance Test ==="

# 1. Setup Output
OUTDIR="runs/phase17_accept_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTDIR"
echo ">> Using Acceptance Dir: $OUTDIR"

# 2. Coverage Pre-Check (In-Sample)
echo ">> Step 0: Coverage Check (INSAMPLE)"
# Use explicit data_dir
if ! python3 scripts/verify_dataset_coverage.py --symbol BTCUSDT --start_date 2024-02-01 --end_date 2024-03-15 --data_dir argus_py/data/cache; then
    echo "FAIL: INSAMPLE Data Missing. Aborting."
    exit 1
fi

# 3. Coverage Pre-Check (Out-Sample)
echo ">> Step 0b: Coverage Check (OUTSAMPLE)"
if ! python3 scripts/verify_dataset_coverage.py --symbol BTCUSDT --start_date 2024-03-15 --end_date 2024-04-15 --data_dir argus_py/data/cache; then
    echo "FAIL: OUTSAMPLE Data Missing."
    echo "Sugestion: Run the downloader command shown above."
    # Fail fast!
    exit 1
fi

# 4. Run In-Sample Small Grid (6 pts)
echo ">> Step 1: In-Sample Grid (6 points)"
python3 scripts/phase17_grid.py --window INSAMPLE --points 6 --symbol BTCUSDT --outdir "$OUTDIR"

# 5. Run Out-Sample Small Grid (6 pts) - In Same Dir
echo ">> Step 2: Out-Sample Grid (6 points)"
# Use --resume to ensure we append/don't overwrite if collision (though windows differ)
python3 scripts/phase17_grid.py --window OUTSAMPLE --points 6 --symbol BTCUSDT --outdir "$OUTDIR" --resume

# 4. Validation
echo ">> Step 3: Validating Artifacts"

check_csv() {
    CSV=$1
    if [ ! -f "$CSV" ]; then
        echo "FAIL: $CSV missing."
        exit 1
    fi
    ROWS=$(wc -l < "$CSV")
    # Header + 6 rows = 7 lines optimal. 
    if [ "$ROWS" -lt 7 ]; then
        echo "FAIL: $CSV has insufficient rows ($ROWS). Expected >= 7."
        exit 1
    fi
    # Check for empty cells in metrics (implying None/NaN logic worked but data missing)
    # Actually just check basic integrity
    echo "PASS: $CSV ($ROWS lines)."
}

check_csv "$OUTDIR/grid_summary_INSAMPLE.csv"
check_csv "$OUTDIR/grid_summary_OUTSAMPLE.csv"

# Check Fingerprints and Runs
if grep -q "Error" "$OUTDIR/grid_summary_INSAMPLE.csv"; then
    echo "WARNING: Found 'Error' in fingerprints."
fi

# 5. Generate Surface
echo ">> Step 4: Testing Surface Generator"
python3 scripts/phase17_surface.py "$OUTDIR"

# Verify Surface Files
if [ ! -f "$OUTDIR/phase17_surface_summary.md" ]; then
    echo "FAIL: Summary MD not generated."
    exit 1
fi

echo "=== ACCEPTANCE PASSED ==="
