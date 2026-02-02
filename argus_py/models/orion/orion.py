from typing import List, Optional
from argus_py.data.market_state import Bar
from argus_py.council.defs import Vote
import pandas as pd
import numpy as np

class OrionEngine:
    """
    Orion Voter: Trend Confirmation.
    Uses ADX(14) for Trend Strength and SMA(50) for Trend Direction.
    """
    
    def __init__(self, adx_period=14, sma_period=50):
        self.adx_period = adx_period
        self.sma_period = sma_period
        
    def calculate(self, history: List[Bar]) -> Optional[Vote]:
        if len(history) < max(self.adx_period, self.sma_period) * 2:
            return Vote("Orion", "FLAT", 0.0, 50.0, ["Insufficient Data"], metadata={"orion_valid": False, "reason": "WARMUP"})
            
        # Optimize: Take last 100 bars
        subset = history[-100:]
        df = pd.DataFrame([vars(b) for b in subset])
        
        # 1. ADX Calculation
        # TR, +DM, -DM
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift(1))
        df['tr2'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        
        # Smooth
        # ADX smoothing is specific (Wilder's). Using EWM as approx or Simple Rolling/Alpha?
        # Standard ADX uses Wilder's Smoothing (alpha = 1/n)
        alpha = 1 / self.adx_period
        
        # Helper for Wilder's
        def wilders(series, n):
            return series.ewm(alpha=1/n, adjust=False).mean()
            
        df['atr'] = wilders(df['tr'], self.adx_period)
        df['plus_di'] = 100 * wilders(df['plus_dm'], self.adx_period) / df['atr']
        df['minus_di'] = 100 * wilders(df['minus_dm'], self.adx_period) / df['atr']
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = wilders(df['dx'], self.adx_period)
        
        # 2. SMA
        df['sma'] = df['close'].rolling(window=self.sma_period).mean()
        
        last = df.iloc[-1]
        
        # Logic
        adx = last['adx']
        price = last['close']
        sma = last['sma']
        
        direction = "FLAT"
        confidence = 0.0
        
        # Trend Filter
        if adx > 25:
            # Strong Trend
            if price > sma:
                direction = "LONG"
                confidence = min(1.0, (adx - 20) / 40.0) # Scale confidence with ADX strength
            elif price < sma:
                direction = "SHORT"
                confidence = min(1.0, (adx - 20) / 40.0)
        else:
            # Weak Signal
            confidence = 0.2
            if price > sma: direction = "LONG"
            else: direction = "SHORT"
            
        score = 50 + (confidence * 50 if direction == "LONG" else -confidence * 50)
        
        meta = {
            "orion_valid": True,
            "adx": adx,
            "atr": last['atr'],
            "sma_dist": (price - sma) / sma if sma else 0.0,
            "trend_active": adx > 25
        }
        
        return Vote(
            module="Orion",
            direction=direction,
            confidence=confidence,
            score=score,
            reasons=[f"ADX={adx:.1f}", f"Price vs SMA: {'Above' if price > sma else 'Below'}"],
            metadata=meta
        )
