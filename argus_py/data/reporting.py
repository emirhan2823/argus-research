import csv
import os
import json
from datetime import datetime
from typing import List, Any
from argus_py.broker.paper import TradeFill, AccountState
from argus_py.council.defs import ConsensusVerdict

class Reporter:
    def __init__(self, base_dir="runs"):
        import uuid
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        self.run_dir = os.path.join(base_dir, f"{ts}_{suffix}")
        if not os.path.exists(self.run_dir):
            os.makedirs(self.run_dir)
        print(f"Logging run to: {self.run_dir}")
            
    def save_config(self, args: Any):
        path = os.path.join(self.run_dir, "config.json")
        with open(path, 'w') as f:
            json.dump(vars(args), f, indent=4)
            
    def log_decision(self, verdict: ConsensusVerdict, mode_process: Any = None, capital_profile: str = "N/A"):
        path = os.path.join(self.run_dir, "decision_log.csv")
        exists = os.path.exists(path)
        
        with open(path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow([
                    "Timestamp", "Regime", "Decision", "Direction", "Conviction", 
                    "Mode", "CapitalProfile", "RiskStyle", "Lev", "Mult", 
                    "Votes", "Rationale",
                    "BlockReason", "AegeanSlope", "AegeanZone", "OrionADX", "OrionTrend",
                    "ExpMove", "Cost", "SafetyFactor", "Score"
                ])
                
            votes_str = "|".join([f"{v.module}:{v.direction}({v.confidence:.2f})" for v in verdict.votes])
            
            mode_str = "N/A"
            risk_style_str = "N/A"
            mult_str = "1.0"
            lev_str = "1.0"
            
            if mode_process:
                mode_str = mode_process.mode.value
                risk_style_str = mode_process.profile.value if hasattr(mode_process, 'profile') else "N/A"
                mult_str = f"{mode_process.risk_multiplier:.2f}"
                lev_str = f"{getattr(mode_process, 'leverage_allowed', 1.0):.1f}"
            
            # Extract Metadata
            meta = verdict.metadata
            block_reason = meta.get("block_reason", "N/A")
            slope = f"{meta.get('slope', 0.0):.6f}"
            zone = meta.get("zone", "N/A")
            adx = f"{meta.get('adx', 0.0):.2f}"
            trend_active = meta.get("trend_active", False)
            exp_move = f"{meta.get('expected_move', 0.0):.1f}"
            cost = f"{meta.get('cost', 0.0):.1f}"
            score = f"{meta.get('score', 0.0):.2f}"
            safety = f"{meta.get('safety_factor', 0.0):.2f}"
            
            writer.writerow([
                verdict.timestamp,
                verdict.regime,
                verdict.decision,
                verdict.direction,
                f"{verdict.conviction:.2f}",
                mode_str,
                capital_profile,
                risk_style_str,
                lev_str,
                mult_str,
                votes_str,
                verdict.rationale,
                block_reason,
                slope,
                zone,
                adx,
                trend_active,
                exp_move,
                cost,
                safety,
                score
            ])

    def log_reject(self, timestamp: float, symbol: str, reason: str, details: str, meta: str = ""):
        path = os.path.join(self.run_dir, "rejects.csv")
        exists = os.path.exists(path)
        with open(path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(["Timestamp", "Symbol", "Reason", "Details", "Meta"])
            writer.writerow([timestamp, symbol, reason, details, meta])

    def log_debug(self, timestamp: float, symbol: str, key: str, details: str, meta: str = ""):
        path = os.path.join(self.run_dir, "debug.csv")
        exists = os.path.exists(path)
        with open(path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(["Timestamp", "Symbol", "Key", "Details", "Meta"])
            writer.writerow([timestamp, symbol, key, details, meta])

    def save_trades(self, trades: List[TradeFill], filename="trades.csv"):
        path = os.path.join(self.run_dir, filename)
            
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Symbol", "Side", "Price", "Qty", "Comm", "PnL", "Event", "PositionId", "MarkPrice", "FillPrice"])
            for t in trades:
                # Use getattr for backward compat if field missing in older objects (though we updated class)
                mp = getattr(t, 'mark_price', 0.0)
                fp = getattr(t, 'fill_price', 0.0)
                writer.writerow([t.timestamp, t.symbol, t.side, t.price, t.quantity, t.commission, t.pnl, t.event, t.position_id, mp, fp])
                
    def save_metrics(self, equity_curve: List[AccountState], filename="metrics.csv"):
        path = os.path.join(self.run_dir, filename)
        with open(path, 'w', newline='') as f:
             writer = csv.writer(f)
             writer.writerow(["Bar", "Timestamp", "Equity", "Balance", "UnrealizedPnL", "PositionQty", "Type"])
             for i, state in enumerate(equity_curve):
                 writer.writerow([
                     i, 
                     state.timestamp, 
                     f"{state.equity:.2f}", 
                     f"{state.balance:.2f}",
                     f"{state.unrealized_pnl:.2f}",
                     f"{state.open_quantity:.8f}",
                     state.snapshot_type
                 ])

    def save_summary(self, start_balance: float, equity_curve: List[AccountState], trades: List[TradeFill], signal_stats: dict = None, data_summary: dict = None):
        if not equity_curve: return
        
        final_equity = equity_curve[-1].equity
        total_ret_pct = ((final_equity / start_balance) - 1) * 100.0
        
        # Max Drawdown
        high_water = 0.0
        max_dd = 0.0
        for s in equity_curve:
            if s.equity > high_water: high_water = s.equity
            dd = (high_water - s.equity) / high_water if high_water > 0 else 0
            if dd > max_dd: max_dd = dd
            
        # Win Rate / Profit Factor
        # Filter only CLOSE trades for PnL
        closed_trades = [t for t in trades if t.event == "CLOSE"]
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0.0
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
        
        total_pnl = sum(t.pnl for t in closed_trades)
        total_comm = sum(t.commission for t in trades)
        
        # JSON Summary
        summary = {
            "start_balance": start_balance,
            "final_equity": final_equity,
            "total_return_pct": total_ret_pct,
            "max_drawdown_pct": max_dd * 100.0,
            "total_trades": len(closed_trades),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "total_fees": total_comm,
            "trade_counts": {
                "open": len([t for t in trades if t.event == "OPEN"]),
                "close": len(closed_trades)
            }
        }
        
        if signal_stats:
            summary["signals"] = signal_stats
            
        if data_summary:
            summary["data_summary"] = data_summary
        
        path = os.path.join(self.run_dir, "summary.json")
        with open(path, 'w') as f:
            json.dump(summary, f, indent=4)
            
        # CSV Summary (Requested Phase B)
        path_csv = os.path.join(self.run_dir, "summary.csv")
        with open(path_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            header = ["TotalReturn", "MaxDrawdown", "TotalTrades", "WinRate", "ProfitFactor", "FinalEquity", "TotalPnL", "TotalFees"]
            row = [
                f"{total_ret_pct:.2f}",
                f"{max_dd:.4f}",
                len(closed_trades),
                f"{win_rate:.2f}",
                f"{profit_factor:.2f}",
                f"{final_equity:.2f}",
                f"{total_pnl:.2f}",
                f"{total_comm:.2f}"
            ]
            
            if signal_stats:
                header.extend(["TotalSignals", "TrendSignals", "ChopSignals"])
                row.extend([
                    signal_stats.get("total_go", 0),
                    signal_stats.get("go_trend", 0),
                    signal_stats.get("go_chop", 0)
                ])
                
            writer.writerow(header)
            writer.writerow(row)
