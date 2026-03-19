
import numpy as np
from typing import List, Dict, Any

class MRIE:
    """
    Market Regime Intelligence Engine (MRIE)
    Computes ShiftScore (0..1) based on Volatility, Trend Exhaustion, and Pattern Traps.
    Passive module - does not make trading decisions directly.
    """
    def __init__(self, atr_window=20, vol_window=20, high_low_window=20):
        self.atr_window = atr_window
        self.vol_window = vol_window
        self.hl_window = high_low_window
        
        # State
        self.atr_history = []
        self.vol_history = []
        self.adx_history = [] # Keep last few for flip detection
        self.highs = []
        self.lows = []
        
    def update(self, atr: float, vol: float, adx: float, high: float, low: float, close: float) -> Dict[str, Any]:
        """
        Updates internal state and returns calculated features for the current bar.
        """
        # 1. Update State
        if atr > 0: self.atr_history.append(atr)
        if vol >= 0: self.vol_history.append(vol) # Vol can be 0, allow it
        self.adx_history.append(adx)
        self.highs.append(high)
        self.lows.append(low)
        
        # Trim Windows
        if len(self.atr_history) > self.atr_window + 5: self.atr_history = self.atr_history[-self.atr_window:]
        if len(self.vol_history) > self.vol_window + 5: self.vol_history = self.vol_history[-self.vol_window:]
        if len(self.adx_history) > 5: self.adx_history = self.adx_history[-5:]
        if len(self.highs) > self.hl_window + 5: self.highs = self.highs[-self.hl_window:]
        if len(self.lows) > self.hl_window + 5: self.lows = self.lows[-self.hl_window:]
        
        # 2. Compute Features
        features = {
            "atr_ratio": 0.0,
            "atr_spike": 0,
            "vol_ratio": 0.0,
            "vol_spike": 0,
            "vol_missing": 0,
            "adx_flip": 0,
            "fake_break": 0,
            "shift_score": 0.0,
            "mode_suggest": "ATTACK"
        }
        
        # A. ATR Spike
        if len(self.atr_history) >= 10:
            past_atr = self.atr_history[:-1]
            if past_atr:
                avg_atr = sum(past_atr[-self.atr_window:]) / len(past_atr[-self.atr_window:])
                if avg_atr > 0:
                    features["atr_ratio"] = atr / avg_atr
                    if features["atr_ratio"] > 1.5:
                        features["atr_spike"] = 1
        
        # B. Vol Spike
        if vol is None or vol < 0:
            features["vol_missing"] = 1
            features["vol_ratio"] = float('nan')
        else:
            if len(self.vol_history) >= 10:
                past_vol = self.vol_history[:-1]
                if past_vol:
                    avg_vol = sum(past_vol[-self.vol_window:]) / len(past_vol[-self.vol_window:])
                    if avg_vol > 0:
                        features["vol_ratio"] = vol / avg_vol
                        if features["vol_ratio"] > 2.0:
                            features["vol_spike"] = 1
                    else:
                         # Avg vol is 0 (flatline?)
                         features["vol_ratio"] = 0.0
            else:
                # Not enough history
                features["vol_ratio"] = 0.0
                        
        # C. ADX Flip
        # Rule: (Prev < 20 & Now > 25) OR (Prev > 30 & Now < 25)
        if len(self.adx_history) >= 2:
            prev = self.adx_history[-2]
            curr = self.adx_history[-1]
            features["adx_prev"] = prev
            features["adx_now"] = curr
            
            # Strengthening Flip (Quiet -> Trend)
            if prev < 20 and curr > 25:
                features["adx_flip"] = 1
            # Exhaustion Flip (Strong -> Weak)
            elif prev > 30 and curr < 25:
                features["adx_flip"] = 1
                
        # D. Fake Break (Bull/Bear Trap)
        # Needs High/Low context.
        # Logic: Did we break a recent N-high recently (1-3 bars ago) and now close below it?
        # Robust basic impl:
        # Check High(20) of *previous* bar (excluding current).
        # If High[current] > High(20)[prev] AND Close[current] < High(20)[prev] -> Potential Fake Break (Wick)
        # Actually proper trap:
        # Day T-1 or T-2 broke N-High.
        # Day T closes back inside range.
        # Let's verify "Current Close < Recent Resistance" where "Recent Resistance was broken recently".
        
        # Simple Proxy: Reversion after Breakout
        # 1. Recent Box High (excluding current)
        if len(self.highs) >= self.hl_window:
            recent_highs = self.highs[:-1]
            recent_lows = self.lows[:-1]
            
            box_high = max(recent_highs[-self.hl_window:])
            box_low = min(recent_lows[-self.hl_window:])
            
            # Did we trade outside box today?
            broke_high = high > box_high
            broke_low = low < box_low
            
            # Did we close inside box?
            closed_in = (close < box_high) and (close > box_low)
            
            if broke_high and closed_in:
                # Bull Trap / Rejection
                features["fake_break"] = 1
            elif broke_low and closed_in:
                # Bear Trap / Rejection
                features["fake_break"] = 1
                
        # 3. Compute Shift Score
        # Simple weighted sum
        # Weights: ATR(0.25), Vol(0.25), Flip(0.25), Fake(0.25)
        raw_sum = features["atr_spike"] + features["vol_spike"] + features["adx_flip"] + features["fake_break"]
        features["shift_score"] = min(1.0, raw_sum * 0.25)
        
        # 4. Mode Suggestion
        score = features["shift_score"]
        if score < 0.3:
            features["mode_suggest"] = "ATTACK"
        elif score < 0.6:
            features["mode_suggest"] = "CAUTION"
        else:
            features["mode_suggest"] = "DEFENSE"
            
        return features
