from enum import Enum
from dataclasses import dataclass

class RiskState(Enum):
    NORMAL = "NORMAL"
    COOLDOWN = "COOLDOWN"
    SAFE = "SAFE"

@dataclass
class RiskSnapshot:
    state: RiskState
    reason: str
    can_trade: bool

class RiskStateMachine:
    def __init__(self, max_daily_dd_pct=0.06, cooldown_on_consecutive_losses=3):
        self.state = RiskState.NORMAL
        self.reason = "Startup"
        self.max_dd_pct = max_daily_dd_pct
        self.cooldown_limit = cooldown_on_consecutive_losses
        self.consecutive_losses = 0
        self.high_water_mark = 0.0

    def update(self, current_equity: float, daily_start_equity: float) -> RiskSnapshot:
        # Update HWM
        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity
            
        # 1. Check SAFE Condition (Hard Stop)
        daily_dd = (daily_start_equity - current_equity) / daily_start_equity
        if daily_dd > self.max_dd_pct:
            self.state = RiskState.SAFE
            self.reason = f"Max Daily DD Hit: {daily_dd*100:.2f}% > {self.max_dd_pct*100}%"
            return self._snapshot()
            
        # 2. Check Cooldown
        if self.state == RiskState.NORMAL:
            if self.consecutive_losses >= self.cooldown_limit:
                 self.state = RiskState.COOLDOWN
                 self.reason = f"Consecutive Losses: {self.consecutive_losses}"
        
        # 3. Recovery from Cooldown? (Simplified: Manual reset or time based usually. For P0, stick.)
        
        return self._snapshot()

    def record_trade(self, pnl: float):
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            # If in Cooldown and we get a win (impossible usually as we don't trade),
            # but usually we reset cooldown after N bars. 
            # For P0, lets say we auto-reset if manual override or time passed.
            # We'll need a 'reset_cooldown()' method called by Runner after N bars.
            if self.state == RiskState.COOLDOWN:
                self.state = RiskState.NORMAL
                self.reason = "Win reset"

    def reset_cooldown(self):
        if self.state == RiskState.COOLDOWN:
            self.state = RiskState.NORMAL
            self.consecutive_losses = 0
            self.reason = "Cooldown Expired"

    def _snapshot(self):
        return RiskSnapshot(
            state=self.state,
            reason=self.reason,
            can_trade=(self.state == RiskState.NORMAL)
        )
