
import os
import sys
import time
import json
import requests
import traceback
import pandas as pd
import numpy as np
from datetime import datetime
from collections import deque
from argparse import Namespace
from pathlib import Path

# --- ABSOLUTE PATH SETUP ---
# Script is in scripts/, so repo_root is parent
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from argus_py.models.aegean.aegean import AegeanEngine
from argus_py.models.orion.orion import OrionEngine
from argus_py.council.aggregator import Council
from argus_py.strategy.router import ModeRouter
from argus_py.risk.regime import RegimeDetector
from argus_py.broker.paper import PaperBroker
from argus_py.data.reporting import Reporter
from argus_py.data.market_state import Bar
from argus_py.telemetry.schema import TelemetryEvent
import argparse

# --- CONFIGURATION (Adx35_Exp80) ---
# --- CONFIGURATION (DEFAULTS) ---
DEFAULT_CONFIG = {
    "symbol": "BTCUSDT",
    "interval": "1m",
    "lookback_init": 1000,
    "run_dir": REPO_ROOT / "runs/phase19_twin/STRICT",
    "daemon_id": "STRICT",
    # Strategy Params
    "min_adx": 35.0,
    "max_exp_move_bps": 80.0,
    "fee_bps": 4.0,
    "slippage_bps": 2.0,
    "spread_bps": 1.0,
    "min_expected_move_bps": 0.0,
    # Advanced Strategy Params
    "atr_k": 1.0,
    "adx_boost": 1.3,
    "exp_cap_mult": 1.5,
    "min_expected_move_multiplier": 0.0,
    "vol_trap_v2": False,
    "cost_safety_factor": 2.0,
    "cost_safety_homerun": 1.3,
    "adaptive_cost_safety": False,
    "start_balance": 1000.0,
    "max_risk_trade_pct": 1.0,
    "daily_loss_limit_pct": 3.0,
    "kill_switch_dd_pct": 8.0,
    
    # Config Objects Mock (Will be populated in main)
    "args": None
}

class PaperDaemon:
    def __init__(self, config):
        self.cfg = config
        self.run_dir = Path(self.cfg["run_dir"])
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        # Paths
        self.state_file = self.run_dir / "daemon_state.json"
        self.state_file_tmp = self.run_dir / "daemon_state.json.tmp"
        self.hb_log = self.run_dir / "status.log"
        self.state_file_tmp = self.run_dir / "daemon_state.json.tmp"
        self.hb_log = self.run_dir / "status.log"
        self.error_log = self.run_dir / "errors.log"

        # Phase 19.5 Telemetry Files
        self.heartbeat_file = self.run_dir / "heartbeat.json"
        self.heartbeat_tmp = self.run_dir / "heartbeat.json.tmp"
        self.decisions_csv = self.run_dir / "decisions.csv"
        self.decisions_jsonl = self.run_dir / "decisions.jsonl"
        self.rejects_csv = self.run_dir / "rejects.csv"
        self.rejects_jsonl = self.run_dir / "rejects.jsonl"
        self.trades_csv = self.run_dir / "trades.csv"
        self.trades_jsonl = self.run_dir / "trades.jsonl"

        # Counters & Health
        self.counters = {
            "bars_seen": 0,
            "decisions_total": 0,
            "trades_total": 0,
            "rejects_total": 0
        }
        self.health = {
            "last_error": None,
            "consecutive_errors": 0,
            "start_time_iso": datetime.now().isoformat()
        }
        
        # Ensure CSV Headers
        self._init_csvs()
        
        # 1. Start Logging
        print(f"Daemon Initialized.")
        print(f"Repo Root: {REPO_ROOT}")
        print(f"Run Dir: {self.run_dir}")
        print(f"State File: {self.state_file}")
        
        # 2. Load State
        loaded_state = self.load_state()
        initial_balance = loaded_state.get("balance", self.cfg["start_balance"])
        
        # 3. Components
        self.reporter = Reporter(str(self.run_dir))
        self.broker = PaperBroker(
            start_balance=initial_balance,
            mode="paper",
            reporter=self.reporter
        )
        
        # Inject Positions
        if "positions" in loaded_state:
            # TODO: Rehydrate positions if complex state needed
            if loaded_state["positions"]:
                print(f"WARNING: Previous positions existed but manual rehydration pending.")
        
        # Strategy
        self.aegean = AegeanEngine()
        self.orion = OrionEngine()
        self.council = Council()
        self.router = ModeRouter()
        self.regime_detector = RegimeDetector()
        
        # Runtime
        self.history_bars = [] 
        self.atr_history = []
        
        # Initialize Logs
        with open(self.hb_log, "a") as f:
            f.write(f"\n--- SESSION START {datetime.now()} ---\n")
            
    def load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading state: {e}")
        return {}

    def save_state(self, reason="update"):
        try:
            state = {
                "timestamp": time.time(),
                "timestamp_iso": datetime.now().isoformat(),
                "reason": reason,
                "balance": self.broker.balance,
                "equity": self.broker.equity,
                "positions": [str(p) for p in self.broker.details.values()],
                "config_snapshot": {
                    "symbol": self.cfg["args"].symbol,
                    "min_adx": self.cfg["min_adx"]
                }
            }
            # Atomic Write
            with open(self.state_file_tmp, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(self.state_file_tmp, self.state_file)
            
            size = self.state_file.stat().st_size
            print(f"STATE_SAVED: {self.state_file} size={size} reason={reason}")
            
        except Exception:
            self.log_error("SAVE_STATE_FAILED")

    def log_error(self, context):
        self.health["last_error"] = f"{context} @ {datetime.now().isoformat()}"
        self.health["consecutive_errors"] += 1
        with open(self.error_log, "a") as f:
            f.write(f"--- ERROR in {context} @ {datetime.now()} ---\n")
            traceback.print_exc(file=f)
        traceback.print_exc()
        # Force Heartbeat Update to reflect error
        self.update_heartbeat()

    def _init_csvs(self):
        # Decisions
        if not self.decisions_csv.exists():
            with open(self.decisions_csv, "w") as f:
                f.write("ts_iso,bar_ts_iso,symbol,regime,mode,decision,direction,score,exp_move,adx,reasons\n")
        
        # Rejects
        if not self.rejects_csv.exists():
            with open(self.rejects_csv, "w") as f:
                f.write("ts_iso,bar_ts_iso,symbol,code,detail\n")

        # Trades (Simple Mirror)
        if not self.trades_csv.exists():
            with open(self.trades_csv, "w") as f:
                f.write("ts_iso,symbol,side,price,qty,pnl,event\n")

    def update_heartbeat(self, last_bar=None):
        try:
            hb = {
                "ts_iso": datetime.now().isoformat(),
                "last_closed_bar_iso": datetime.fromtimestamp(last_bar.timestamp).isoformat() if last_bar else None,
                "last_price": last_bar.close if last_bar else 0.0,
                "equity": self.broker.equity,
                "balance": self.broker.balance,
                "dd_pct": (1.0 - (self.broker.equity / self.cfg["start_balance"])) * 100.0,
                "position": None,
                "counters": self.counters,
                "daemon": {
                    "id": self.cfg["daemon_id"],
                    "min_adx": self.cfg["min_adx"]
                },
                "health": {
                    "stale_seconds": 0, # Calculated by consumer
                    "last_error": self.health["last_error"],
                    "consecutive_errors": self.health["consecutive_errors"],
                    "uptime_start": self.health["start_time_iso"]
                }
            }
            
            # Position Detail if exists
            open_positions = list(self.broker.details.values())
            if open_positions:
                p = open_positions[0]
                hb["position"] = {
                    "side": p.side,
                    "qty": p.quantity,
                    "entry": p.entry_price,
                    "unrealized_pnl": self.broker.unrealized_pnl,
                    "id": p.position_id
                }

            # Atomic Write
            with open(self.heartbeat_tmp, "w") as f:
                json.dump(hb, f, indent=2)
            os.replace(self.heartbeat_tmp, self.heartbeat_file)
            
        except Exception as e:
            print(f"Heartbeat Error: {e}")

    def append_decision(self, bar, verdict, router_res, score, exp_move, adx):
        self.counters["decisions_total"] += 1
        ts_iso = datetime.now().isoformat()
        bar_ts_iso = datetime.fromtimestamp(bar.timestamp).isoformat()
        reasons = verdict.metadata.get("block_reason", "")
        
        # CSV (Legacy/UI quick view)
        row = f"{ts_iso},{bar_ts_iso},{self.cfg['symbol']},{verdict.regime},{router_res['mode_final']},{verdict.decision},{verdict.direction},{score:.2f},{exp_move:.1f},{adx:.1f},{reasons}\n"
        with open(self.decisions_csv, "a") as f:
            f.write(row)
            
        # JSONL (Truth)
        reasons_list = [reasons] if reasons else []
        event = TelemetryEvent.decision(
            daemon_id=self.cfg["daemon_id"],
            run_id=self.cfg.get("run_id", "unknown"),
            symbol=self.cfg["symbol"],
            interval=self.cfg["interval"],
            bar_ts=bar.timestamp,
            regime=verdict.regime,
            mode=router_res['mode_final'],
            policy=router_res['policy'],
            verdict=verdict,
            scores={
                "ae_score": 0.0, # Not readily avail in daemon scope yet, placeholder
                "edge_score": score,
                "adx": adx,
                "slope": verdict.metadata.get("slope", 0.0),
                "atr": verdict.metadata.get("atr", 0.0),
                "expected_move_bps": exp_move
            },
            params={
                "max_exp_move_bps": self.cfg["max_exp_move_bps"],
                "min_adx": self.cfg["min_adx"]
            },
            reasons=reasons_list
        )
        with open(self.decisions_jsonl, "a") as f:
            f.write(json.dumps(event) + "\n")

    def append_reject(self, bar, code, detail):
        self.counters["rejects_total"] += 1
        ts_iso = datetime.now().isoformat()
        bar_ts_iso = datetime.fromtimestamp(bar.timestamp).isoformat()
        
        # CSV
        row = f"{ts_iso},{bar_ts_iso},{self.cfg['symbol']},{code},{detail}\n"
        with open(self.rejects_csv, "a") as f:
            f.write(row)
            
        # JSONL
        event = TelemetryEvent.reject(
            daemon_id=self.cfg["daemon_id"],
            run_id=self.cfg.get("run_id", "unknown"),
            symbol=self.cfg["symbol"],
            interval=self.cfg["interval"],
            bar_ts=bar.timestamp,
            code=code,
            detail=detail,
            snapshot={} # Could enrich later
        )
        with open(self.rejects_jsonl, "a") as f:
            f.write(json.dumps(event) + "\n")
            
    def append_trade(self, fill):
        self.counters["trades_total"] += 1
        ts_iso = datetime.now().isoformat()
        
        # CSV
        row = f"{ts_iso},{fill.symbol},{fill.side},{fill.price:.2f},{fill.quantity:.4f},{fill.pnl:.2f},{fill.event}\n"
        with open(self.trades_csv, "a") as f:
            f.write(row)
            
        # JSONL
        # Split open/close based on fill event or PnL?
        # Fill event usually 'ENTRY' or 'STOP'/'PROFIT'.
        # Assuming broker fills structure.
        if fill.pnl == 0.0 and fill.event in ["ENTRY", "signal"]: 
            event = TelemetryEvent.trade_open(
                daemon_id=self.cfg["daemon_id"],
                run_id=self.cfg.get("run_id", "unknown"),
                symbol=fill.symbol,
                interval=self.cfg["interval"],
                bar_ts=None, # timestamp in fill?
                entry_price=fill.price,
                qty=fill.quantity,
                side=fill.side,
                fees_model="legacy"
            )
        else:
            event = TelemetryEvent.trade_close(
                daemon_id=self.cfg["daemon_id"],
                run_id=self.cfg.get("run_id", "unknown"),
                symbol=fill.symbol,
                interval=self.cfg["interval"],
                bar_ts=None,
                exit_price=fill.price,
                pnl=fill.pnl,
                pnl_pct=0.0, # calculate if pos known
                reason=fill.event
            )
        with open(self.trades_jsonl, "a") as f:
            f.write(json.dumps(event) + "\n")

    def fetch_klines(self, limit=100):
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": self.cfg["symbol"],
            "interval": self.cfg["interval"],
            "limit": limit
        }
        
        attempts = 0
        while attempts < 3:
            try:
                r = requests.get(url, params=params, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    bars = []
                    for k in data:
                        b = Bar(
                            timestamp=int(k[0]) / 1000.0,
                            open=float(k[1]),
                            high=float(k[2]),
                            low=float(k[3]),
                            close=float(k[4]),
                            volume=float(k[5])
                        )
                        bars.append(b)
                    return bars
                elif r.status_code == 429:
                    print(f"Rate Limit 429. Waiting...")
                    time.sleep(10 + (attempts * 5))
            except Exception:
                # Log but retry
                pass
            
            attempts += 1
            time.sleep(2 * attempts)
            
        print("CRITICAL: Failed to fetch data.")
        return []

    def warmup(self):
        try:
            print(f"Warming up with {self.cfg['lookback_init']} bars...")
            bars = self.fetch_klines(limit=self.cfg['lookback_init'])
            if not bars:
                raise Exception("Warmup failed (No Data)")
                
            self.history_bars = bars
            
            # Rebuild ATR
            for i in range(max(0, len(bars)-100), len(bars)):
                subset = bars[:i+1]
                if len(subset) > 20:
                    or_vote = self.orion.calculate(subset)
                    curr_atr = or_vote.metadata.get('atr', 0.0)
                    if curr_atr > 0: self.atr_history.append(curr_atr)
                    
            print(f"Warmup Complete. ATR Points: {len(self.atr_history)}")
            self.save_state("warmup_complete")
            
        except Exception:
            self.log_error("WARMUP_FAILED")
            sys.exit(1)

    def run_loop(self):
        print("Daemon Started. Listening...")
        self.save_state("loop_start")
        last_ts = self.history_bars[-1].timestamp
        
        while True:
            try:
                # 1. Kill Switch
                dd_pct = (1.0 - (self.broker.equity / self.cfg["start_balance"])) * 100.0
                if dd_pct >= self.cfg["kill_switch_dd_pct"]:
                    print(f"KILL SWITCH TRIGGERED. DD: {dd_pct:.2f}%")
                    self.save_state("kill_switch")
                    break

                # 2. Fetch Data
                klines = self.fetch_klines(limit=2)
                if not klines:
                    time.sleep(10)
                    continue
                
                # Close Logic: index 0 is N-1 (Closed), index 1 is N (Open)
                # Ensure we process closed bar
                candidate_bar = klines[0]
                
                if candidate_bar.timestamp > last_ts:
                    print(f"[{datetime.fromtimestamp(candidate_bar.timestamp)}] New Closed Bar: {candidate_bar.close}")
                    self.process_bar(candidate_bar)
                    last_ts = candidate_bar.timestamp
                    self.save_state("new_bar_processed")
                    
                    # Heartbeat
                    self.update_heartbeat(last_bar=candidate_bar)
                    self.health["consecutive_errors"] = 0 # Reset health on success
                    
                    with open(self.hb_log, "a") as f:
                        entry = f"HEARTBEAT: {datetime.now().isoformat()} last_bar_ts={last_ts} equity={self.broker.equity:.2f} pos={len(self.broker.details)}\n"
                        f.write(entry)
                        
                time.sleep(5) 
                # Refresh heartbeat even if no new bar (keep alive) - every 12 loops (approx 1 min) ?
                # Or just every loop? cheap enough.
                self.update_heartbeat(last_bar=None if not self.history_bars else self.history_bars[-1]) 
                
            except KeyboardInterrupt:
                print("Stopping...")
                self.save_state("shutdown")
                break
            except Exception:
                self.log_error("RUN_LOOP_EXCEPTION")
                time.sleep(10)
                
    def process_bar(self, bar: Bar):
        self.counters["bars_seen"] += 1
        self.history_bars.append(bar)
        if len(self.history_bars) > 2000:
            self.history_bars.pop(0) 
        
        args = self.cfg["args"]
        history = self.history_bars
        
        # 1. Indicators
        regime = self.regime_detector.detect(history)
        ae_vote = self.aegean.calculate(history)
        or_vote = self.orion.calculate(history)
        
        # 2. MRIE & Router
        slope_raw = ae_vote.metadata.get('slope', 0.0)
        
        # 2. Router
        base_mode = "ATTACK"
        if regime == "CHOP": base_mode = "DEFENSE"
        elif regime == "RANGE": base_mode = "CAUTION"
        router_res = self.router.update(base_mode, abs(slope_raw))
        
        # 3. Council
        verdict = self.council.deliberate(
            [ae_vote, or_vote],
            regime,
            bar.timestamp,
            threshold=0.4,
            chop_floor=None
        )
        
        # 4. Filters (Adx35_Exp80)
        adx_m = or_vote.metadata.get('adx', 0.0)
        slope_bps_abs = (abs(slope_raw) / bar.close) * 10000.0
        atr_m = or_vote.metadata.get('atr', 0.0)
        atr_bps = (atr_m / bar.close) * 10000.0 if bar.close > 0 else 0.0
        
        expected_move = 0.0
        if verdict.decision == "GO":
             # Exp Logic
             adx_bps_m = adx_m * 0.4
             edge_score = (0.6 * slope_bps_abs) + (0.4 * adx_bps_m)
             
             atr_base = atr_bps * self.cfg["atr_k"]
             adx_factor = 0.0
             if adx_m > 20: adx_factor = min(1.0, (adx_m - 20) / 40.0)
             adx_boost = 1.0 + adx_factor
             
             expected_move = max(slope_bps_abs, atr_base) * adx_boost * self.cfg["adx_boost"]
             cap_bps = atr_bps * self.cfg["exp_cap_mult"]
             expected_move = min(expected_move, cap_bps)
             
             verdict.metadata['expected_move'] = expected_move
             verdict.metadata['score'] = edge_score

        # Gates
        # Risk Mult
        r_risk_mult = 1.0
        r_risk_mult = 1.0
        if router_res['policy'] == "caution_v5": r_risk_mult = 0.7
        elif router_res['policy'] == "defense_flat": 
            if self.cfg["soft_defense_override"]:
                r_risk_mult = 0.2
            else:
                r_risk_mult = 0.0
        
        if verdict.decision == "GO" and r_risk_mult == 0.0:
            verdict.decision = "BLOCK"
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "ROUTER_DEFENSE", "Risk=0.0")
            self.append_reject(bar, "ROUTER_DEFENSE", "Risk=0.0")

        # Min ADX
        min_adx = self.cfg["min_adx"]
        if router_res['policy'] == "caution_v5": min_adx += 10.0
        
        if verdict.decision == "GO" and adx_m < min_adx:
            verdict.decision = "BLOCK"
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "MIN_ADX", f"{adx_m:.1f} < {min_adx}")
            self.append_reject(bar, "MIN_ADX", f"{adx_m:.1f} < {min_adx}")

        # Max Exp
        max_exp = self.cfg["max_exp_move_bps"]
        em_check = verdict.metadata.get('expected_move', 0.0)
        if verdict.decision == "GO" and em_check > max_exp:
            verdict.decision = "BLOCK"
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "MAX_EXP", f"Exp {em_check:.1f} > {max_exp}")
            self.append_reject(bar, "MAX_EXP", f"Exp {em_check:.1f} > {max_exp}")
            
        # Log Decision
        self.append_decision(bar, verdict, router_res, edge_score if verdict.decision=="GO" else 0.0, em_check, adx_m)
            
        # 5. Execution
        self.broker.mark_to_market(self.cfg["symbol"], bar.close)
        
        # Check Exits (Brackets)
        exit_fill = self.broker.check_brackets(self.cfg["symbol"], bar.high, bar.low, bar.timestamp)
        if exit_fill:
             print(f"CLOSE {exit_fill.side} @ {exit_fill.price:.2f} PnL:{exit_fill.pnl:.2f} ({exit_fill.event})")
             self.append_trade(exit_fill)
        
        if verdict.decision == "GO":
            # Risk calc matching CLI (approx)
            risk_pct = self.cfg["max_risk_trade_pct"] * r_risk_mult
            
            # SAFE PAPER: Enforce min floor if we are taking a trade (risk > 0 or safe_mode override)
            if risk_pct > 0 or self.cfg.get("safe_paper", False):
                 min_r = self.cfg.get("min_risk_pct", 0.1)
                 if risk_pct < min_r:
                     risk_pct = min_r # Bump to floor
            
            # Execute Strategy (Entry)
            # LOG DEBUG
            # print(f"DEBUG EXEC: RiskMult={r_risk_mult} RiskPct={risk_pct:.4f}")
            
            success, reason = self.broker.execute_strategy(
                symbol=self.cfg["symbol"],
                decision=verdict.decision,
                direction=verdict.direction,
                price=bar.close,
                timestamp=bar.timestamp,
                risk_pct=risk_pct,
                leverage=1.0 
            )
            
            if success:
                print(f"OPEN {verdict.direction} @ {bar.close} [Score:{edge_score:.2f}]")
                self.reporter.log_decision(verdict, mode_process=None, capital_profile="ACTIVE")
                if self.broker.trades: self.append_trade(self.broker.trades[-1])
            else:
                print(f"TRADE REJECTED: {reason} [RiskPct:{risk_pct*100:.2f}%]")
                # Also log to rejects for visibility
                self.append_reject(bar, "EXEC_FAIL", reason)

        # elif verdict.decision == "EXIT":
        #    # CLI/Council does not generate EXIT signals currently.
        #    pass
                
        # Update ATR
        if atr_m > 0: self.atr_history.append(atr_m)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon_id", type=str, default="STRICT")
    parser.add_argument("--run_dir", type=str, default="runs/phase19_twin/STRICT")
    parser.add_argument("--min_adx", type=float, default=35.0)
    parser.add_argument("--max_exp_move_bps", type=float, default=80.0)
    parser.add_argument("--soft_defense_override", action="store_true", help="Allow defense mode triggers with reduced risk.")
    parser.add_argument("--min_risk_pct", type=float, default=0.1, help="Minimum risk %% floor per trade")
    parser.add_argument("--safe_paper", action="store_true", help="Enable safe paper mode (min risk floor + defense override)")
    
    args = parser.parse_args()
    
    # Merge with Defaults
    cfg = DEFAULT_CONFIG.copy()
    cfg["daemon_id"] = args.daemon_id
    
    # Resolve Run Dir
    # If starting with /, assume absolute. Else relative to REPO_ROOT
    p = Path(args.run_dir)
    if not p.is_absolute():
        p = REPO_ROOT / args.run_dir
    cfg["run_dir"] = p
    
    cfg["min_adx"] = args.min_adx
    cfg["min_adx"] = args.min_adx
    cfg["max_exp_move_bps"] = args.max_exp_move_bps
    cfg["soft_defense_override"] = args.soft_defense_override
    cfg["min_risk_pct"] = args.min_risk_pct
    cfg["safe_paper"] = args.safe_paper
    if cfg["safe_paper"]:
        cfg["soft_defense_override"] = True # Implies override
    
    # Run ID
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cfg["run_id"] = f"phase19_twin_{ts}"
    
    # Update Namespace
    cfg["args"] = Namespace(
        symbol=cfg["symbol"],
        fee_bps=cfg["fee_bps"],
        slippage_bps=cfg["slippage_bps"],
        spread_bps=cfg["spread_bps"],
        min_adx=cfg["min_adx"],
        max_exp_move_bps=cfg["max_exp_move_bps"],
        vol_trap_mult=None,
        vol_trap_threshold=None,
        vol_trap_v2=False,
        quiet=False,
        min_expected_move_bps=cfg["min_expected_move_bps"],
        cost_safety_factor=cfg["cost_safety_factor"],
        cost_safety_homerun=cfg["cost_safety_homerun"],
        adaptive_cost_safety=cfg["adaptive_cost_safety"],
        atr_k=cfg["atr_k"], 
        adx_boost=cfg["adx_boost"],
        exp_cap_mult=cfg["exp_cap_mult"],
        min_expected_move_multiplier=cfg["min_expected_move_multiplier"]
    )
    
    print(f"Starting PaperDaemon [{cfg['daemon_id']}]")
    print(f"  MinADX: {cfg['min_adx']}")
    print(f"  RunDir: {cfg['run_dir']}")
    
    d = PaperDaemon(cfg)
    d.warmup()
    d.run_loop()
