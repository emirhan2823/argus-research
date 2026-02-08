from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from argus_py.core.exchange_rules import ExchangeConfig
from argus_py.risk.sizing import PositionSizer
from argus_py.broker.realism import (
    FeeModel,
    RealismConfig,
    RealismEngine,
    SlippageModel,
)

import uuid

@dataclass
class Position:
    symbol: str
    side: str # BUY, SELL
    entry_price: float
    quantity: float
    position_id: str
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    creation_time: float = 0
    highest_price: float = 0.0 
    lowest_price: float = 0.0 
    bars_held: int = 0

    def __post_init__(self):
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price

@dataclass
class TradeFill:
    timestamp: float
    symbol: str
    side: str
    price: float # This is the Executed Price (FillPrice)
    quantity: float
    commission: float
    pnl: float = 0.0
    position_id: str = ""
    event: str = "row" # OPEN, CLOSE
    
    # Diagnostics Fields
    mark_price: float = 0.0
    fill_price: float = 0.0 # Repeated for clarity, or just rely on 'price'
    # Actually, let's store MarkPrice explicitly. 'price' is typically Fill Price.
    # We will log 'MarkPrice' (bar close) separately.
    slip_applied: float = 0.0 # bps
    spread_applied: float = 0.0 # bps

@dataclass
class AccountState:
    timestamp: float
    equity: float
    balance: float
    unrealized_pnl: float
    open_quantity: float
    snapshot_type: str = "BAR"

class PaperBroker:
    def __init__(self, start_balance: float = 1000.0, mode="paper", exit_policy="FIXED_BRACKET", reporter=None, realism_config: Dict = None):
        self.balance = start_balance
        self.equity = start_balance
        self.unrealized_pnl = 0.0
        self.details: Dict[str, Position] = {}
        self.trades: List[TradeFill] = []
        self.config = ExchangeConfig
        self.mode = mode
        self.exit_policy = exit_policy
        self.reporter = reporter # Added for debug logging
        
        # Realism Config Defaults
        self.realism = realism_config or {
            "fee_bps": 4.0,
            "slippage_bps": 2.0,
            "spread_bps": 1.0,
            "funding_bps_per_8h": 0.0,
            "use_bid_ask": False,
            "max_risk_per_trade_pct": 1.0,
            "max_notional_pct_of_equity": 100.0,
            "liq_safety_margin_pct": 20.0
        }
        self.realism_engine = RealismEngine(
            RealismConfig(
                fees=FeeModel(
                    taker_bps=float(self.realism.get("fee_bps", 4.0)),
                    maker_bps=float(self.realism.get("maker_bps", 2.0)),
                    funding_bps=float(self.realism.get("funding_bps_per_8h", 1.0)),
                ),
                slippage=SlippageModel(
                    base_bps=float(self.realism.get("slippage_bps", 2.0)),
                    size_impact_bps=float(self.realism.get("size_impact_bps", 1.0)),
                    volatility_mult=float(self.realism.get("volatility_mult", 1.5)),
                ),
            )
        )
        
        # Advanced Exit Config
        self.trailing_active = (exit_policy == "TRAILING_STOP")
        self.trailing_dist_pct = 0.015 
        self.trailing_activation_pct = 0.01 
        self.time_stop_bars = 48 
        self.time_stop_active = (exit_policy == "TIME_STOP" or mode == "adaptive")
        
        # Override for FIXED
        if exit_policy == "FIXED_BRACKET":
             self.trailing_active = False

    def _get_execution_price(self, price: float, side: str, is_entry: bool = True, quantity: float = 1.0, atr: Optional[float] = None) -> float:
        """
        Calculates execution price including Spread and Slippage.
        Price is usually 'close' or 'trigger' price.
        
        Formula:
        If use_bid_ask is True:
          BUY = price * (1 + spread_bps/10000 + slippage_bps/10000)
          SELL = price * (1 - spread_bps/10000 - slippage_bps/10000)
        Else:
          Ignore spread, just slippage? 
          Prompt said: "BUY entry = close * (1 + ... + ...)"
          Assuming non-bid-ask mode also applies basic slippage.
        """
        spread_bps = self.realism.get("spread_bps", 1.0)
        use_bid_ask = self.realism.get("use_bid_ask", False)
        
        # Determine direction relative to price
        # BUY (Entry or Exit Short) -> Pay more
        # SELL (Entry Short or Exit Long) -> Receive less
        
        spread_factor = (spread_bps / 10000.0) if use_bid_ask else 0.0
        if side == "BUY":
            adjusted_price = price * (1.0 + spread_factor)
        elif side == "SELL":
            adjusted_price = price * (1.0 - spread_factor)
        else:
            adjusted_price = price

        return self.realism_engine.get_effective_price(
            adjusted_price,
            max(quantity, 0.0),
            side,
            atr=atr,
        )


    def mark_to_market(self, symbol: str, current_price: float) -> float:
        self.unrealized_pnl = 0.0
        
        if symbol in self.details:
            pos = self.details[symbol]
            pos.bars_held += 1 # Increment bars held on every mark update
            
            # Update extremes
            if current_price > pos.highest_price: pos.highest_price = current_price
            if current_price < pos.lowest_price: pos.lowest_price = current_price
            
            pnl = 0.0
            if pos.side == "BUY":
                pnl = (current_price - pos.entry_price) * pos.quantity
            elif pos.side == "SELL":
                pnl = (pos.entry_price - current_price) * pos.quantity
                
            self.unrealized_pnl += pnl
                
        self.equity = self.balance + self.unrealized_pnl
        return self.equity

    def get_state(self, timestamp: float, snapshot_type: str = "BAR") -> AccountState:
        # PnL matches the last mark_to_market call. 
        # If we just traded, PnL for new pos is 0 relative to entry (mark).
        # Balance might have changed due to comm.
        # So recalculate equity to be safe.
        self.equity = self.balance + self.unrealized_pnl
        
        qty = 0.0
        for pos in self.details.values():
            qty += (pos.quantity if pos.side == "BUY" else -pos.quantity)
            
        return AccountState(
            timestamp=timestamp,
            equity=self.equity,
            balance=self.balance,
            unrealized_pnl=self.unrealized_pnl,
            open_quantity=qty,
            snapshot_type=snapshot_type
        )

    def check_brackets(self, symbol: str, high: float, low: float, timestamp: float) -> Optional[TradeFill]:
        if symbol not in self.details: return None
        
        pos = self.details[symbol]
        
        # 0. Time Stop (Stagnation)
        if self.time_stop_active and pos.bars_held > self.time_stop_bars:
             # Check if PnL is negative/stagnant? Or just hard exit.
             # Strict Time Stop = Exit regardless.
             return self._close_position(symbol, (high+low)/2, "TIME", timestamp)
             
        # Same Bar Protection (Phase P2.2)
        if timestamp <= pos.creation_time:
             return None
        
        # 1. Update Trailing Stop
        if self.trailing_active:
            if pos.side == "BUY":
                profit_high = (pos.highest_price - pos.entry_price) / pos.entry_price
                if profit_high >= self.trailing_activation_pct:
                    new_sl = pos.highest_price * (1.0 - self.trailing_dist_pct)
                    if pos.sl_price is None or new_sl > pos.sl_price:
                        pos.sl_price = new_sl
            elif pos.side == "SELL":
                 profit_low = (pos.entry_price - pos.lowest_price) / pos.entry_price
                 if profit_low >= self.trailing_activation_pct:
                     new_sl = pos.lowest_price * (1.0 + self.trailing_dist_pct)
                     if pos.sl_price is None or new_sl < pos.sl_price:
                         pos.sl_price = new_sl

        # 2. Check Exits 
        if pos.side == "BUY":
            if pos.sl_price and low <= pos.sl_price:
                return self._close_position(symbol, pos.sl_price, "SL", timestamp)
            if pos.tp_price and high >= pos.tp_price:
                return self._close_position(symbol, pos.tp_price, "TP", timestamp)
        
        elif pos.side == "SELL":
            if pos.sl_price and high >= pos.sl_price:
                return self._close_position(symbol, pos.sl_price, "SL", timestamp)
            if pos.tp_price and low <= pos.tp_price:
                return self._close_position(symbol, pos.tp_price, "TP", timestamp)
            
        return None

    def execute_strategy(
        self,
        symbol: str,
        decision: str,
        direction: str,
        price: float,
        timestamp: float,
        risk_pct: float = 0.02,
        leverage: float = 1.0,
        custom_sl_price: Optional[float] = None,
        custom_tp_price: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Returns (Success, Reason/Details)
        """
        if symbol in self.details: 
             return (False, "Already in position")
        
        if decision == "GO":
            rules = self.config.get_rules(symbol, self.mode)
            # Phase P2.1: Small Cap Optimization
            if self.balance < 100:
                rules.min_notional = 2.0
            
            # Realism: Calculate Real Execution Price
            exec_price = self._get_execution_price(price, direction, is_entry=True, quantity=1.0)
            
            sl_price = 0.0
            tp_price = 0.0
            
            # Simple bracket logic (can be refined later to use volatility)
            if direction == "BUY":
                sl_price = custom_sl_price if custom_sl_price is not None else (exec_price * 0.98)
                tp_price = custom_tp_price if custom_tp_price is not None else (exec_price * 1.04)
            elif direction == "SELL":
                sl_price = custom_sl_price if custom_sl_price is not None else (exec_price * 1.02)
                tp_price = custom_tp_price if custom_tp_price is not None else (exec_price * 0.96)
            else:
                 return (False, "Invalid Direction")
            
            # Sizing
            risk_amt = self.equity * risk_pct
            price_dist = abs(exec_price - sl_price)
            if price_dist == 0: return (False, "Invalid SL Dist")
            
            qty_risk = risk_amt / price_dist
            max_qty_margin = (self.equity * leverage) / exec_price
            
            qty = min(qty_risk, max_qty_margin)
            
            # Ensure fee buffer
            # Fee logic: bps on total Notional (Lev * Equity usually, but simpler: Qty * Price)
            # We pay fee on OPEN and CLOSE.
            # Fee BPS from config
            fee_bps = self.realism_engine.config.fees.taker_bps
            fee_rate = fee_bps / 10000.0
            
            # Recalculate max qty considering initial margin + open fee
            # Equity >= (Qty * Price / Lev) + (Qty * Price * FeeRate)
            # Equity >= Qty * Price * (1/Lev + FeeRate)
            qty_capped_by_equity = self.equity / (exec_price * (1.0/leverage + fee_rate))
            
            qty = min(qty, qty_capped_by_equity)
            
            # Guardrails (Mega Prompt)
            # 1. Max Risk Per Trade %
            # Actual Risk = Qty * |Entry - SL|
            # Risk % = Actual Risk / Equity
            actual_risk_val = qty * price_dist
            max_risk_pct_cap = self.realism.get("max_risk_per_trade_pct", 1.0) / 100.0
            actual_risk_ratio = (actual_risk_val / self.equity) if self.equity > 0 else 0.0
            # Tolerate tiny floating-point drift at the cap boundary (e.g. 1.0000000002%).
            eps = 1e-9
            
            if (actual_risk_ratio - max_risk_pct_cap) > eps:
                # Should we resize or reject? Prompt says "REJECT et"
                # "Eğer position açma, bu guardrail’leri ihlal ediyorsa trade’i REJECT et"
                return (False, f"REJECT_RISK_CAP: Risk {actual_risk_ratio*100:.2f}% > {max_risk_pct_cap*100:.2f}%")

            # 2. Notional Cap
            notional = qty * exec_price
            max_notional_pct = self.realism.get("max_notional_pct_of_equity", 100.0) / 100.0
            notional_ratio = (notional / self.equity) if self.equity > 0 else 0.0
            if (notional_ratio - max_notional_pct) > eps:
                 return (False, f"REJECT_NOTIONAL_CAP: Notional {notional_ratio*100:.2f}% > {max_notional_pct*100:.2f}%")

            # 3. Liquidation Safety Margin
            # Liq Price approx: Entry * (1 - 1/Lev) for Long, Entry * (1 + 1/Lev) for Short (Isolated)
            # Safety Margin = abs(Entry - Liq) / Entry ? Or distance.
            # Prompt: "liq_safety_margin_pct (default 20.0)"
            # "Entry vs LiqPrice is too close" -> Reject if we are too leveraged basically.
            # Approx Liq Distance % = 1 / Leverage
            # If 1/Lev < SafetyMargin, it's unsafe?
            # Example: Lev 10x -> dist 10%. Safety 20% -> Reject.
            # Example: Lev 2x -> dist 50%. Safety 20% -> OK.
            # So logic: (1 / Leverage) must be > (SafetyMarginPct / 100) ???
            # Wait, safety margin usually means "How far is Liq from price".
            # If I ask for 20% safety, I want Liq to be at least 20% away.
            # So 1/Lev >= 0.20 -> Lev <= 5.
            # Implementation:
            liq_dist_pct = 1.0 / leverage
            req_safety = self.realism.get("liq_safety_margin_pct", 20.0) / 100.0
            if liq_dist_pct < req_safety:
                 return (False, f"REJECT_LIQ_MARGIN: LiqDist {liq_dist_pct*100:.1f}% < {req_safety*100:.1f}% (Lev {leverage}x too high)")

            
            # Step Size Rounding
            step_size = rules.step_size if hasattr(rules, 'step_size') and rules.step_size else 0.000001
            qty = int(qty / step_size) * step_size
            
            if qty <= 0:
                 return (False, f"Qty calculated to 0.")
                 
            notional = qty * exec_price
            if notional < rules.min_notional:
                 return (False, f"Min Notional Fail: {notional:.2f} < {rules.min_notional}")

            self.place_order(symbol, direction, exec_price, qty, sl_price, tp_price, timestamp, mark_price=price)
            return (True, f"Filled @ {exec_price:.2f} (Lev {leverage}x)")
            
        return (False, "NO_GO")

    def close_all_positions(self, timestamp: float, price_dict: Dict[str, float]) -> List[TradeFill]:
        """
        Force close all open positions at given prices.
        """
        closed_trades = []
        # Create a list key entries to avoid runtime error during iteration
        symbols = list(self.details.keys())
        for symbol in symbols:
            price = price_dict.get(symbol)
            if price:
                t_fill = self._close_position(symbol, price, "EOS", timestamp)
                closed_trades.append(t_fill)
        return closed_trades

    def close_all(self, timestamp: float, price_dict: Dict[str, float]) -> List[TradeFill]:
        """Compatibility alias used by risk kill-switch integration."""
        return self.close_all_positions(timestamp, price_dict)

    def _generate_stable_pid(self, symbol: str, timestamp: float, direction: str, price: float, unique_seq: int) -> str:
        """
        Generates a deterministic 8-char PositionID based on entry details + sequence counter.
        Uses SHA1 hash of (Symbol, IntTimestamp, Direction, RoundedPrice, Seq).
        """
        import hashlib
        # Round price to 4 decimals to avoid float jitter
        price_str = f"{price:.4f}"
        # Use int timestamp to avoid microsecond jitter
        ts_int = int(timestamp)
        
        raw = f"{symbol}|{ts_int}|{direction}|{price_str}|{unique_seq}"
        return hashlib.sha1(raw.encode()).hexdigest()[:8]

    def place_order(self, symbol: str, side: str, price: float, quantity: float, sl: float = None, tp: float = None, timestamp: float = 0, mark_price: float = 0.0):
        cost = price * quantity
        comm = self.realism_engine.calculate_commission(quantity, price, is_taker=True)
        
        if mark_price == 0.0: mark_price = price # Fallback
        
        if side == "BUY":
            self.balance -= (cost + comm)
        elif side == "SELL":
            self.balance -= comm 

        # Generate Deterministic Position ID with Sequence Counter to prevent collisions
        seq = len(self.trades)
        pid = self._generate_stable_pid(symbol, timestamp, side, price, seq)
            
        pos = Position(symbol, side, price, quantity, pid, sl, tp, timestamp)
        self.details[symbol] = pos
        
        tf = TradeFill(timestamp, symbol, side, price, quantity, comm, 0.0, pid, "OPEN")
        tf.mark_price = mark_price
        tf.fill_price = price
        self.trades.append(tf)
        
        # Immediate Equity Update (PnL 0)
        self.equity = self.balance + self.unrealized_pnl
        return True

    def _close_position(self, symbol: str, price: float, reason: str, timestamp: float) -> TradeFill:
        pos = self.details.pop(symbol)
        
        # Realism: Apply Slippage/Spread to Exit Price too!
        # When closing BUY (Selling): Price is Bid (Lower)
        # When closing SELL (Buying): Price is Ask (Higher)
        # Determining Side of closing trade:
        close_side = "SELL" if pos.side == "BUY" else "BUY"
        final_price = self._get_execution_price(
            price,
            close_side,
            is_entry=False,
            quantity=pos.quantity,
        )
        
        revenue = final_price * pos.quantity
        comm = self.realism_engine.calculate_commission(pos.quantity, final_price, is_taker=True)
        
        net = 0.0
        if pos.side == "BUY":
            gross = (final_price - pos.entry_price) * pos.quantity
            self.balance += (revenue - comm)
            # Net PnL = Gross - ExitFee - EntryFee
            # Existing `TradeFill` log stored Entry Comm. We can't access it easily without lookup?
            # Actually, we don't store EntryComm in Position.
            # We can approx: Total PnL of this trade (Exit - Entry) - Total Comm.
            # Or just store Net of this 'leg'.
            # Argus usually tracks "Trade PnL" as entry vs exit net of ALL fees?
            # Let's stick to standard PnL = (Exit - Entry) * Qty - ExitComm.
            # The EntryComm was already deducted from Balance.
            # So "Net" here is the realization effect on balance?
            # Let's effectively log the realized PnL of the round trip if possible, or just this fill.
            # Standard: realized_pnl = (exit - entry) * qty - exit_comm - entry_comm.
            # Simplified: (exit - entry) * qty - exit_comm. (Entry comm is sunk cost).
            net = gross - comm
            
        elif pos.side == "SELL":
            gross = (pos.entry_price - final_price) * pos.quantity
            self.balance += (gross - comm) # Short close: Receive Initial Margin + PnL - Comm? 
            # Simplified model: Balance += Gross (PnL) - Comm. (And we get back margin?)
            # Actually, `place_order` for short didn't deduct cost. It only deducted comm.
            # So `balance` was high.
            # Now we add `gross` (PnL).
            # If PnL negative, we subtract.
            # So Balance += (PnL - Comm).
            # Logic: `gross - comm`. Correct.
            net = gross - comm
        
        # Update PnL (Closed = 0 unrealized for this pos)
        self.unrealized_pnl = 0.0 
        self.equity = self.balance + self.unrealized_pnl
        
        # Update PnL (Closed = 0 unrealized for this pos)
        self.unrealized_pnl = 0.0 
        self.equity = self.balance + self.unrealized_pnl
        
        # Log CLOSE event with same PositionID
        trade = TradeFill(timestamp, symbol, f"{close_side}_{reason}", final_price, pos.quantity, comm, net, pos.position_id, "CLOSE")
        trade.mark_price = price # 'price' passed to _close_position IS Mark/Trigger Price
        trade.fill_price = final_price
        self.trades.append(trade)
        return trade
