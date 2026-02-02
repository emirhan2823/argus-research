import numpy as np
from typing import List
from argus_py.broker.paper import TradeFill

class PerformanceGuard:
    def __init__(self):
        self.trades: List[TradeFill] = []
        self.high_water_mark = 0.0
        self.current_dd = 0.0
        self.lockdown_counter = 0
        self.lockdown_duration = 20 # Bars
        
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
        
        # 1. Drawdown Rules
        if self.current_dd > 0.15:
            # Lockdown
            if self.lockdown_counter == 0: # Trigger once
                 self.lockdown_counter = self.lockdown_duration
            status = "LOCKDOWN"
            risk_mod = 0.0
            
        elif self.current_dd > 0.08:
            status = "DEFENSIVE_DD"
            risk_mod = 0.5
            
        # 2. Performance Rules (only if not already locked)
        if status != "LOCKDOWN":
            if len(self.trades) >= 10 and wr20 < 0.40:
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
            "win_rate_20": wr20
        }
