import math
from argus_py.core.exchange_rules import InstrumentRules

class PositionSizer:
    """
    Calculates safe position size based on risk percentage and stop loss distance.
    Enforces exchange rules (Min Notional, Min Qty).
    """
    
    @staticmethod
    def calculate_qty(
        equity: float, 
        risk_pct: float, 
        entry_price: float, 
        sl_price: float, 
        rules: InstrumentRules
    ) -> float:
        
        if equity <= 0: return 0.0
        
        # 1. Risk Amount
        risk_amt = equity * risk_pct
        
        # 2. Risk per Unit
        risk_per_unit = abs(entry_price - sl_price)
        if risk_per_unit == 0: return 0.0
        
        # 3. Raw Qty
        raw_qty = risk_amt / risk_per_unit
        
        # 4. Filter: Max Leverage (Implicit 1x cap for P0 unless Sniper mode)
        # Low capital survival -> 1x cap is safest
        max_qty_1x = equity / entry_price
        # Let's cap at 0.98x to leave room for fees
        qty = min(raw_qty, max_qty_1x * 0.98)
        
        # 5. Apply Exchange Rules
        # Min Qty
        if qty < rules.min_qty:
            return 0.0
            
        # Step Size Rounding
        if not rules.allow_fractional:
            steps = math.floor(qty / rules.step_size)
            qty = steps * rules.step_size
        
        # Min Notional
        notional = qty * entry_price
        if notional < rules.min_notional:
            return 0.0
            
        return qty
