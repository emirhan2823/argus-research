#!/bin/zsh
# Generate and Show Router Report from Latest Pack

LATEST_PACK=$(ls -dt runs/pack_* | head -n 1)

if [[ -z "$LATEST_PACK" ]]; then
    echo "No packs found."
    exit 1
fi

echo ">> Analyzing Pack: $LATEST_PACK"

# Run Diagnostics to populate calibration dump
python3 -m argus_py.reporting.diagnostics "$LATEST_PACK"

REPORT_MD="$LATEST_PACK/diagnostics.md"

if [[ ! -f "$REPORT_MD" ]]; then
    echo "Report generation failed."
    exit 1
fi

echo "\n=== ROUTER REPORT START ===\n"

# Extract Mode Router Analysis (at end of file)
sed -n '/## Mode Router Analysis/,$p' "$REPORT_MD"

echo "\n=== ROUTER REPORT END ==="
