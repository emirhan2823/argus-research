# Hedge Fund Style Trading Bot

A robust, modular trading system designed for high reliability and risk management ("Survival First").
Targeting consistent returns (6-8% monthly goal) on Commodities and Indices via BingX Futures.

## Features

- **Risk Management Module:** Strict position sizing (Kelly/Fixed Fractional), Daily Loss Limits, Max Drawdown Limits.
- **Strategy Engine:** Modular strategy implementation (Trend Following, Mean Reversion).
- **Execution Interface:** Connects to BingX via CCXT.
- **Backtesting:** Verify strategies on historical data.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API keys:
   - Create a `.env` file based on the template.
   - Add your `BINGX_API_KEY` and `BINGX_SECRET_KEY`.

## Usage

Run the main bot:
```bash
python src/main.py
```

Run backtests:
```bash
python src/core/backtester.py
```

## Structure

- `src/core/`: Core logic (Risk Manager, Backtester).
- `src/strategies/`: Strategy implementations.
- `src/data/`: Data fetching and exchange interaction.
- `config/`: Configuration settings.
- `tests/`: Unit tests.
