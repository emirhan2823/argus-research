#!/bin/zsh
# MRIE Sanity Check for ShiftScore Inputs

# 1. Find Latest Pack
LATEST_PACK=$(ls -dt runs/pack_* | head -n 1)

if [[ -z "$LATEST_PACK" ]]; then
    echo "No packs found."
    exit 1
fi

echo ">> Sanity Checking Pack: $LATEST_PACK"

# 2. Identify Baseline Log
if [[ -f "$LATEST_PACK/A_Baseline_Norm/decision_log.csv" ]]; then
    DEC_LOG="$LATEST_PACK/A_Baseline_Norm/decision_log.csv"
elif [[ -f "$LATEST_PACK/A_Baseline/decision_log.csv" ]]; then
    DEC_LOG="$LATEST_PACK/A_Baseline/decision_log.csv"
else
    SCENARIO=$(ls -d $LATEST_PACK/*/ 2>/dev/null | head -n 1)
    DEC_LOG="${SCENARIO}decision_log.csv"
fi

if [[ ! -f "$DEC_LOG" ]]; then
    echo "DecLog not found."
    exit 1
fi

echo "Log: $DEC_LOG"

# 3. Python Analysis
python3 -c "
import pandas as pd
import sys

try:
    df = pd.read_csv('$DEC_LOG')
    total = len(df)
    print(f'Total Rows: {total}')
    
    # Check column existence
    if 'AtrRatio' not in df.columns:
        print('ERROR: AtrRatio column missing.')
        sys.exit(1)
        
    # Active Stats
    active_atr = len(df[df['AtrRatio'] > 0])
    miss_vol = len(df[df['VolMissing'] == 1]) if 'VolMissing' in df.columns else 0
    active_vol = len(df[df['VolRatio'].notnull()])
    
    fake_breaks = len(df[df['FakeBreak'] == 1])
    adx_flips = len(df[df['AdxFlip'] == 1])
    
    print(f'Rows with AtrRatio > 0: {active_atr} ({active_atr/total*100:.1f}%)')
    print(f'Rows with VolMissing=1: {miss_vol} ({miss_vol/total*100:.1f}%)')
    print(f'FakeBreaks: {fake_breaks} ({fake_breaks/total*100:.1f}%)')
    print(f'AdxFlips: {adx_flips} ({adx_flips/total*100:.1f}%)')
    
    print('\nShiftScore Distribution:')
    print(df['ShiftScore'].describe())
    
    print('\nTop 20 High ShiftScore Rows:')
    cols = ['Timestamp', 'ShiftScore', 'ModeSuggest', 'AtrRatio', 'VolRatio', 'AdxFlip', 'FakeBreak']
    # Check for ADX column? usually OrionADX or similar?
    # 'OrionADX' in reporting.py mapping? 
    if 'OrionADX' in df.columns: cols.append('OrionADX')
    
    # Filter existing cols
    cols = [c for c in cols if c in df.columns]
    
    high_scores = df.sort_values('ShiftScore', ascending=False).head(20)
    print(high_scores[cols].to_string(index=False))

except Exception as e:
    print(f'Error: {e}')
"
