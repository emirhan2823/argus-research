import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.strategies.trend_following import TrendFollowingStrategy
from src.core.risk_manager import RiskManager
from config.settings import INITIAL_CAPITAL, COMMISSION_RATE, SLIPPAGE

class Backtester:
    """
    Simple event-driven backtester.
    """
    def __init__(self, data: pd.DataFrame, strategy, initial_capital=INITIAL_CAPITAL):
        self.data = data
        self.strategy = strategy
        self.risk_manager = RiskManager(initial_balance=initial_capital)
        self.capital = initial_capital
        self.position = None # {'type': 'long'/'short', 'entry_price': float, 'size': float, 'stop_loss': float, 'take_profit': float}
        self.trades = []
        self.equity_curve = []

    def run(self):
        """
        Runs the backtest loop.
        """
        print("Starting Backtest...")

        # Pre-calculate indicators to speed up loop
        self.data = self.strategy.calculate_indicators(self.data)

        for i in range(len(self.data)):
            # Simulate walking through time
            current_slice = self.data.iloc[:i+1]
            current_bar = self.data.iloc[i]
            timestamp = current_bar.name

            # Check for exits if in position
            if self.position:
                self._check_exit(current_bar, timestamp)

            # Check for entries if not in position
            if not self.position:
                signal, metadata = self.strategy.generate_signal(current_slice)
                if signal:
                    self._execute_entry(signal, metadata, timestamp)

            # Record Equity
            current_equity = self.capital
            if self.position:
                # Mark-to-market value
                pnl = (current_bar['close'] - self.position['entry_price']) * self.position['size']
                if self.position['type'] == 'short':
                    pnl = -pnl
                current_equity += pnl

            self.equity_curve.append({'timestamp': timestamp, 'equity': current_equity})
            self.risk_manager.update_balance(current_equity)

        self._generate_report()

    def _execute_entry(self, signal, metadata, timestamp):
        entry_price = metadata['entry_price']
        stop_loss = metadata['stop_loss']
        take_profit = metadata['take_profit']

        # Risk Check
        if not self.risk_manager.check_trade_allowed():
            return

        size = self.risk_manager.calculate_position_size(entry_price, stop_loss, self.capital)

        if size <= 0:
            return

        # Apply Slippage
        if signal == 'buy':
            entry_price *= (1 + SLIPPAGE)
        else:
            entry_price *= (1 - SLIPPAGE)

        cost = size * entry_price * COMMISSION_RATE
        self.capital -= cost

        self.position = {
            'type': 'long' if signal == 'buy' else 'short',
            'entry_price': entry_price,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': timestamp
        }
        # print(f"Entry {signal.upper()} at {entry_price} on {timestamp}")

    def _check_exit(self, current_bar, timestamp):
        if not self.position:
            return

        exit_price = None
        reason = None

        low = current_bar['low']
        high = current_bar['high']
        close = current_bar['close']

        # Check SL/TP
        if self.position['type'] == 'long':
            if low <= self.position['stop_loss']:
                exit_price = self.position['stop_loss'] # Assuming filled at SL
                reason = 'Stop Loss'
            elif high >= self.position['take_profit']:
                exit_price = self.position['take_profit']
                reason = 'Take Profit'
        elif self.position['type'] == 'short':
            if high >= self.position['stop_loss']:
                exit_price = self.position['stop_loss']
                reason = 'Stop Loss'
            elif low <= self.position['take_profit']:
                exit_price = self.position['take_profit']
                reason = 'Take Profit'

        if exit_price:
            self._close_position(exit_price, reason, timestamp)

    def _close_position(self, exit_price, reason, timestamp):
        size = self.position['size']
        entry_price = self.position['entry_price']

        # Calculate PnL
        if self.position['type'] == 'long':
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        # Commission
        commission = exit_price * size * COMMISSION_RATE
        net_pnl = pnl - commission

        self.capital += net_pnl

        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': timestamp,
            'type': self.position['type'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size': size,
            'pnl': net_pnl,
            'reason': reason
        })

        self.position = None
        # print(f"Exit {reason} at {exit_price}. PnL: {net_pnl:.2f}")

    def _generate_report(self):
        df_trades = pd.DataFrame(self.trades)
        if df_trades.empty:
            print("No trades executed.")
            return

        total_return = (self.capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
        win_rate = len(df_trades[df_trades['pnl'] > 0]) / len(df_trades) * 100

        print("\n--- Backtest Report ---")
        print(f"Initial Capital: ${INITIAL_CAPITAL:.2f}")
        print(f"Final Capital:   ${self.capital:.2f}")
        print(f"Total Return:    {total_return:.2f}%")
        print(f"Total Trades:    {len(df_trades)}")
        print(f"Win Rate:        {win_rate:.2f}%")
        print("-----------------------")

if __name__ == "__main__":
    # Test Run with random data if run directly
    dates = pd.date_range(start='2023-01-01', periods=500, freq='4h')
    data = pd.DataFrame({
        'open': np.random.randn(500).cumsum() + 1000,
        'high': np.random.randn(500).cumsum() + 1005,
        'low': np.random.randn(500).cumsum() + 995,
        'close': np.random.randn(500).cumsum() + 1000,
        'volume': np.random.randint(100, 1000, 500)
    }, index=dates)

    # Ensure High is highest and Low is lowest
    data['high'] = data[['open', 'close', 'high']].max(axis=1)
    data['low'] = data[['open', 'close', 'low']].min(axis=1)

    strategy = TrendFollowingStrategy(risk_manager=None) # Risk manager init inside backtester
    bt = Backtester(data, strategy)
    bt.run()
