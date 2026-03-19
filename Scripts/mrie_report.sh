#!/bin/zsh
# Generate and Show MRIE Report from Latest Pack

# 1. Find Latest Pack (Robust)
LATEST_PACK=$(ls -dt runs/* | head -n 1)

if [[ -z "$LATEST_PACK" ]]; then
    echo "No packs found."
    exit 1
fi

echo ">> Analyzing Pack: $LATEST_PACK"

# 2. Run Diagnostics (Update Logic)
# This generates calibration_dump.csv and updates diagnostics.md with new sections
python3 -m argus_py.reporting.diagnostics "$LATEST_PACK"

REPORT_MD="$LATEST_PACK/diagnostics.md"

if [[ ! -f "$REPORT_MD" ]]; then
    echo "Report generation failed."
    exit 1
fi

echo "\n=== MRIE REPORT START ===\n"

# 3. Print MRIE Sections
# Use sed/awk to extract sections
# Section 1: Regime ShiftScore Summary (Early in file, Phase 7 header)
# Section 2: MRIE ShiftScore Reliability (End of file, Phase 7 bonus)

# Extract "Regime ShiftScore Summary" until next header
echo "--- DISTRIBUTION SUMMARY ---"
sed -n '/## Regime ShiftScore Summary/,/##/p' "$REPORT_MD" | sed '$d'

echo "\n--- RELIABILITY ANALYSIS ---"
sed -n '/## MRIE ShiftScore Reliability/,$p' "$REPORT_MD"


echo "\n=== MRIE REPORT END ==="
