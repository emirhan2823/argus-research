from dataclasses import dataclass
from typing import Dict

@dataclass
class InstrumentRules:
    symbol: str
    min_notional: float
    min_qty: float
    step_size: float
    tick_size: float
    maker_fee: float
    taker_fee: float
    allow_fractional: bool = False # If True, step_size is ignored/relaxed

class ExchangeConfig:
    """
    Central repository for exchange rules.
    LIVE mode: Strict Binance rules.
    PAPER/BACKTEST mode: Relaxed rules for functionality testing.
    """
    
    @staticmethod
    def get_rules(symbol: str, mode: str = "live") -> InstrumentRules:
        is_sim = mode in ["backtest", "paper"]
        
        # Defaults for BTCUSDT
        # Live: Min Notional $5, Step 0.00001
        # Sim: Min Notional $1 (for $30 accts), Step 1e-8
        
        base_min_notional = 5.0 if not is_sim else 0.5 # Allow tiny trades in sim
        base_min_qty = 0.00001 if not is_sim else 0.00000001
        step_size = 0.00001 if not is_sim else 0.00000001
        
        return InstrumentRules(
            symbol=symbol,
            min_notional=base_min_notional,
            min_qty=base_min_qty,
            step_size=step_size,
            tick_size=0.01,
            maker_fee=0.001,
            taker_fee=0.001,
            allow_fractional=is_sim
        )
