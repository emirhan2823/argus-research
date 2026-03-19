import math
from argus_py.core.exchange_rules import InstrumentRules
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class StopLossResult:
    """Result of ATR-based stop-loss calculation."""
    stop_price: float
    stop_distance: float
    stop_distance_pct: float
    atr_multiplier: float
    method: str  # "ATR" or "FIXED"


class ATRStopCalculator:
    """
    Calculates dynamic stop-loss prices based on ATR (Average True Range).
    
    Benefits over fixed stops:
    - Adapts to market volatility
    - Tighter stops in calm markets = less risk
    - Wider stops in volatile markets = avoids whipsaws
    """
    
    DEFAULT_ATR_MULT = 1.5  # Standard: 1.5x ATR
    MIN_STOP_PCT = 0.005   # Minimum 0.5% stop (floor)
    MAX_STOP_PCT = 0.05    # Maximum 5% stop (cap)
    
    @staticmethod
    def calculate_stop(
        entry_price: float,
        atr: float,
        direction: str,  # "BUY" or "SELL"
        atr_multiplier: float = 1.5,
        min_stop_pct: float = 0.005,
        max_stop_pct: float = 0.05
    ) -> StopLossResult:
        """
        Calculate ATR-based stop-loss price.
        
        Args:
            entry_price: Entry price for the trade
            atr: Current ATR (Average True Range) value
            direction: "BUY" for long, "SELL" for short
            atr_multiplier: Multiplier for ATR (higher = wider stop)
            min_stop_pct: Minimum stop distance as percentage
            max_stop_pct: Maximum stop distance as percentage
            
        Returns:
            StopLossResult with stop price and metadata
        """
        if entry_price <= 0 or atr <= 0:
            # Fallback to fixed percentage if ATR unavailable
            default_pct = 0.02  # 2% default
            stop_dist = entry_price * default_pct
            if direction == "BUY":
                stop_price = entry_price - stop_dist
            else:
                stop_price = entry_price + stop_dist
            return StopLossResult(
                stop_price=stop_price,
                stop_distance=stop_dist,
                stop_distance_pct=default_pct,
                atr_multiplier=0,
                method="FIXED"
            )
        
        # Calculate raw stop distance
        raw_stop_dist = atr * atr_multiplier
        
        # Apply floor and ceiling
        min_dist = entry_price * min_stop_pct
        max_dist = entry_price * max_stop_pct
        
        stop_dist = max(min_dist, min(raw_stop_dist, max_dist))
        stop_pct = stop_dist / entry_price
        
        # Calculate stop price based on direction
        if direction == "BUY":
            stop_price = entry_price - stop_dist
        else:  # SELL (short)
            stop_price = entry_price + stop_dist
            
        return StopLossResult(
            stop_price=stop_price,
            stop_distance=stop_dist,
            stop_distance_pct=stop_pct,
            atr_multiplier=atr_multiplier,
            method="ATR"
        )
    
    @staticmethod
    def calculate_take_profit(
        entry_price: float,
        stop_distance: float,
        direction: str,
        reward_ratio: float = 2.0
    ) -> float:
        """
        Calculate take-profit price based on risk:reward ratio.
        
        Args:
            entry_price: Entry price
            stop_distance: Distance to stop-loss
            direction: "BUY" or "SELL"
            reward_ratio: Minimum risk:reward ratio (default 1:2)
            
        Returns:
            Take-profit price
        """
        tp_distance = stop_distance * reward_ratio
        
        if direction == "BUY":
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance


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
