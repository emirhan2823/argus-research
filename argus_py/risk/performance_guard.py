import numpy as np
from typing import List
from argus_py.broker.paper import TradeFill

class PerformanceGuard:
    """
    Performance-based risk guard with tightened drawdown limits.
    
    Thresholds (Updated for capital preservation):
    - LOCKDOWN: 8% DD (was 15%) - Complete trading halt
    - DEFENSIVE: 5% DD (was 8%) - 50% risk reduction
    """
    
    # Tighter DD thresholds for small accounts
    DD_LOCKDOWN_PCT = 0.08      # 8% (was 15%)
    DD_DEFENSIVE_PCT = 0.05    # 5% (was 8%)
    WIN_RATE_MIN = 0.40        # Minimum win rate before penalty
    LOCKDOWN_DURATION = 30     # Bars (was 20)
    
    def __init__(self):
        self.trades: List[TradeFill] = []
        self.high_water_mark = 0.0
        self.current_dd = 0.0
        self.lockdown_counter = 0
        self.lockdown_duration = self.LOCKDOWN_DURATION
        
    def update(self, equity: float, new_trades: List[TradeFill]):
        # HWM Logic
        if equity > self.high_water_mark:
            self.high_water_mark = equity
            
        if self.high_water_mark > 0:
            self.current_dd = (self.high_water_mark - equity) / self.high_water_mark
        else:
            self.current_dd = 0.0
            
        # Add new closed trades
        for t in new_trades:
            if t.event == "CLOSE":
                self.trades.append(t)
                
        # Lockdown Countdown
        if self.lockdown_counter > 0:
            self.lockdown_counter -= 1

    def get_winrate_20(self) -> float:
        if not self.trades: return 0.0
        last_20 = self.trades[-20:]
        wins = sum(1 for t in last_20 if t.pnl > 0)
        return wins / len(last_20)

    def get_safety_report(self) -> dict:
        wr20 = self.get_winrate_20()
        
        # Default Multiplier
        risk_mod = 1.0
        status = "NORMAL"
        
        # 1. Drawdown Rules (Tightened)
        if self.current_dd > self.DD_LOCKDOWN_PCT:
            # Lockdown at 8% DD
            if self.lockdown_counter == 0:  # Trigger once
                self.lockdown_counter = self.lockdown_duration
            status = "LOCKDOWN"
            risk_mod = 0.0
            
        elif self.current_dd > self.DD_DEFENSIVE_PCT:
            # Defensive at 5% DD
            status = "DEFENSIVE_DD"
            risk_mod = 0.5
            
        # 2. Performance Rules (only if not already locked)
        if status != "LOCKDOWN":
            if len(self.trades) >= 10 and wr20 < self.WIN_RATE_MIN:
                status = f"{status}+POOR_PERF"
                risk_mod = min(risk_mod, 0.5)
                
        # 3. Lockdown Handling
        if self.lockdown_counter > 0:
            status = f"LOCKDOWN({self.lockdown_counter})"
            risk_mod = 0.0
            
        return {
            "status": status,
            "risk_modifier": risk_mod,
            "current_dd": self.current_dd,
            "win_rate_20": wr20,
            "dd_lockdown_threshold": self.DD_LOCKDOWN_PCT,
            "dd_defensive_threshold": self.DD_DEFENSIVE_PCT
        }
