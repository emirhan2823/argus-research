from typing import List, Optional
from argus_py.data.market_state import Bar
from argus_py.council.defs import Vote
import pandas as pd
import numpy as np

class AegeanEngine:
    """
    Aegean Indicator Logic (Real Pandas Implementation)
    Components:
    1. Slope: Rate of change of EMA(20).
    2. Position: %Rank in Donchian Channel(20).
    """
    
    def __init__(self, ema_period=20, channel_period=20):
        self.ema_period = ema_period
        self.channel_period = channel_period
        
    def calculate(self, history: List[Bar]) -> Optional[Vote]:
        if len(history) < self.channel_period + 5:
            return Vote("Aegean", "FLAT", 0.0, 50.0, ["Insufficient Data"], metadata={"aegean_valid": False, "reason": "WARMUP"})
            
        lookback = max(self.ema_period, self.channel_period) * 2
        subset = history[-lookback:]
        
        df = pd.DataFrame([vars(b) for b in subset])
        
        # 1. EMA
        df['ema'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()
        
        # 2. Slope 
        df['slope'] = df['ema'].diff()
        
        # 3. Channel
        df['hh'] = df['high'].rolling(window=self.channel_period).max()
        df['ll'] = df['low'].rolling(window=self.channel_period).min()
        
        last = df.iloc[-1]
        
        # Logic
        slope_val = last['slope']
        slope_dir = "FLAT"
        
        # Adaptive Threshold (0.01% of price)
        threshold = 0.0001 * last['close']
        
        if slope_val > threshold: slope_dir = "UP"
        elif slope_val < -threshold: slope_dir = "DOWN"
        
        hh = last['hh']
        ll = last['ll']
        close = last['close']
        
        if hh == ll:
            pos = 0.5
        else:
            pos = (close - ll) / (hh - ll)
            
        zone = "MID"
        if pos > 0.85: zone = "TOP"
        elif pos < 0.15: zone = "DIP"
        
        # Vote Synthesis
        direction = "FLAT"
        confidence = 0.5
        reasons = [f"Slope:{slope_dir}", f"Zone:{zone}", f"Pos:{pos:.2f}"]
        
        if slope_dir == "UP":
            if zone == "TOP": 
                direction = "FLAT" # Caution
                reasons.append("Bullish but Top Zone")
                confidence = 0.3
            else:
                direction = "LONG"
                confidence = 0.8 if zone == "DIP" else 0.7
                
        elif slope_dir == "DOWN":
            if zone == "DIP":
                direction = "FLAT"
                reasons.append("Bearish but Dip Zone")
                confidence = 0.3
            else:
                direction = "SHORT"
                confidence = 0.8 if zone == "TOP" else 0.7
                
        score = 50 + (confidence * 50 if direction == "LONG" else -confidence * 50)
        if direction == "SHORT": score = 50 - (confidence * 50)
        
        meta = {
            "aegean_valid": True,
            "slope": slope_val,
            "zone": zone,
            "pos": pos
        }
        
        return Vote("Aegean", direction, confidence, score, reasons, meta)
