from abc import ABC, abstractmethod
import pandas as pd
import pandas_ta as ta

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    """

    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.position = None # Current open position ('long', 'short', or None)
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame):
        """
        Analyzes data and returns a trading signal.
        Returns:
            signal: 'buy', 'sell', 'exit_long', 'exit_short', or None
            metadata: dict with relevant info (e.g., stop_loss_price)
        """
        pass

    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame):
        """
        Calculates technical indicators for the strategy.
        """
        pass
