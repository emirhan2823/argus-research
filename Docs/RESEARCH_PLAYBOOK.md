# Research Playbook & Dataset Standards

## Dataset Standards

For Argus backtesting to work correctly, market data CSV files must follow these standards:

### 1. File Naming
- **Format**: `SYMBOL.csv` (e.g., `BTCUSDT.csv`, `ETHUSDT_1h.csv`)
- **Location**: `argus_py/data/` (or specified via `--data_dir`)
- **Best Practice**: Use uppercase symbols matching the exchange pair names.

### 2. CSV Columns
The CSV must have a header row and the following columns (order matters if columns not named exactly, but standard parsing is robust):

| Column | Description | Unit |
| :--- | :--- | :--- |
| `timestamp` | Time of the bar | Unix Timestamp (Seconds or Milliseconds) |
| `open` | Opening price | float |
| `high` | Highest price | float |
| `low` | Lowest price | float |
| `close` | Closing price | float |
| `volume` | Volume | float |

**Note**: If timestamp > 1e12 (trillions), loader assumes Milliseconds and converts to Seconds.

### 3. Data Integrity
- **Monotonic**: Timestamps must strictly increase.
- **Positive**: Prices must be > 0.
- **Valid Candles**: `High >= Open`, `High >= Close`, `Low <= Open`, `Low <= Close`.

---

## Running Backtests

### Basic Command
```bash
python3 -m argus_py.runner.cli --symbol BTCUSDT --data_dir argus_py/data --mode adaptive
```

### Options
- `--max_bars N`: Load only the last N bars (useful for quick tests).
  - **Warning**: If N < 200, indicators may stay in WARMUP mode.
- `--start_balance`: Initial capital (default 1000).
- `--report`: Generate charts and markdown report.

### Troubleshooting
- **"No CSV files found"**: Ensure your file name matches the `--symbol` (e.g. `BTCUSDT` -> `BTCUSDT.csv`).
- **"Expect NO_GO signals"**: Your dataset is too short (< 200 bars). Increase `max_bars` or use a larger dataset.
- **"WARNING: using sample data"**: You are running on `sample.csv`. Results are not indicative of real performance.
