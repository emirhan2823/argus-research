import sys
import os

# Ensure we can import from config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from config.settings import MAX_RISK_PER_TRADE, MAX_DAILY_LOSS, MAX_DRAWDOWN, LEVERAGE

class RiskManager:
    """
    Implements 'Survival First' risk management rules.
    """

    def __init__(self, initial_balance=10000.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.start_of_day_balance = initial_balance
        self.daily_pnl = 0.0
        self.peak_balance = initial_balance
        self.current_drawdown = 0.0

    def update_balance(self, new_balance):
        """
        Updates the account balance and recalculates drawdown.
        """
        self.current_balance = new_balance
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance

        self.current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        self.daily_pnl = self.current_balance - self.start_of_day_balance

    def check_trade_allowed(self):
        """
        Checks if a trade is allowed based on daily loss and drawdown limits.
        """
        if self.daily_pnl < - (self.initial_balance * MAX_DAILY_LOSS):
            print(f"Daily loss limit hit: {self.daily_pnl} < -{self.initial_balance * MAX_DAILY_LOSS}")
            return False

        if self.current_drawdown > MAX_DRAWDOWN:
            print(f"Max drawdown limit hit: {self.current_drawdown} > {MAX_DRAWDOWN}")
            return False

        return True

    def calculate_position_size(self, entry_price, stop_loss_price, account_balance):
        """
        Calculates position size based on risk per trade (fixed fractional).
        Formula: Position Size = (Account Balance * Risk %) / (Entry Price - Stop Loss Price)
        """
        risk_amount = account_balance * MAX_RISK_PER_TRADE
        price_difference = abs(entry_price - stop_loss_price)

        if price_difference == 0:
            return 0

        position_size = risk_amount / price_difference

        # Apply leverage constraint
        max_position_value = account_balance * LEVERAGE
        position_value = position_size * entry_price

        if position_value > max_position_value:
            position_size = max_position_value / entry_price
            print(f"Position size capped by leverage: {position_size}")

        return position_size

    def reset_daily_pnl(self):
        """
        Resets daily PnL at the start of a new trading day.
        """
        self.start_of_day_balance = self.current_balance
        self.daily_pnl = 0.0
        # In a real system, we'd sync this with the exchange daily reset time.
