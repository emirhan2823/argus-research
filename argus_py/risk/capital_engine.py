from enum import Enum
from dataclasses import dataclass
from typing import List

class CapitalProfileType(Enum):
    SMALL = "SMALL"       # < $100
    GROWTH = "GROWTH"     # $100 - $1,000
    SCALE = "SCALE"       # $1,000 - $10,000
    PRO = "PRO"           # > $10,000

@dataclass
class CapitalConfig:
    profile: CapitalProfileType
    max_risk_per_trade: float
    max_daily_loss: float
    leverage_cap: float
    council_threshold: float
    description: str

class CapitalEngine:
    def __init__(self):
        pass

    def get_config(self, equity: float, profile_override: str = None) -> CapitalConfig:
        if profile_override == "SMALL": equity = 50
        elif profile_override == "GROWTH": equity = 500
        elif profile_override == "SCALE": equity = 5000
        
        if equity < 100:
            return CapitalConfig(
                profile=CapitalProfileType.SMALL,
                max_risk_per_trade=0.02,
                max_daily_loss=0.04,
                leverage_cap=1.0, # Small accounts: 1x to avoid notional cap conflicts
                council_threshold=0.5, # Higher conviction needed
                description="Survival Mode. Lev 1x. Focus on Compounding."
            )
        elif equity < 1000:
            return CapitalConfig(
                profile=CapitalProfileType.GROWTH,
                max_risk_per_trade=0.015,
                max_daily_loss=0.03,
                leverage_cap=2.0,
                council_threshold=0.4,
                description="Balanced Growth. Lev <= 2x."
            )
        elif equity < 10000:
            return CapitalConfig(
                profile=CapitalProfileType.SCALE,
                max_risk_per_trade=0.01,
                max_daily_loss=0.025,
                leverage_cap=3.0, # More room but tighter risk %
                council_threshold=0.4,
                description="Scaling. Defensive Bias."
            )
        else: # PRO
             return CapitalConfig(
                profile=CapitalProfileType.PRO,
                max_risk_per_trade=0.005, # Capital preservation
                max_daily_loss=0.015,
                leverage_cap=3.0, # Adaptive (managed elsewhere)
                council_threshold=0.35, # Aggressive entry allowed but tiny risk
                description="Pro Mode. Kelly-informed. Preservation first."
            )
