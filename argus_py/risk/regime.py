from typing import List, Tuple
from argus_py.data.market_state import Bar
import pandas as pd
import numpy as np

class RegimeDetector:
    """
    Detects Market Regime: TREND (Risk ON) vs CHOP (Risk Filter).
    Logic:
    - TREND: ADX > 25 (High directional movement)
    - CHOP: ADX < 20 or High Volatility w/o Direction
    """
    
    def __init__(self, adx_period=14):
        self.adx_period = adx_period
        
    def detect(self, history: List[Bar]) -> str:
        # Default fallback
        if len(history) < 50: return "CHOP"
        
        # Optimize: reuse DataFrame logic? In production we should have a shared Analysis Service
        # For P2 Parity, simple recalc inside component
        subset = history[-50:]
        df = pd.DataFrame([vars(b) for b in subset])
        
        # ADX Calc (Simplified reused from Orion logic - ideally modularized in core/indicators.py)
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift(1))
        df['tr2'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        
        def wilders(series, n):
            return series.ewm(alpha=1/n, adjust=False).mean()
            
        df['atr'] = wilders(df['tr'], self.adx_period)
        df['plus_di'] = 100 * wilders(df['plus_dm'], self.adx_period) / df['atr']
        df['minus_di'] = 100 * wilders(df['minus_dm'], self.adx_period) / df['atr']
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = wilders(df['dx'], self.adx_period)
        
        adx = df.iloc[-1]['adx']
        
        # Heuristic
        if adx > 25:
            return "TREND"
        else:
            return "CHOP"
