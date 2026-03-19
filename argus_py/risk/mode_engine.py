from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple
from argus_py.broker.paper import TradeFill

class RiskMode(Enum):
    SAFE = "SAFE"
    NORMAL = "NORMAL"
    AGGRESSIVE = "AGGRESSIVE"
    COOLDOWN = "COOLDOWN"

class RiskProfile(Enum):
    DEGEN = "DEGEN"         # < $100 (High Risk)
    BALANCED = "BALANCED"   # $100 - $1000
    DEFENSIVE = "DEFENSIVE" # > $1000
    AUTO = "AUTO"

@dataclass
class ModeSnapshot:
    mode: RiskMode
    profile: RiskProfile
    risk_multiplier: float
    leverage_allowed: float
    reason: str
    can_trade: bool

class ModeEngine:
    def __init__(self, max_daily_dd_pct=0.02, max_total_dd_pct=0.06, profile_override: str = "AUTO"):
        self.mode = RiskMode.NORMAL
        self.max_daily_dd = max_daily_dd_pct
        self.max_total_dd = max_total_dd_pct
        self.high_water_mark = 0.0
        self.consecutive_losses = 0
        self.cooldown_counter = 0
        self.cooldown_duration = 5 
        self.reason = "Startup"
        self.profile_override = profile_override

    def update(self, equity: float, daily_start_equity: float, trades: List[TradeFill], regime: str, conviction: float = 0.0) -> ModeSnapshot:
        # Update HWM
        if equity > self.high_water_mark:
            self.high_water_mark = equity

        # Calculate Drawdowns
        daily_dd = (daily_start_equity - equity) / daily_start_equity
        total_dd = (self.high_water_mark - equity) / self.high_water_mark if self.high_water_mark > 0 else 0

        # Update Streak
        self._update_streak(trades)

        # Determine Capital Risk Profile
        profile = RiskProfile.BALANCED # Default
        if self.profile_override != "AUTO":
             try:
                 profile = RiskProfile(self.profile_override)
             except ValueError:
                 profile = RiskProfile.BALANCED
        else:
            if equity >= 1000:
                profile = RiskProfile.DEFENSIVE
            elif equity < 100:
                profile = RiskProfile.DEGEN
            
        # 1. Critical Safety Triggers
        # Override for DEGEN: looser stops? Or strict daily cut?
        # Prompt: "DEGEN... hard daily loss cut"
        
        effective_max_dd = self.max_daily_dd
        if profile == RiskProfile.DEGEN:
            effective_max_dd = 0.05 # 5% daily stop for DEGEN
        
        if total_dd > self.max_total_dd:
            self.mode = RiskMode.SAFE 
            self.cooldown_counter = self.cooldown_duration
            self.mode = RiskMode.COOLDOWN
            self.reason = f"Max Total DD Hit: {total_dd:.1%}"
            return self._snapshot(profile)

        if daily_dd > effective_max_dd:
            self.mode = RiskMode.SAFE
            self.reason = f"Max Daily DD Hit: {daily_dd:.1%}"
            return self._snapshot(profile)

        # 2. Cooldown Logic
        if self.mode == RiskMode.COOLDOWN:
            self.cooldown_counter -= 1
            if self.cooldown_counter <= 0:
                self.mode = RiskMode.SAFE
                self.reason = "Cooldown Expired -> SAFE"
            else:
                self.reason = f"Cooldown: {self.cooldown_counter} bars"
            return self._snapshot(profile)

        # 3. Streak Logic
        if self.consecutive_losses >= 2:
            self.mode = RiskMode.SAFE
            self.reason = f"Consecutive Losses: {self.consecutive_losses}"
            return self._snapshot(profile)

        # 4. Regime Promotion/Demotion
        last_2_wins = False
        closed_trades = [t for t in trades if t.event == "CLOSE"]
        if len(closed_trades) >= 2:
            if closed_trades[-1].pnl > 0 and closed_trades[-2].pnl > 0:
                last_2_wins = True

        if regime == "TREND" and last_2_wins:
            self.mode = RiskMode.AGGRESSIVE
            self.reason = "Trend & Momentum (2 wins)"
        else:
            self.mode = RiskMode.NORMAL
            self.reason = "Normal Operation"
            
        # Smart Leverage Logic
        # Rules:
        # DEFENSIVE: 1x
        # BALANCED: 1x, unless Trend+Conviction>0.8 -> 2x
        # DEGEN: 1x, unless Trend+Conviction>0.6 -> 3x (Example)
        # CHOP ALWAYS 1.0x
        
        self.leverage_cap = 1.0
        
        if regime == "CHOP":
             self.leverage_cap = 1.0 # Force 1x in Chop
        else:
             if profile == RiskProfile.DEFENSIVE:
                 self.leverage_cap = 1.0
                 
             elif profile == RiskProfile.BALANCED:
                 if conviction > 0.8 and regime == "TREND" and total_dd < 0.01:
                     self.leverage_cap = 2.0
                     self.reason += " + Smart Lev 2x"
                     
             elif profile == RiskProfile.DEGEN:
                 # Aggressive leverage
                 if conviction > 0.6 and regime == "TREND":
                     self.leverage_cap = 3.0
                     self.reason += " + Degen Lev 3x"

        return self._snapshot(profile)

    def _update_streak(self, trades: List[TradeFill]):
        # Analyze last closed trades to count consecutive losses
        streak = 0
        closed = [t for t in trades if t.event == "CLOSE"]
        for t in reversed(closed):
            if t.pnl < 0:
                streak += 1
            else:
                break
        self.consecutive_losses = streak

    def _snapshot(self, profile: RiskProfile) -> ModeSnapshot:
        mult = 1.0
        can_trade = True
        
        # Base Multiplier by Profile
        if profile == RiskProfile.DEGEN:
            mult = 1.5 
        elif profile == RiskProfile.DEFENSIVE:
            mult = 0.5
            
        # Mode Modifier
        if self.mode == RiskMode.SAFE:
            mult *= 0.5
        elif self.mode == RiskMode.AGGRESSIVE:
            mult *= 1.5 
        elif self.mode == RiskMode.COOLDOWN:
            mult = 0.0
            can_trade = False
        
        # Leverage check
        lev = 1.0
        if can_trade:
             lev = getattr(self, 'leverage_cap', 1.0)
            
        return ModeSnapshot(
            mode=self.mode,
            profile=profile,
            risk_multiplier=mult,
            leverage_allowed=lev,
            reason=self.reason,
            can_trade=can_trade
        )
