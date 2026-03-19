#!/bin/zsh
# Verify ShiftScore presence and distribution in latest pack

# 1. Find Latest Pack
LATEST_PACK=$(ls -dt runs/pack_* | head -n 1)

if [[ -z "$LATEST_PACK" ]]; then
    echo "No packs found."
    exit 1
fi

echo "Checking Pack: $LATEST_PACK"

# 2. Check Decision Log
# Prefer A_Baseline_Norm or A_Baseline
if [[ -f "$LATEST_PACK/A_Baseline_Norm/decision_log.csv" ]]; then
    DEC_LOG="$LATEST_PACK/A_Baseline_Norm/decision_log.csv"
elif [[ -f "$LATEST_PACK/A_Baseline/decision_log.csv" ]]; then
    DEC_LOG="$LATEST_PACK/A_Baseline/decision_log.csv"
else
    # Fallback to first dir
    SCENARIO=$(ls -d $LATEST_PACK/*/ 2>/dev/null | head -n 1)
    if [[ -z "$SCENARIO" ]]; then
        # Last resort: root
        DEC_LOG="$LATEST_PACK/decision_log.csv"
    else
        DEC_LOG="${SCENARIO}decision_log.csv"
    fi
fi

echo "Target Decision Log: $DEC_LOG"

if [[ ! -f "$DEC_LOG" ]]; then
    echo "No decision_log.csv found in $LATEST_PACK"
    exit 1
fi

# 3. Check Header
HEADER=$(head -n 1 "$DEC_LOG")
if [[ "$HEADER" != *"ShiftScore"* ]]; then
    echo "FAIL: ShiftScore column missing."
    echo "Header: $HEADER"
    exit 1
else
    echo "PASS: ShiftScore column present."
    # Check for AtrRatio/VolRatio/VolMissing
    if [[ "$HEADER" == *"VolMissing"* ]]; then
         echo "PASS: VolMissing column present."
    fi
fi

# 4. Print First 5 Rows (ShiftScore columns)
echo "\nFirst 5 Rows (ShiftScore, ModeSuggest, AtrRatio, VolRatio, ...):"
python3 -c "
import pandas as pd
import sys
try:
    df = pd.read_csv('$DEC_LOG')
    # Dynamic column selection based on existence
    candidates = ['Timestamp', 'ShiftScore', 'ModeSuggest', 'AtrRatio', 'VolRatio', 'AdxFlip', 'FakeBreak', 'VolMissing']
    cols = [c for c in candidates if c in df.columns]
    print(df[cols].head(5).to_string(index=False))
    
    # 5. Distribution
    print('\nShiftScore Distribution:')
    print(df['ShiftScore'].describe())
    
    print('\nMode Suggestion:')
    print(df['ModeSuggest'].value_counts(normalize=True))
except Exception as e:
    print(e)
"
