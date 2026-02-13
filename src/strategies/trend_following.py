import pandas as pd
import pandas_ta as ta
import numpy as np
import sys
import os

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.strategies.base_strategy import BaseStrategy
from config.settings import EMA_SHORT_PERIOD, EMA_LONG_PERIOD, RSI_PERIOD, ATR_PERIOD, ATR_MULTIPLIER_SL, ATR_MULTIPLIER_TP

class TrendFollowingStrategy(BaseStrategy):
    """
    A simple trend-following strategy using EMA Crossovers and RSI filter.
    Designed for 4H/Daily timeframes on Commodities/Indices.
    """

    def calculate_indicators(self, data: pd.DataFrame):
        """
        Adds EMA, RSI, and ATR columns to the dataframe.
        """
        # Ensure sufficient data length
        if len(data) < EMA_LONG_PERIOD:
            return data

        data['ema_short'] = ta.ema(data['close'], length=EMA_SHORT_PERIOD)
        data['ema_long'] = ta.ema(data['close'], length=EMA_LONG_PERIOD)
        data['rsi'] = ta.rsi(data['close'], length=RSI_PERIOD)
        data['atr'] = ta.atr(data['high'], data['low'], data['close'], length=ATR_PERIOD)

        return data

    def generate_signal(self, data: pd.DataFrame):
        """
        Generates buy/sell signals based on the latest candle.
        """
        if len(data) < EMA_LONG_PERIOD:
            return None, {}

        current = data.iloc[-1]
        prev = data.iloc[-2]

        signal = None
        metadata = {}

        # Long Entry Conditions
        is_uptrend = current['ema_short'] > current['ema_long']
        # Check for crossover or sustained trend with RSI confirmation
        crossover_long = (prev['ema_short'] <= prev['ema_long']) and (current['ema_short'] > current['ema_long'])
        trend_strong_long = (current['close'] > current['ema_short']) and (current['rsi'] > 50)

        if is_uptrend and (crossover_long or trend_strong_long):
             # Calculate SL and TP
            atr = current['atr']
            stop_loss = current['close'] - (atr * ATR_MULTIPLIER_SL)
            take_profit = current['close'] + (atr * ATR_MULTIPLIER_TP)

            signal = 'buy'
            metadata = {
                'entry_price': current['close'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'atr': atr
            }

        # Short Entry Conditions
        is_downtrend = current['ema_short'] < current['ema_long']
        crossover_short = (prev['ema_short'] >= prev['ema_long']) and (current['ema_short'] < current['ema_long'])
        trend_strong_short = (current['close'] < current['ema_short']) and (current['rsi'] < 50)

        if is_downtrend and (crossover_short or trend_strong_short):
            atr = current['atr']
            stop_loss = current['close'] + (atr * ATR_MULTIPLIER_SL)
            take_profit = current['close'] - (atr * ATR_MULTIPLIER_TP)

            signal = 'sell'
            metadata = {
                'entry_price': current['close'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'atr': atr
            }

        return signal, metadata
