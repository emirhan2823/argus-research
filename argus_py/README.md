# Argus Python P0

Production-grade Python port of the Argus Trading System.

## Architecture
Strict parity with Swift MVP architecture:
- **Data**: Time-traveling `MarketState` (No lookahead).
- **Strategy**: `Aegean` (Signal) + `Orion` (Confirm) -> `Council` (Vote).
- **Risk**: State Machine (`NORMAL` -> `COOLDOWN` -> `SAFE`).
- **Broker**: `PaperBroker` with fractional quantities and Bracket Orders.

## Folder Structure
- `argus_py/core`: Shared utilities.
- `argus_py/data`: CSV Loaders and State.
- `argus_py/models`: Trading Logic (`aegean`, `orion`).
- `argus_py/council`: Aggregation logic.
- `argus_py/risk`: Safety gates.
- `argus_py/broker`: Execution simulation.
- `argus_py/runner`: CLI entry point.

## Running Tests
```bash
python3 -m unittest argus_py/tests/test_data.py
```

## Running Backtest
```bash
# Ensure you have data/sample.csv is available
python3 argus_py/runner/cli.py --data_dir argus_py/data/ --symbol BTCUSDT --start_balance 30
```

## Windows Deployment
Argus is designed to run as a **Scheduled Task** or Service on Windows.
1. Install Python 3.10+.
2. Use `NSSM` to wrap `python argus_py/runner/cli.py ...` as a service.
3. Logs are written to `logs/` for monitoring.
