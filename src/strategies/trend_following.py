import pandas as pd
import pandas_ta as ta
import numpy as np
import sys
import os

# Ensure we can import from src

from src.strategies.base_strategy import BaseStrategy
from config.settings import EMA_SHORT_PERIOD, EMA_LONG_PERIOD, RSI_PERIOD, ATR_PERIOD, ATR_MULTIPLIER_SL, ATR_MULTIPLIER_TP

class TrendFollowingStrategy(BaseStrategy):
    """
    A simple trend-following strategy using EMA Crossovers and RSI filter.
    Designed for 4H/Daily timeframes on Commodities/Indices.
    """
    def __init__(self, risk_manager, genome_params=None):
        super().__init__(risk_manager)
        self.params = {
            'ema_short': EMA_SHORT_PERIOD,
            'ema_long': EMA_LONG_PERIOD,
            'rsi_period': RSI_PERIOD,
            'atr_sl': ATR_MULTIPLIER_SL,
            'atr_tp': ATR_MULTIPLIER_TP,
            'use_rsi': 1
        }
        if genome_params:
            self.update_parameters(genome_params)

    def update_parameters(self, genome_params):
        """Updates strategy parameters from a Darwin Genome."""
        self.params['ema_short'] = int(genome_params.get('ema_short', self.params['ema_short']))
        self.params['ema_long'] = int(genome_params.get('ema_long', self.params['ema_long']))
        self.params['rsi_period'] = int(genome_params.get('rsi_period', self.params['rsi_period']))
        self.params['atr_sl'] = float(genome_params.get('sl_atr_mult', self.params['atr_sl']))
        self.params['atr_tp'] = float(genome_params.get('tp_atr_mult', self.params['atr_tp']))
        self.params['use_rsi'] = int(genome_params.get('use_rsi', 1))

    def calculate_indicators(self, data: pd.DataFrame):
        """
        Adds EMA, RSI, and ATR columns to the dataframe.
        """
        # Ensure sufficient data length
        if len(data) < self.params['ema_long']:
            return data

        data['ema_short'] = ta.ema(data['close'], length=self.params['ema_short'])
        data['ema_long'] = ta.ema(data['close'], length=self.params['ema_long'])
        data['rsi'] = ta.rsi(data['close'], length=self.params['rsi_period'])
        data['atr'] = ta.atr(data['high'], data['low'], data['close'], length=ATR_PERIOD)

        return data

    def generate_signal(self, data: pd.DataFrame):
        """
        Generates buy/sell signals based on the latest candle.
        """
        if len(data) < self.params['ema_long']:
            return None, {}

        current = data.iloc[-1]
        prev = data.iloc[-2]

        signal = None
        metadata = {}

        # Long Entry Conditions
        is_uptrend = current['ema_short'] > current['ema_long']
        # Check for crossover or sustained trend with RSI confirmation
        crossover_long = (prev['ema_short'] <= prev['ema_long']) and (current['ema_short'] > current['ema_long'])

        rsi_condition = True
        if self.params['use_rsi']:
            rsi_condition = (current['rsi'] > 50)

        trend_strong_long = (current['close'] > current['ema_short']) and rsi_condition

        if is_uptrend and (crossover_long or trend_strong_long):
             # Calculate SL and TP
            atr = current['atr']
            stop_loss = current['close'] - (atr * self.params['atr_sl'])
            take_profit = current['close'] + (atr * self.params['atr_tp'])

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

        rsi_condition_short = True
        if self.params['use_rsi']:
            rsi_condition_short = (current['rsi'] < 50)

        trend_strong_short = (current['close'] < current['ema_short']) and rsi_condition_short

        if is_downtrend and (crossover_short or trend_strong_short):
            atr = current['atr']
            stop_loss = current['close'] + (atr * self.params['atr_sl'])
            take_profit = current['close'] - (atr * self.params['atr_tp'])

            signal = 'sell'
            metadata = {
                'entry_price': current['close'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'atr': atr
            }

        return signal, metadata
