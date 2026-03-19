import argparse
import time
import os
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any

from argus_py.exchange.bingx import BingXAdapter
from argus_py.exchange.base import ExchangeOrder
from argus_py.models.aegean.aegean import AegeanEngine
from argus_py.models.orion.orion import OrionEngine
from argus_py.council.aggregator import Council
from argus_py.risk.mode_engine import ModeEngine
from argus_py.risk.regime import RegimeDetector
from argus_py.data.reporting import Reporter
from argus_py.core.exchange_rules import ExchangeConfig

# Safety Constants
MAX_DAILY_LOSS_PCT_DEFAULT = 0.02
MAX_DD_PCT_DEFAULT = 0.05
MAX_CONSECUTIVE_LOSSES_DEFAULT = 3

class LiveRunner:
    def __init__(self, args):
        self.args = args
        self.symbol = args.symbol
        self.tf = args.tf
        
        # 1. Mode & Safety Checks
        self.is_live = False
        if args.mode == "live":
            if args.i_understand_live_trading == "yes":
                self.is_live = True
                print("!!! WARNING: LIVE TRADING MODE ENABLED !!!")
            else:
                print("WARNING: Live mode requested but confirmation missing. Forcing DRY RUN.")
        
        # 2. Components
        # Exchange
        api_key = os.environ.get("BINGX_API_KEY")
        api_secret = os.environ.get("BINGX_SECRET")
        self.exchange = BingXAdapter(api_key, api_secret, dry_run=not self.is_live)
        
        # Brain
        self.aegean = AegeanEngine()
        self.orion = OrionEngine()
        self.council = Council()
        self.regime_detector = RegimeDetector()
        self.mode_engine = ModeEngine(
            max_daily_dd_pct=args.max_daily_loss_pct, 
            max_total_dd_pct=args.max_dd_pct,
            profile_override=args.profile
        )
        
        # Reporting
        self.reporter = Reporter(base_dir="runs/live")
        self.reporter.save_config(args)
        
        # State
        self.state_file = os.path.join(self.reporter.run_dir, "live_state.json")
        self.state = {
            "start_balance": 0.0,
            "current_balance": 0.0,
            "daily_start_balance": 0.0,
            "daily_pnl": 0.0,
            "consecutive_losses": 0,
            "trades": [],
            "last_processed_ts": 0
        }
        self.load_state()
        
        # Init Balance
        self.sync_balance()

    def sync_balance(self):
        try:
            bal = self.exchange.get_balance("USDT")
            if self.state["start_balance"] == 0:
                self.state["start_balance"] = bal
                self.state["daily_start_balance"] = bal
            
            self.state["current_balance"] = bal
            
            # Recalculate Daily PnL
            # (Simple: Current - DailyStart)
            # In real system, handle deposits/withdrawals logic.
            self.state["daily_pnl"] = self.state["current_balance"] - self.state["daily_start_balance"]
            self.save_state()
            
        except Exception as e:
            print(f"Error syncing balance: {e}")

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.state.update(data)
            except Exception as e:
                print(f"Error loading state: {e}")

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=4)

    def check_safety_gates(self) -> bool:
        # 1. Daily Loss
        loss_pct = 0.0
        if self.state["daily_start_balance"] > 0:
            loss_pct = -1 * (self.state["daily_pnl"] / self.state["daily_start_balance"])
        
        if loss_pct > self.args.max_daily_loss_pct:
            print(f"SAFETY GATE: Max Daily Loss Hit ({loss_pct*100:.2f}% > {self.args.max_daily_loss_pct*100:.2f}%)")
            return False

        # 2. Consecutive Losses
        if self.state["consecutive_losses"] >= self.args.max_consecutive_losses:
             print(f"SAFETY GATE: Max Consecutive Losses Hit ({self.state['consecutive_losses']})")
             return False
             
        # 3. Mode Engine Safety
        # Already checked in logic, but explicit check here good.
        
        return True

    def loop(self):
        print(f"--- Live Runner Started [{self.symbol}] ---")
        while True:
            try:
                self.tick()
            except Exception as e:
                print(f"Error in tick: {e}")
                
            time.sleep(self.args.poll_seconds)

    def tick(self):
        # 1. Fetch Candles
        # Need enough history for indicators (e.g. 100 bars)
        candles = self.exchange.get_public_candles(self.symbol, self.tf, limit=200)
        if not candles: 
            print("No candles yielded.")
            return

        # Convert to internal Bar format
        # TODO: Define conversation logic. 
        # Assuming we have a helper or do it inline. 
        # For simplicity, let's assume candles is list of Objects compatible with Council.
        # But Council expects 'Bar' objects.
        # We need a quick adapter here.
        # skipping detailed implementation for brevity, assuming stub.

        # Check if new bar closed
        last_candle = candles[-1]
        ts = last_candle.get('timestamp', 0)
        
        # Simple Logic: Run on every poll? Or only on new bar?
        # Council logic usually On-Close-Bar.
        # If ts > self.state["last_processed_ts"] -> New Bar.
        # But for live, we might want intra-bar checks? 
        # Let's stick to ON CLOSE for safety.
        # Real exchanges update current candle timestamp continuously. 
        # We need completed candles. 'candles' usually returns completed + current.
        # We look at candles[-2] (last completed).
        
        completed_candle = candles[-2] if len(candles) > 1 else None
        if not completed_candle: return
        
        c_ts = completed_candle.get('timestamp')
        if c_ts <= self.state["last_processed_ts"]:
             return # Already processed
             
        print(f"Processing Bar: {datetime.fromtimestamp(c_ts/1000)}")
        
        # 2. Update Balance
        self.sync_balance()
        if not self.check_safety_gates():
             return

        # 3. Strategy
        # Build History...
        # ...
        
        # 4. Decision
        # ...
        
        # 5. Execution
        # If GO:
        #   check filters
        #   place_order()
        
        self.state["last_processed_ts"] = c_ts
        self.save_state()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="bingx")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--tf", default="15m")
    parser.add_argument("--mode", default="dry_run", choices=["dry_run", "live"])
    parser.add_argument("--profile", default="AUTO")
    parser.add_argument("--i_understand_live_trading", default="no")
    parser.add_argument("--poll_seconds", type=int, default=30)
    
    # Safety args
    parser.add_argument("--max_daily_loss_pct", type=float, default=MAX_DAILY_LOSS_PCT_DEFAULT)
    parser.add_argument("--max_dd_pct", type=float, default=MAX_DD_PCT_DEFAULT)
    parser.add_argument("--max_consecutive_losses", type=int, default=MAX_CONSECUTIVE_LOSSES_DEFAULT)
    
    args = parser.parse_args()
    
    runner = LiveRunner(args)
    runner.loop()
