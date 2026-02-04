# Phase 17 Out-Sample Cache Guide

## Overview
Phase 17 runs parameter grids over two windows:
1. **INSAMPLE**: `2024-02-01` -> `2024-03-15`
2. **OUTSAMPLE**: `2024-03-15` -> `2024-04-15`

Argus strictly requires data cache files that cover these ranges.

## Error: "Dataset Range Mismatch"
If you see this error, it means the requested range is not covered by any single file in `argus_py/data/cache`.

### Resolution

1. **Verify Coverage**:
   Run the verification script to pinpoint missing ranges:
   ```bash
   python3 scripts/verify_dataset_coverage.py --symbol BTCUSDT --start_date 2024-03-15 --end_date 2024-04-15
   ```

2. **Download Missing Data**:
   Use the built-in downloader to fetch 1-minute klines from Binance.
   
   **For Out-Sample**:
   ```bash
   python3 -m argus_py.data.binance_downloader --symbol BTCUSDT --start_date 2024-03-15 --end_date 2024-04-15 --output_dir argus_py/data/cache
   ```

3. **Verify Again**:
   Re-run the verification script. It should now say `PASS`.

## Grid Execution
Once cache is populated, proceed with the grid:
```bash
python3 scripts/phase17_grid.py --window OUTSAMPLE
```
