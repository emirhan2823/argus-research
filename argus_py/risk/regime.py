from typing import List, Tuple
from argus_py.data.market_state import Bar
import pandas as pd
import numpy as np

class RegimeDetector:
    """
    Detects Market Regime: TREND (Risk ON) vs CHOP (Risk Filter).
    
    Tightened thresholds for better signal quality:
    - TREND: ADX > 28 (was 25) - only strong trends
    - CHOP: ADX < 22 (was 20) - more conservative chop detection
    - UNCERTAIN: 22 <= ADX <= 28 - treat as CHOP for safety
    """
    
    # Tightened thresholds
    ADX_TREND_THRESHOLD = 28    # Was 25
    ADX_CHOP_THRESHOLD = 22     # Was 20
    MIN_BARS_REQUIRED = 50      # Minimum history
    
    def __init__(self, adx_period=14):
        self.adx_period = adx_period
        
    def detect(self, history: List[Bar]) -> str:
        # Default fallback
        if len(history) < self.MIN_BARS_REQUIRED:
            return "CHOP"
        
        subset = history[-50:]
        df = pd.DataFrame([vars(b) for b in subset])
        
        # ADX Calc
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
        
        # Tightened heuristic - only trade in strong trends
        if adx > self.ADX_TREND_THRESHOLD:
            return "TREND"
        else:
            # Both CHOP and UNCERTAIN zones → conservative CHOP
            return "CHOP"
    
    def detect_detailed(self, history: List[Bar]) -> Tuple[str, float]:
        """
        Returns regime with ADX value for debugging.
        """
        if len(history) < self.MIN_BARS_REQUIRED:
            return ("CHOP", 0.0)
            
        subset = history[-50:]
        df = pd.DataFrame([vars(b) for b in subset])
        
        # Same ADX calculation
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
        regime = "TREND" if adx > self.ADX_TREND_THRESHOLD else "CHOP"
        
        return (regime, adx)
