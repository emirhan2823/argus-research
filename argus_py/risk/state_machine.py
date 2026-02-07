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
    cooldown_bars_remaining: int = 0
    consecutive_losses: int = 0

class RiskStateMachine:
    """
    Risk state machine with progressive cooldown system.
    
    Progressive Cooldown (for capital preservation):
    - 1 loss: 5 bars wait
    - 2 consecutive losses: 15 bars wait
    - 3+ consecutive losses: 50 bars wait (until day end effectively)
    
    States:
    - NORMAL: Can trade freely
    - COOLDOWN: Waiting period after losses
    - SAFE: Hard stop hit, no trading until manual reset
    """
    
    # Progressive cooldown configuration
    COOLDOWN_1_LOSS = 5      # Bars after 1 loss
    COOLDOWN_2_LOSS = 15     # Bars after 2 consecutive losses
    COOLDOWN_3_PLUS = 50     # Bars after 3+ consecutive losses
    
    # Tighter DD limits
    DEFAULT_MAX_DAILY_DD = 0.05   # 5% (was 6%)
    DEFAULT_MAX_TOTAL_DD = 0.08   # 8% (was 10%)
    
    def __init__(self, max_daily_dd_pct=0.05, cooldown_on_consecutive_losses=2):
        self.state = RiskState.NORMAL
        self.reason = "Startup"
        self.max_dd_pct = max_daily_dd_pct
        self.cooldown_limit = cooldown_on_consecutive_losses
        self.consecutive_losses = 0
        self.high_water_mark = 0.0
        self.cooldown_bars_remaining = 0

    def update(self, current_equity: float, daily_start_equity: float) -> RiskSnapshot:
        # Update HWM
        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity
        
        # Decrement cooldown
        if self.cooldown_bars_remaining > 0:
            self.cooldown_bars_remaining -= 1
            if self.cooldown_bars_remaining == 0 and self.state == RiskState.COOLDOWN:
                self.state = RiskState.NORMAL
                self.reason = "Cooldown expired"
            
        # 1. Check SAFE Condition (Hard Stop)
        daily_dd = (daily_start_equity - current_equity) / daily_start_equity if daily_start_equity > 0 else 0
        if daily_dd > self.max_dd_pct:
            self.state = RiskState.SAFE
            self.reason = f"Max Daily DD Hit: {daily_dd*100:.2f}% > {self.max_dd_pct*100}%"
            return self._snapshot()
            
        # 2. Cooldown state check
        if self.cooldown_bars_remaining > 0:
            self.state = RiskState.COOLDOWN
            self.reason = f"Cooldown: {self.cooldown_bars_remaining} bars ({self.consecutive_losses} losses)"
        
        return self._snapshot()

    def record_trade(self, pnl: float):
        """Record a trade result and update cooldown state."""
        if pnl < 0:
            self.consecutive_losses += 1
            
            # Calculate progressive cooldown
            cooldown_bars = self._calculate_cooldown()
            self.cooldown_bars_remaining = cooldown_bars
            self.state = RiskState.COOLDOWN
            self.reason = f"Loss #{self.consecutive_losses} - {cooldown_bars} bar cooldown"
        else:
            # Win resets consecutive losses
            self.consecutive_losses = 0
            self.cooldown_bars_remaining = 0
            if self.state == RiskState.COOLDOWN:
                self.state = RiskState.NORMAL
                self.reason = "Win reset"
                
    def _calculate_cooldown(self) -> int:
        """Calculate progressive cooldown based on consecutive losses."""
        if self.consecutive_losses >= 3:
            return self.COOLDOWN_3_PLUS  # 50 bars
        elif self.consecutive_losses == 2:
            return self.COOLDOWN_2_LOSS  # 15 bars
        else:
            return self.COOLDOWN_1_LOSS  # 5 bars

    def reset_cooldown(self):
        """Manual reset of cooldown state."""
        if self.state == RiskState.COOLDOWN:
            self.state = RiskState.NORMAL
            self.consecutive_losses = 0
            self.cooldown_bars_remaining = 0
            self.reason = "Manual reset"
            
    def reset_safe_mode(self):
        """Reset from SAFE mode (requires manual intervention)."""
        if self.state == RiskState.SAFE:
            self.state = RiskState.NORMAL
            self.consecutive_losses = 0
            self.cooldown_bars_remaining = 0
            self.reason = "Safe mode reset"

    def _snapshot(self):
        return RiskSnapshot(
            state=self.state,
            reason=self.reason,
            can_trade=(self.state == RiskState.NORMAL),
            cooldown_bars_remaining=self.cooldown_bars_remaining,
            consecutive_losses=self.consecutive_losses
        )
