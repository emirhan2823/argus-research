import os
from dotenv import load_dotenv

load_dotenv()

# --- Exchange Configuration ---
BINGX_API_KEY = os.getenv("BINGX_API_KEY")
BINGX_SECRET_KEY = os.getenv("BINGX_SECRET_KEY")
EXCHANGE_ID = "bingx"
SYMBOL = "XAU/USDT:USDT"  # Default Symbol (Gold Futures)
TIMEFRAME = "4h"

# --- Risk Management Settings ("Survival First") ---
MAX_RISK_PER_TRADE = 0.01  # 1% of account equity per trade
MAX_DAILY_LOSS = 0.02      # Stop trading if daily loss exceeds 2%
MAX_DRAWDOWN = 0.06        # Stop trading if total drawdown exceeds 6%
LEVERAGE = 5               # Conservative leverage for "Survival First" approach

# --- Strategy Parameters ---
EMA_SHORT_PERIOD = 50
EMA_LONG_PERIOD = 200
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 2.0    # Stop Loss multiplier
ATR_MULTIPLIER_TP = 4.0    # Take Profit multiplier (Risk:Reward 1:2)

# --- Backtesting Settings ---
INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.00045  # Standard taker fee (0.045%)
SLIPPAGE = 0.0001          # Estimated slippage
