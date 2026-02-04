#!/bin/bash
CSV=$1
if [ -z "$CSV" ] || [ ! -f "$CSV" ]; then
  echo "Usage: ./dataset_range.sh <csv_file>"
  exit 1
fi

python3 -c "
import sys, pandas as pd
try:
    df = pd.read_csv(sys.argv[1])
    if df.empty:
        print('Rows: 0 | Range: N/A')
    else:
        # Assume Timestamp col exists or first col
        ts_col = 'Timestamp' if 'Timestamp' in df.columns else df.columns[0]
        t_min = df[ts_col].min()
        t_max = df[ts_col].max()
        
        # Convert to readable if possible, but raw ts is requested
        print(f'Rows: {len(df)} | Min: {t_min} | Max: {t_max}')
except Exception as e:
    print(f'Error reading {sys.argv[1]}: {e}')
" "$CSV"
