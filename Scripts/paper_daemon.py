
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
from typing import Dict, Optional

# --- ABSOLUTE PATH SETUP ---
# Script is in scripts/, so repo_root is parent
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from argus_py.models.aegean.aegean import AegeanEngine
from argus_py.models.orion.orion import OrionEngine
from argus_py.council.aggregator import Council
from argus_py.council.defs import ConsensusVerdict
from argus_py.execution import UrgencyLevel
from argus_py.strategy.router import ModeRouter
from argus_py.strategy.tophunter_short import evaluate_tophunter_short_v1
from argus_py.risk.regime import RegimeDetector
from argus_py.runner.runtime_selector import select_runtime
from argus_py.strategy.lifecycle import StrategyState
from argus_py.strategy.registry_guard import StrategyRegistryGuard
from argus_py.broker.paper import PaperBroker, TradeFill
from argus_py.data.reporting import Reporter
from argus_py.data.market_state import Bar
from argus_py.telemetry.schema import TelemetryEvent
from argus_py.telemetry.reject_schema import normalize_reject, validate_reject
from argus_py.risk.kill_switch import KillSwitch, KillSwitchConfig, check_and_activate
from argus_py.ops.macro_event_guard import MacroEventGuard
from argus_py.ops.hermes_position_manager_v2 import HermesPositionManagerV2, urgency_from_score
from argus_py.ops.advisory_cards import write_advisory_card
from argus_py.portfolio.allocator import PortfolioAllocatorV1
from argus_py.portfolio.exposure_controller import ExposureController, ExposureLimits, PositionExposure
from argus_py.portfolio.optimizer import AllocationCandidate, OptimizerConstraints, PortfolioOptimizerV2
from argus_py.risk.correlation import CorrelationRiskMonitor
from argus_py.risk.entry_quality import EntryQualityScorer
from argus_py.risk.execution_quality_gate import ExecutionQualityGate, ExecutionQualityInput
from argus_py.ops.data_quality_sentinel import DataQualitySentinel
from argus_py.risk.regime_policy_packs import RegimePolicyResolver
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
    "soft_defense_override": False,
    "min_risk_pct": 0.1,
    "safe_paper": False,
    "mode": "legacy",
    "asset_class": "crypto",
    "venue_id": "auto",
    "macro_events_file": None,
    "strategy_registry_file": REPO_ROOT / "runs/year2/governance/strategy_registry.json",
    "disabled_strategies_file": REPO_ROOT / "runs/year2/governance/disabled_strategies.json",
    "allocator_risk_budget_pct": 1.0,
    "allocator_max_asset_exposure_pct": 35.0,
    "allocator_assumed_stop_loss_pct": 2.0,
    "correlation_threshold": 0.7,
    "correlation_min_scale": 0.3,
    "advisory_cards_enabled": True,
    "execution_quality_gate_enabled": True,
    "execution_quality_threshold": 0.55,
    "execution_quality_min_expected_move_bps": 3.0,
    "exposure_total_cap_pct": 90.0,
    "exposure_symbol_cap_pct": 35.0,
    "exposure_asset_cap_crypto_pct": 75.0,
    "exposure_asset_cap_stock_pct": 70.0,
    "exposure_asset_cap_defi_pct": 40.0,
    "data_quality_sentinel_enabled": True,
    "sentinel_degraded_threshold": 0.70,
    "sentinel_halt_threshold": 0.40,
    "regime_policy_pack": "legacy",
    "optimizer_enabled": True,
    "optimizer_gross_cap_pct": 100.0,
    "optimizer_per_symbol_cap_pct": 20.0,
    "optimizer_per_asset_cap_crypto_pct": 70.0,
    "optimizer_per_asset_cap_stock_pct": 70.0,
    "optimizer_per_asset_cap_defi_pct": 35.0,
    "optimizer_cvar_limit_pct": 2.5,
    # Strategy selection
    "strategy": "council",
    "tophunter_adx_max": 20.0,
    "tophunter_pivot_left": 2,
    "tophunter_pivot_right": 2,
    "tophunter_max_risk_trade_pct": 0.5,
    "tophunter_daily_loss_cap_pct": 1.5,
    "tophunter_max_open_positions": 1,
    "tophunter_loss_cooldown_bars": 3,
    "heartbeat_interval_sec": 5,
    
    # Config Objects Mock (Will be populated in main)
    "args": None
}

class PaperDaemon:
    def __init__(self, config):
        self.cfg = config
        self.mode_requested = str(self.cfg.get("mode", "legacy")).lower()
        self.mode = self.mode_requested
        self.runtime_boot_reason = "mode_unset"
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
        self.metrics_file = self.run_dir / "metrics.json"
        self.metrics_tmp = self.run_dir / "metrics.json.tmp"
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
            "errors_total": 0,
            "start_time_iso": datetime.now().isoformat()
        }
        self.last_heartbeat_push_ts = 0.0
        self.heartbeat_interval_sec = max(1, int(self.cfg.get("heartbeat_interval_sec", 5)))
        self.consecutive_losses = 0
        self.tophunter_cooldown_remaining = 0
        self.api_error_timestamps = deque(maxlen=2048)
        self.api_errors_1h = 0
        self.strategy_counters = {}
        self._touch_strategy_bucket(self._resolve_strategy_id(None))
        self.open_position_strategy: Dict[str, str] = {}
        self.v2_bridge = None
        self.last_v2_snapshot = None
        self.asset_router = None
        self._asset_tags = {
            "asset_class": str(self.cfg.get("asset_class", "crypto")).lower(),
            "venue_id": str(self.cfg.get("venue_id", "auto")).lower(),
            "asset_class_requested": str(self.cfg.get("asset_class", "crypto")).lower(),
            "venue_id_requested": str(self.cfg.get("venue_id", "auto")).lower(),
            "adapter_id": "legacy",
        }
        self._last_engine_signals = {
            "orion": 0.0,
            "aegean": 0.0,
            "atlas": 0.0,
            "aether": 0.0,
            "hermes": 0.0,
        }
        self._risk_sizing = {
            "allocator_reason": "N/A",
            "allocator_allowed_risk_pct": 0.0,
            "correlation_scale": 1.0,
            "correlation_max_abs": 0.0,
            "correlation_reason": "N/A",
            "exposure_scale": 1.0,
            "exposure_reason": "N/A",
        }
        self._last_execution_quality = None
        self._last_sentinel = None
        self._last_regime_policy = None
        self._last_optimizer = None
        self._pnl_attribution = {
            "by_strategy": {},
            "by_asset_class": {},
            "by_venue": {},
        }
        self.event_counters = {
            "macro_blocks_total": 0,
            "strategy_disabled_blocks_total": 0,
            "hermes_actions_total": 0,
            "advisory_cards_total": 0,
            "execution_quality_blocks_total": 0,
            "sentinel_halts_total": 0,
            "exposure_blocks_total": 0,
            "optimizer_blocks_total": 0,
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
        self.current_day = None
        self.day_start_equity = initial_balance
        self.daily_stop_active = False
        self.kill_switch_active = False
        self.kill_switch_state_file = self.run_dir / "kill_switch_state.json"
        
        # 3. Components
        self.reporter = Reporter(str(self.run_dir))
        self.broker = PaperBroker(
            start_balance=initial_balance,
            mode="paper",
            reporter=self.reporter
        )
        ks_cfg = KillSwitchConfig(
            soft_daily_loss_pct=self.cfg["daily_loss_limit_pct"],
            halt_dd_pct=self.cfg["kill_switch_dd_pct"]
        )
        self.kill_switch = KillSwitch.load_state(self.kill_switch_state_file, config=ks_cfg)
        
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
        self.macro_guard = MacroEventGuard(self._macro_events_path())
        self.strategy_registry_guard = StrategyRegistryGuard(
            paths=[
                Path(self.cfg.get("strategy_registry_file")),
                Path(self.cfg.get("disabled_strategies_file")),
            ]
        )
        self.hermes_position_manager = HermesPositionManagerV2(self.broker)
        self.allocator = PortfolioAllocatorV1(
            risk_budget_pct=float(self.cfg.get("allocator_risk_budget_pct", 1.0)),
            max_asset_exposure_pct=float(self.cfg.get("allocator_max_asset_exposure_pct", 35.0)),
            assumed_stop_loss_pct=float(self.cfg.get("allocator_assumed_stop_loss_pct", 2.0)),
        )
        self.correlation_monitor = CorrelationRiskMonitor(
            threshold=float(self.cfg.get("correlation_threshold", 0.7)),
            min_scale=float(self.cfg.get("correlation_min_scale", 0.3)),
        )
        self.entry_quality_scorer = EntryQualityScorer(
            min_quality_threshold=float(self.cfg.get("execution_quality_threshold", 0.55))
        )
        self.execution_quality_gate = ExecutionQualityGate(
            threshold=float(self.cfg.get("execution_quality_threshold", 0.55)),
            min_expected_move_bps=float(self.cfg.get("execution_quality_min_expected_move_bps", 3.0)),
            max_slippage_bps=float(self.cfg.get("slippage_bps", 2.0)) * 3.0,
            max_spread_bps=float(self.cfg.get("spread_bps", 1.0)) * 4.0,
        )
        self.exposure_controller = ExposureController(
            limits=ExposureLimits(
                total_cap_pct=float(self.cfg.get("exposure_total_cap_pct", 90.0)),
                per_symbol_cap_pct=float(self.cfg.get("exposure_symbol_cap_pct", 35.0)),
                per_asset_caps_pct={
                    "crypto": float(self.cfg.get("exposure_asset_cap_crypto_pct", 75.0)),
                    "stock": float(self.cfg.get("exposure_asset_cap_stock_pct", 70.0)),
                    "defi": float(self.cfg.get("exposure_asset_cap_defi_pct", 40.0)),
                },
            )
        )
        self.data_quality_sentinel = DataQualitySentinel(
            interval=str(self.cfg.get("interval", "1m")),
            degraded_threshold=float(self.cfg.get("sentinel_degraded_threshold", 0.70)),
            halt_threshold=float(self.cfg.get("sentinel_halt_threshold", 0.40)),
        )
        self.regime_policy_resolver = RegimePolicyResolver(str(self.cfg.get("regime_policy_pack", "legacy")))
        self.portfolio_optimizer = PortfolioOptimizerV2(
            constraints=OptimizerConstraints(
                gross_cap_pct=float(self.cfg.get("optimizer_gross_cap_pct", 100.0)),
                per_symbol_cap_pct=float(self.cfg.get("optimizer_per_symbol_cap_pct", 20.0)),
                per_asset_cap_pct={
                    "crypto": float(self.cfg.get("optimizer_per_asset_cap_crypto_pct", 70.0)),
                    "stock": float(self.cfg.get("optimizer_per_asset_cap_stock_pct", 70.0)),
                    "defi": float(self.cfg.get("optimizer_per_asset_cap_defi_pct", 35.0)),
                },
                cvar_limit_pct=float(self.cfg.get("optimizer_cvar_limit_pct", 2.5)),
            )
        )
        runtime = select_runtime(self.cfg, self.run_dir, self.broker)
        self.mode = runtime.final_mode
        self.runtime_boot_reason = runtime.reason
        self.asset_router = runtime.asset_router
        self.v2_bridge = runtime.v2_bridge
        self._asset_tags = runtime.asset_tags
        if self.mode == "v2":
            print("V2_RUNTIME: enabled (MODE=v2)")
        else:
            print(f"V2_RUNTIME: disabled (MODE=legacy) reason={self.runtime_boot_reason}")
            if self.mode_requested == "v2":
                print("V2_RUNTIME: requested v2 but falling back to legacy for safety.")
        
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

    def _macro_events_path(self) -> Optional[Path]:
        cfg_path = self.cfg.get("macro_events_file")
        if cfg_path:
            p = Path(cfg_path)
            if not p.is_absolute():
                p = REPO_ROOT / p
            return p
        default_path = self.run_dir / "macro_events.json"
        return default_path

    def _strategy_registry_disabled(self, strategy_id: str) -> tuple[bool, str]:
        try:
            return self.strategy_registry_guard.is_disabled(strategy_id)
        except Exception as exc:
            return False, f"registry_guard_error:{exc}"

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
                    "min_adx": self.cfg["min_adx"],
                    "strategy": self.cfg.get("strategy", "council"),
                    "mode": self.mode,
                    "mode_requested": self.mode_requested,
                    "mode_final": self.mode,
                    "runtime_boot_reason": self.runtime_boot_reason,
                    "asset_class": self.cfg.get("asset_class", "crypto"),
                    "venue_id": self.cfg.get("venue_id", "auto"),
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
        self.health["errors_total"] += 1
        if self.v2_bridge is not None:
            try:
                self.v2_bridge.open_incident(
                    title=f"PaperDaemon error: {context}",
                    context={
                        "errors_total": self.health["errors_total"],
                        "consecutive_errors": self.health["consecutive_errors"],
                    },
                )
            except Exception:
                pass
        with open(self.error_log, "a") as f:
            f.write(f"--- ERROR in {context} @ {datetime.now()} ---\n")
            traceback.print_exc(file=f)
        traceback.print_exc()
        # Force heartbeat+metrics update to reflect error state.
        hb_bar = self.history_bars[-1] if self.history_bars else None
        self._maybe_write_heartbeat(last_bar=hb_bar, force=True)

    def _resolve_strategy_id(self, strategy_tags):
        if strategy_tags and strategy_tags.get("strategy_id"):
            return str(strategy_tags.get("strategy_id")).strip() or "UNKNOWN_STRATEGY"
        strategy_name = str(self.cfg.get("strategy", "council")).lower()
        if strategy_name == "tophunter_short_v1":
            return "TOPHUNTER_SHORT_V1"
        if strategy_name == "council":
            return "COUNCIL_BASELINE"
        return strategy_name.upper() if strategy_name else "UNKNOWN_STRATEGY"

    def _touch_strategy_bucket(self, strategy_id):
        sid = strategy_id or "UNKNOWN_STRATEGY"
        if sid not in self.strategy_counters:
            self.strategy_counters[sid] = {
                "decisions": 0,
                "rejects": 0,
                "trades": 0,
            }
        return sid

    def _add_pnl_bucket(self, bucket: str, key: str, pnl: float):
        if bucket not in self._pnl_attribution:
            self._pnl_attribution[bucket] = {}
        m = self._pnl_attribution[bucket]
        if key not in m:
            m[key] = {"trades": 0, "realized_pnl": 0.0}
        m[key]["trades"] += 1
        m[key]["realized_pnl"] += float(pnl)

    def _broker_position_exposures(self, market_price: float) -> list[PositionExposure]:
        out: list[PositionExposure] = []
        asset_class = str(self._asset_tags.get("asset_class", self.cfg.get("asset_class", "crypto")))
        for symbol, pos in getattr(self.broker, "details", {}).items():
            qty = abs(float(getattr(pos, "quantity", 0.0)))
            notional = qty * float(market_price)
            if notional <= 0:
                continue
            out.append(PositionExposure(symbol=str(symbol), asset_class=asset_class, notional=notional))
        return out

    def _estimate_volatility_bps(self) -> float:
        closes = [float(b.close) for b in self.history_bars[-120:]]
        if len(closes) < 8:
            return 60.0
        series = pd.Series(closes, dtype=float)
        rets = series.pct_change().dropna()
        if rets.empty:
            return 60.0
        std = float(rets.std(ddof=1))
        if not np.isfinite(std):
            return 60.0
        return max(5.0, std * 10000.0)

    def _write_metrics(self, last_bar=None):
        last_bar_iso = None
        if last_bar is not None:
            try:
                last_bar_iso = datetime.fromtimestamp(last_bar.timestamp).isoformat()
            except Exception:
                last_bar_iso = None
        payload = {
            "ts_iso": datetime.now().isoformat(),
            "run_id": self.cfg.get("run_id", "unknown"),
            "daemon_id": self.cfg.get("daemon_id", "UNKNOWN"),
            "mode": self.mode,
            "mode_requested": self.mode_requested,
            "mode_final": self.mode,
            "runtime_boot_reason": self.runtime_boot_reason,
            "strategy_mode": self.cfg.get("strategy", "council"),
            "last_closed_bar_iso": last_bar_iso,
            "bars_seen": self.counters.get("bars_seen", 0),
            "decisions_total": self.counters.get("decisions_total", 0),
            "trades_total": self.counters.get("trades_total", 0),
            "rejects_total": self.counters.get("rejects_total", 0),
            "errors_total": self.health.get("errors_total", 0),
            "last_error": self.health.get("last_error"),
            "api_errors_1h": self.api_errors_1h,
            "risk_level": self.kill_switch.get_level().value,
            "strategy_id_breakdown": self.strategy_counters,
            "event_counters": self.event_counters,
            "risk_sizing": self._risk_sizing,
            "asset_class": self._asset_tags.get("asset_class"),
            "venue_id": self._asset_tags.get("venue_id"),
            "asset_class_requested": self._asset_tags.get("asset_class_requested"),
            "venue_id_requested": self._asset_tags.get("venue_id_requested"),
            "asset_adapter_id": self._asset_tags.get("adapter_id"),
            "execution_quality": self._last_execution_quality,
            "sentinel": self._last_sentinel,
            "regime_policy": self._last_regime_policy,
            "optimizer": self._last_optimizer,
            "pnl_attribution_live": self._pnl_attribution,
        }
        if self.v2_bridge is not None:
            payload["v2"] = self.v2_bridge.metrics_payload()
        with open(self.metrics_tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(self.metrics_tmp, self.metrics_file)

    def _maybe_write_heartbeat(self, last_bar=None, force=False):
        now = time.time()
        should_write = force or ((now - self.last_heartbeat_push_ts) >= self.heartbeat_interval_sec)
        if not should_write:
            return
        self.update_heartbeat(last_bar=last_bar)
        self.last_heartbeat_push_ts = now

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
        self.trades_csv_mode = "extended"
        if self.trades_csv.exists():
            try:
                head = self.trades_csv.read_text(encoding="utf-8").splitlines()[0].strip().lower()
            except Exception:
                head = ""
            if head == "ts_iso,symbol,side,price,qty,pnl,event":
                self.trades_csv_mode = "legacy"
        else:
            with open(self.trades_csv, "w") as f:
                f.write(
                    "ts_iso,symbol,side,price,qty,commission,pnl,event,mark_price,fill_price,slip_applied,spread_applied,asset_class,venue_id,strategy_id\n"
                )

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
                    "min_adx": self.cfg["min_adx"],
                    "mode": self.mode,
                    "mode_requested": self.mode_requested,
                    "mode_final": self.mode,
                    "runtime_boot_reason": self.runtime_boot_reason,
                    "asset_class": self._asset_tags.get("asset_class"),
                    "venue_id": self._asset_tags.get("venue_id"),
                    "asset_adapter_id": self._asset_tags.get("adapter_id"),
                },
                "risk_level": self.kill_switch.get_level().value,
                "health": {
                    "stale_seconds": 0, # Calculated by consumer
                    "last_error": self.health["last_error"],
                    "consecutive_errors": self.health["consecutive_errors"],
                    "errors_total": self.health["errors_total"],
                    "uptime_start": self.health["start_time_iso"]
                }
            }
            if self.v2_bridge is not None:
                hb["v2"] = self.v2_bridge.metrics_payload()
            
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
            self._write_metrics(last_bar=last_bar)
            
        except Exception as e:
            print(f"Heartbeat Error: {e}")

    def _refresh_api_error_count(self):
        now = time.time()
        self.api_errors_1h = sum(1 for ts in self.api_error_timestamps if (now - ts) <= 3600.0)

    def _record_api_error(self):
        self.api_error_timestamps.append(time.time())
        self._refresh_api_error_count()

    def _persist_kill_switch(self):
        try:
            self.kill_switch.save_state(self.run_dir / "kill_switch_state.json")
        except Exception:
            self.log_error("SAVE_KILL_SWITCH_FAILED")

    @staticmethod
    def _format_strategy_tags(strategy_tags):
        if not strategy_tags:
            return ""
        return "|".join(f"{k}={v}" for k, v in strategy_tags.items())

    def _apply_kill_switch_guard(self, bar: Bar, daily_pnl_pct: float, current_dd_pct: float) -> bool:
        metrics = {
            'daily_pnl_pct': daily_pnl_pct,
            'total_dd_pct': current_dd_pct,
            'consecutive_losses': self.consecutive_losses,
            'api_errors_1h': self.api_errors_1h
        }
        level = check_and_activate(self.kill_switch, metrics)

        if self.kill_switch.should_close_all() and self.broker.details:
            close_map = {self.cfg["symbol"]: bar.close}
            if hasattr(self.broker, "close_all"):
                closed = self.broker.close_all(bar.timestamp, close_map)
            else:
                closed = self.broker.close_all_positions(bar.timestamp, close_map)
            for fill in closed:
                self.append_trade(fill)

        if not self.kill_switch.can_trade():
            self.append_reject(bar, "REJECT_KILL_SWITCH", f"Level: {level.value}")
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "REJECT_KILL_SWITCH", f"Level: {level.value}")
            self.kill_switch_active = level.value in {"HARD", "HALT"}
            return True
        return False

    def _current_asset_exposure_pct(self, market_price: float) -> float:
        pos = self.broker.details.get(self.cfg["symbol"])
        if pos is None:
            return 0.0
        notional = abs(float(pos.quantity) * float(market_price))
        equity = max(1e-9, float(self.broker.equity))
        return (notional / equity) * 100.0

    def _apply_v2_risk_sizing(
        self,
        risk_pct: float,
        market_price: float,
        *,
        expected_move_bps: float = 0.0,
        edge_score: float = 0.0,
    ) -> tuple[float, Optional[str]]:
        requested = max(0.0, float(risk_pct))
        if self.mode != "v2":
            self._risk_sizing = {
                "allocator_reason": "legacy_mode",
                "allocator_allowed_risk_pct": requested * 100.0,
                "correlation_scale": 1.0,
                "correlation_max_abs": 0.0,
                "correlation_reason": "legacy_mode",
                "exposure_scale": 1.0,
                "exposure_reason": "legacy_mode",
                "optimizer_scale": 1.0,
                "optimizer_reason": "legacy_mode",
            }
            return requested, None

        exposure_pct = self._current_asset_exposure_pct(market_price)
        alloc = self.allocator.allocate_single_asset(
            requested_risk_pct=requested,
            current_asset_exposure_pct=exposure_pct,
        )
        if alloc.blocked:
            self._risk_sizing = {
                "allocator_reason": alloc.reason,
                "allocator_allowed_risk_pct": 0.0,
                "correlation_scale": 1.0,
                "correlation_max_abs": 0.0,
                "correlation_reason": "allocator_blocked",
                "exposure_scale": 0.0,
                "exposure_reason": "allocator_blocked",
                "optimizer_scale": 0.0,
                "optimizer_reason": "allocator_blocked",
            }
            return 0.0, alloc.reason

        allowed = float(alloc.allowed_risk_pct) / 100.0
        corr_scale = 1.0
        corr_max_abs = 0.0
        corr_reason = "insufficient_history"
        try:
            closes = [float(b.close) for b in self.history_bars[-180:]]
            if len(closes) >= 40:
                base = pd.Series(closes, dtype=float)
                prices = pd.DataFrame(
                    {
                        self.cfg["symbol"]: base.values,
                        "BENCH_SYNTH": base.rolling(window=5, min_periods=1).mean().values,
                    }
                )
                notional = {
                    self.cfg["symbol"]: max(0.0, float(self.broker.equity) * allowed),
                    "BENCH_SYNTH": max(0.0, float(self.broker.equity) * allowed),
                }
                _, details = self.correlation_monitor.scale_positions(prices, notional)
                det = details.get(self.cfg["symbol"])
                if det is not None:
                    corr_scale = float(det.scale)
                    corr_max_abs = float(det.max_abs_corr)
                    corr_reason = str(det.reason)
        except Exception as exc:
            corr_reason = f"correlation_error:{exc}"
            corr_scale = 1.0
            corr_max_abs = 0.0

        final_risk = max(0.0, allowed * corr_scale)
        stop_ratio = max(0.0001, float(self.cfg.get("allocator_assumed_stop_loss_pct", 2.0)) / 100.0)
        candidate_notional = (float(self.broker.equity) * final_risk) / stop_ratio
        exposure_decision = self.exposure_controller.decide(
            equity=float(self.broker.equity),
            existing_positions=self._broker_position_exposures(market_price),
            candidate_symbol=str(self.cfg["symbol"]),
            candidate_asset_class=str(self._asset_tags.get("asset_class", self.cfg.get("asset_class", "crypto"))),
            candidate_notional=max(0.0, candidate_notional),
        )
        if not exposure_decision.accepted:
            self._risk_sizing = {
                "allocator_reason": alloc.reason,
                "allocator_allowed_risk_pct": float(alloc.allowed_risk_pct),
                "correlation_scale": corr_scale,
                "correlation_max_abs": corr_max_abs,
                "correlation_reason": corr_reason,
                "exposure_scale": 0.0,
                "exposure_reason": exposure_decision.reason,
                "optimizer_scale": 0.0,
                "optimizer_reason": "exposure_blocked",
            }
            self.event_counters["exposure_blocks_total"] += 1
            return 0.0, f"EXPOSURE_BLOCK:{exposure_decision.reason}"
        final_risk = max(0.0, final_risk * float(exposure_decision.scale))

        optimizer_scale = 1.0
        optimizer_reason = "DISABLED"
        optimizer_cvar = 0.0
        if bool(self.cfg.get("optimizer_enabled", True)):
            try:
                candidate_weight_pct = (candidate_notional / max(1e-9, float(self.broker.equity))) * 100.0
                score_for_opt = max(1.0, float(edge_score) if edge_score > 0 else 50.0)
                expected_for_opt = max(0.5, float(expected_move_bps) if expected_move_bps > 0 else 5.0)
                vol_bps = self._estimate_volatility_bps()
                opt = self.portfolio_optimizer.optimize(
                    [
                        AllocationCandidate(
                            symbol=str(self.cfg["symbol"]),
                            asset_class=str(self._asset_tags.get("asset_class", self.cfg.get("asset_class", "crypto"))),
                            signal_score=score_for_opt,
                            expected_return_bps=expected_for_opt,
                            volatility_bps=vol_bps,
                        )
                    ]
                )
                target_weight = float(opt.target_weights_pct.get(str(self.cfg["symbol"]), 0.0))
                if candidate_weight_pct > 0:
                    optimizer_scale = max(0.0, min(1.0, target_weight / candidate_weight_pct))
                else:
                    optimizer_scale = 1.0
                optimizer_reason = str(opt.reason)
                optimizer_cvar = float(opt.cvar_proxy_pct)
                self._last_optimizer = {
                    "target_weight_pct": target_weight,
                    "candidate_weight_pct": candidate_weight_pct,
                    "total_weight_pct": float(opt.total_weight_pct),
                    "cvar_proxy_pct": optimizer_cvar,
                    "scale": optimizer_scale,
                    "reason": optimizer_reason,
                }
                if optimizer_scale <= 0.0:
                    self.event_counters["optimizer_blocks_total"] += 1
                    return 0.0, "OPTIMIZER_BLOCK"
                final_risk = max(0.0, final_risk * optimizer_scale)
            except Exception as exc:
                optimizer_scale = 1.0
                optimizer_reason = f"optimizer_error:{exc}"
                self._last_optimizer = {
                    "scale": optimizer_scale,
                    "reason": optimizer_reason,
                }
        else:
            self._last_optimizer = {
                "scale": 1.0,
                "reason": "optimizer_disabled",
            }

        self._risk_sizing = {
            "allocator_reason": alloc.reason,
            "allocator_allowed_risk_pct": float(alloc.allowed_risk_pct),
            "correlation_scale": corr_scale,
            "correlation_max_abs": corr_max_abs,
            "correlation_reason": corr_reason,
            "exposure_scale": float(exposure_decision.scale),
            "exposure_reason": exposure_decision.reason,
            "optimizer_scale": float(optimizer_scale),
            "optimizer_reason": optimizer_reason,
            "optimizer_cvar_proxy_pct": float(optimizer_cvar),
            "exposure_snapshot": {
                "total_exposure_pct": exposure_decision.snapshot.total_exposure_pct,
                "symbol_exposure_pct": exposure_decision.snapshot.symbol_exposure_pct,
                "asset_exposure_pct": exposure_decision.snapshot.asset_exposure_pct,
            },
        }
        return final_risk, None

    def _apply_macro_guard(self, bar: Bar, verdict, strategy_tags=None):
        if self.mode != "v2" or verdict.decision != "GO":
            return verdict
        block, detail = self.macro_guard.should_block_entry(
            ts=float(bar.timestamp),
            asset_class=str(self._asset_tags.get("asset_class", self.cfg.get("asset_class", "crypto"))),
            symbol=str(self.cfg.get("symbol", "")),
        )
        if not block:
            return verdict
        verdict.decision = "BLOCK"
        self.event_counters["macro_blocks_total"] += 1
        self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "MACRO_EVENT_BLACKOUT", detail)
        self.append_reject(bar, "MACRO_EVENT_BLACKOUT", detail, strategy_tags=strategy_tags)
        return verdict

    def _apply_strategy_disable_guard(self, bar: Bar, verdict, strategy_tags=None):
        if self.mode != "v2" or verdict.decision != "GO":
            return verdict
        strategy_id = self._resolve_strategy_id(strategy_tags)
        disabled, reason = self._strategy_registry_disabled(strategy_id)
        if not disabled:
            return verdict
        verdict.decision = "BLOCK"
        self.event_counters["strategy_disabled_blocks_total"] += 1
        detail = f"{strategy_id}: {reason}"
        self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "STRATEGY_DISABLED", detail)
        self.append_reject(bar, "STRATEGY_DISABLED", detail, strategy_tags=strategy_tags)
        return verdict

    def _apply_hermes_position_actions(self, bar: Bar):
        if self.mode != "v2":
            return
        if self.last_v2_snapshot is None:
            return
        if not self.broker.details:
            return
        score = float(self.last_v2_snapshot.hermes_score)
        urgency = urgency_from_score(score)
        for symbol in list(self.broker.details.keys()):
            try:
                outcome = self.hermes_position_manager.apply(
                    symbol=symbol,
                    sentiment_score=score,
                    urgency=urgency,
                    market_price=float(bar.close),
                    timestamp=float(bar.timestamp),
                )
                if not outcome.handled:
                    continue
                self.event_counters["hermes_actions_total"] += 1
                if outcome.action == "CLOSE_POSITION":
                    fill = self.broker.trades[-1] if self.broker.trades else None
                    if fill is not None:
                        self.append_trade(fill, strategy_tags={"strategy_id": self.open_position_strategy.get(symbol, "UNKNOWN_STRATEGY")})
            except Exception:
                self.log_error("HERMES_POSITION_ACTION_FAILED")

    def _emit_advisory_card(self, bar: Bar, verdict, strategy_tags, stop_price: Optional[float], tp_price: Optional[float]):
        if self.mode != "v2":
            return
        if not bool(self.cfg.get("advisory_cards_enabled", True)):
            return
        if verdict.decision != "GO":
            return
        try:
            strategy_id = self._resolve_strategy_id(strategy_tags)
            if tp_price is None:
                tp_price = float(bar.close) * (1.04 if str(verdict.direction).upper() == "BUY" else 0.96)
            if stop_price is None:
                stop_price = float(bar.close) * (0.98 if str(verdict.direction).upper() == "BUY" else 1.02)
            tp_levels = [tp_price] if tp_price is not None else []
            out = write_advisory_card(
                run_dir=self.run_dir,
                symbol=self.cfg["symbol"],
                side=verdict.direction,
                entry_price=float(bar.close),
                stop_price=stop_price,
                take_profit_levels=tp_levels,
                rationale=str(verdict.rationale),
                strategy_id=strategy_id,
                asset_class=str(self._asset_tags.get("asset_class", self.cfg.get("asset_class", "crypto"))),
                venue_id=str(self._asset_tags.get("venue_id", self.cfg.get("venue_id", "auto"))),
                bar_timestamp=float(bar.timestamp),
                quality_score=(self._last_execution_quality or {}).get("score"),
                quality_grade=(self._last_execution_quality or {}).get("grade"),
            )
            self.event_counters["advisory_cards_total"] += 1
        except Exception:
            self.log_error("ADVISORY_CARD_FAILED")

    def append_decision(self, bar, verdict, router_res, score, exp_move, adx, strategy_tags=None):
        self.counters["decisions_total"] += 1
        sid = self._touch_strategy_bucket(self._resolve_strategy_id(strategy_tags))
        self.strategy_counters[sid]["decisions"] += 1
        ts_iso = datetime.now().isoformat()
        bar_ts_iso = datetime.fromtimestamp(bar.timestamp).isoformat()
        reasons = verdict.metadata.get("block_reason", "")
        tags_text = self._format_strategy_tags(strategy_tags)
        if tags_text:
            reasons = f"{reasons};{tags_text}" if reasons else tags_text
        
        # CSV (Legacy/UI quick view)
        row = f"{ts_iso},{bar_ts_iso},{self.cfg['symbol']},{verdict.regime},{router_res['mode_final']},{verdict.decision},{verdict.direction},{score:.2f},{exp_move:.1f},{adx:.1f},{reasons}\n"
        with open(self.decisions_csv, "a") as f:
            f.write(row)
            
        # JSONL (Truth)
        reasons_list = [reasons] if reasons else []
        params_payload = {
            "max_exp_move_bps": self.cfg["max_exp_move_bps"],
            "min_adx": self.cfg["min_adx"],
            "asset_class": self._asset_tags.get("asset_class"),
            "venue_id": self._asset_tags.get("venue_id"),
        }
        if strategy_tags:
            params_payload.update(strategy_tags)
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
            params=params_payload,
            reasons=reasons_list
        )
        with open(self.decisions_jsonl, "a") as f:
            f.write(json.dumps(event) + "\n")
        if self.v2_bridge is not None:
            self.v2_bridge.on_decision(event)

    def append_reject(self, bar, code, detail, strategy_tags=None):
        code, detail = normalize_reject(code, detail)
        try:
            validate_reject(code, detail)
        except Exception as e:
            code = "REJECT_SCHEMA_INVALID"
            detail = f"Schema validation failed: {e}"
        self.counters["rejects_total"] += 1
        sid = self._touch_strategy_bucket(self._resolve_strategy_id(strategy_tags))
        self.strategy_counters[sid]["rejects"] += 1
        ts_iso = datetime.now().isoformat()
        bar_ts_iso = datetime.fromtimestamp(bar.timestamp).isoformat()
        tags_text = self._format_strategy_tags(strategy_tags)
        if tags_text:
            detail = f"{detail} | {tags_text}" if detail else tags_text
        
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
            snapshot={
                "strategy_tags": strategy_tags or {},
                "asset_class": self._asset_tags.get("asset_class"),
                "venue_id": self._asset_tags.get("venue_id"),
            } # Could enrich later
        )
        with open(self.rejects_jsonl, "a") as f:
            f.write(json.dumps(event) + "\n")
        if self.v2_bridge is not None:
            self.v2_bridge.on_reject(event)
            
    def append_trade(self, fill, strategy_tags=None):
        self.counters["trades_total"] += 1
        sid = self._touch_strategy_bucket(self._resolve_strategy_id(strategy_tags))
        self.strategy_counters[sid]["trades"] += 1
        ts_iso = datetime.now().isoformat()

        mark_price = float(getattr(fill, "mark_price", fill.price))
        fill_price = float(getattr(fill, "fill_price", fill.price))
        slip_applied = float(getattr(fill, "slip_applied", 0.0))
        spread_applied = float(getattr(fill, "spread_applied", 0.0))
        commission = float(getattr(fill, "commission", 0.0))

        # CSV
        if getattr(self, "trades_csv_mode", "extended") == "legacy":
            row = f"{ts_iso},{fill.symbol},{fill.side},{fill.price:.2f},{fill.quantity:.4f},{fill.pnl:.2f},{fill.event}\n"
        else:
            row = (
                f"{ts_iso},{fill.symbol},{fill.side},{fill.price:.8f},{fill.quantity:.8f},{commission:.8f},"
                f"{fill.pnl:.8f},{fill.event},{mark_price:.8f},{fill_price:.8f},{slip_applied:.8f},"
                f"{spread_applied:.8f},{self._asset_tags.get('asset_class')},{self._asset_tags.get('venue_id')},{sid}\n"
            )
        with open(self.trades_csv, "a") as f:
            f.write(row)
            
        # JSONL
        # Split open/close based on fill event or PnL?
        # Fill event usually 'ENTRY' or 'STOP'/'PROFIT'.
        # Assuming broker fills structure.
        if fill.pnl == 0.0 and str(fill.event).upper() in {"ENTRY", "SIGNAL", "OPEN"}:
            event = TelemetryEvent.trade_open(
                daemon_id=self.cfg["daemon_id"],
                run_id=self.cfg.get("run_id", "unknown"),
                symbol=fill.symbol,
                interval=self.cfg["interval"],
                bar_ts=None, # timestamp in fill?
                entry_price=fill.price,
                qty=fill.quantity,
                side=fill.side,
                fees_model="legacy",
                asset_class=self._asset_tags.get("asset_class"),
                venue_id=self._asset_tags.get("venue_id"),
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
                reason=fill.event,
                asset_class=self._asset_tags.get("asset_class"),
                venue_id=self._asset_tags.get("venue_id"),
            )
        with open(self.trades_jsonl, "a") as f:
            f.write(json.dumps(event) + "\n")
        if self.v2_bridge is not None:
            payload = {
                "symbol": fill.symbol,
                "side": fill.side,
                "price": fill.price,
                "qty": fill.quantity,
                "pnl": fill.pnl,
                "event": fill.event,
                "timestamp": fill.timestamp,
            }
            self.v2_bridge.on_trade(payload)
            if abs(float(fill.pnl)) > 1e-12:
                regime = self.last_v2_snapshot.regime_v2 if self.last_v2_snapshot is not None else "LOW_VOL_CALM"
                self.v2_bridge.observe_trade(
                    regime=regime,
                    engine_signals=self._last_engine_signals,
                    pnl=float(fill.pnl),
                    timestamp=float(fill.timestamp),
                )
        if abs(float(fill.pnl)) > 1e-12:
            self._add_pnl_bucket("by_strategy", sid, float(fill.pnl))
            self._add_pnl_bucket(
                "by_asset_class",
                str(self._asset_tags.get("asset_class", self.cfg.get("asset_class", "unknown"))),
                float(fill.pnl),
            )
            self._add_pnl_bucket(
                "by_venue",
                str(self._asset_tags.get("venue_id", self.cfg.get("venue_id", "unknown"))),
                float(fill.pnl),
            )
        # Keep position-strategy map aligned with broker state.
        if str(fill.event).upper() in {"OPEN", "ENTRY"}:
            self.open_position_strategy[str(fill.symbol)] = sid
        elif str(fill.event).upper() not in {"REJECTED"}:
            self.open_position_strategy.pop(str(fill.symbol), None)

    def fetch_klines(self, limit=100):
        if self.mode == "v2" and self.asset_router is not None:
            try:
                bars = self.asset_router.fetch_klines(
                    symbol=self.cfg["symbol"],
                    interval=self.cfg["interval"],
                    limit=int(limit),
                    now_ts=time.time(),
                )
                self._asset_tags = self.asset_router.telemetry_tags()
                if bars:
                    return bars
                # keep loop alive; fallback to legacy fetch only for crypto routes
                if self._asset_tags.get("asset_class") != "crypto":
                    return []
            except Exception as exc:
                # Backend failure must never crash daemon.
                self._asset_tags = {
                    **self._asset_tags,
                    "router_error": str(exc),
                }
                return []

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
        
        try:
            while True:
                heartbeat_bar = self.history_bars[-1] if self.history_bars else None
                try:
                    # 2. Fetch Data
                    klines = self.fetch_klines(limit=2)
                    if not klines:
                        self._record_api_error()
                        time.sleep(10)
                        continue
                    self._refresh_api_error_count()
                    
                    # Close Logic: index 0 is N-1 (Closed), index 1 is N (Open)
                    # Ensure we process closed bar
                    candidate_bar = klines[0]
                    
                    if candidate_bar.timestamp > last_ts:
                        print(f"[{datetime.fromtimestamp(candidate_bar.timestamp)}] New Closed Bar: {candidate_bar.close}")
                        self.process_bar(candidate_bar)
                        if self.kill_switch.should_disconnect():
                            print("KILL SWITCH HALT ACTIVE. Stopping daemon loop.")
                            self.save_state("kill_switch_halt")
                            break
                        last_ts = candidate_bar.timestamp
                        heartbeat_bar = candidate_bar
                        self.save_state("new_bar_processed")
                        self.health["consecutive_errors"] = 0 # Reset health on success
                        
                        with open(self.hb_log, "a") as f:
                            entry = f"HEARTBEAT: {datetime.now().isoformat()} last_bar_ts={last_ts} equity={self.broker.equity:.2f} pos={len(self.broker.details)}\n"
                            f.write(entry)
                            
                    time.sleep(5) 
                    
                except KeyboardInterrupt:
                    print("Stopping...")
                    self.save_state("shutdown")
                    break
                except Exception:
                    self.log_error("RUN_LOOP_EXCEPTION")
                    self._record_api_error()
                    time.sleep(10)
                finally:
                    self._maybe_write_heartbeat(last_bar=heartbeat_bar)
        finally:
            self._persist_kill_switch()
                
    def process_bar(self, bar: Bar):
        self.counters["bars_seen"] += 1
        self.history_bars.append(bar)
        if len(self.history_bars) > 2000:
            self.history_bars.pop(0) 

        sentinel_score = 1.0
        sentinel_halt = False
        if self.mode == "v2" and bool(self.cfg.get("data_quality_sentinel_enabled", True)):
            try:
                sentinel = self.data_quality_sentinel.evaluate(self.history_bars, now_ts=time.time())
                sentinel_score = float(sentinel.score)
                sentinel_halt = bool(sentinel.halt_new_entries)
                self._last_sentinel = {
                    "score": sentinel.score,
                    "band": sentinel.band,
                    "reason": sentinel.reason,
                }
                if sentinel_halt:
                    self.event_counters["sentinel_halts_total"] += 1
            except Exception as exc:
                sentinel_halt = True
                self._last_sentinel = {
                    "score": 0.0,
                    "band": "HALT",
                    "reason": f"sentinel_error:{exc}",
                }
                self.event_counters["sentinel_halts_total"] += 1
        else:
            self._last_sentinel = {"score": sentinel_score, "band": "DISABLED", "reason": "sentinel_off"}
        
        strategy_name = str(self.cfg.get("strategy", "council")).lower()
        use_tophunter = strategy_name == "tophunter_short_v1"
        if use_tophunter and self.tophunter_cooldown_remaining > 0:
            self.tophunter_cooldown_remaining -= 1

        history = self.history_bars

        # Mark equity on current close before risk gates.
        self.broker.mark_to_market(self.cfg["symbol"], bar.close)
        total_dd_pct = (1.0 - (self.broker.equity / self.cfg["start_balance"])) * 100.0

        bar_day = datetime.fromtimestamp(bar.timestamp).date()
        if self.current_day is None or bar_day != self.current_day:
            self.current_day = bar_day
            self.day_start_equity = self.broker.equity
            self.daily_stop_active = False

        daily_dd_pct = 0.0
        if self.day_start_equity > 0:
            daily_dd_pct = ((self.day_start_equity - self.broker.equity) / self.day_start_equity) * 100.0
        daily_pnl_pct = -daily_dd_pct
        current_dd_pct = -total_dd_pct
        if daily_dd_pct >= self.cfg["daily_loss_limit_pct"]:
            self.daily_stop_active = True
        
        # 1. Indicators / Regime
        regime = self.regime_detector.detect(history)
        if self.v2_bridge is not None:
            snap = self.v2_bridge.compute_market_snapshot(history)
            if snap is not None:
                self.last_v2_snapshot = snap
                regime = snap.regime_legacy
        regime_policy = self.regime_policy_resolver.resolve(regime)
        self._last_regime_policy = {
            "pack": self.regime_policy_resolver.name,
            "regime": regime,
            "risk_multiplier": regime_policy.risk_multiplier,
            "min_adx_bonus": regime_policy.min_adx_bonus,
            "max_exp_multiplier": regime_policy.max_exp_multiplier,
            "cooldown_bars": regime_policy.cooldown_bars,
        }
        ae_vote = self.aegean.calculate(history)
        or_vote = self.orion.calculate(history)
        self._last_engine_signals["orion"] = float(or_vote.score if or_vote else 0.0)
        self._last_engine_signals["aegean"] = float(ae_vote.score if ae_vote else 0.0)
        if self.last_v2_snapshot is not None:
            self._last_engine_signals["atlas"] = float(self.last_v2_snapshot.atlas_score)
            self._last_engine_signals["aether"] = float(self.last_v2_snapshot.aether_score)
            self._last_engine_signals["hermes"] = float(self.last_v2_snapshot.hermes_score)
            self._apply_hermes_position_actions(bar)
        
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

        strategy_tags = None
        tophunter_signal = None
        expected_move = 0.0
        edge_score = 0.0
        if use_tophunter:
            tophunter_signal = evaluate_tophunter_short_v1(
                history,
                adx_value=adx_m,
                max_adx=float(self.cfg.get("tophunter_adx_max", 20.0)),
                left=int(self.cfg.get("tophunter_pivot_left", 2)),
                right=int(self.cfg.get("tophunter_pivot_right", 2)),
            )
            strategy_tags = dict(tophunter_signal.tags)
            strategy_tags["strategy_timeframe"] = self.cfg["interval"]
            if tophunter_signal.decision == "GO":
                strategy_tags["trigger_state"] = "FIRED"
                reason = tophunter_signal.reason
                verdict = ConsensusVerdict(
                    timestamp=bar.timestamp,
                    decision="GO",
                    direction="SELL",
                    conviction=85.0,
                    regime=regime,
                    rationale=reason,
                    votes=[],
                    metadata={
                        "block_reason": None,
                        "strategy_id": strategy_tags["strategy_id"],
                        "trigger_type": strategy_tags["trigger_type"],
                        "regime_filter": strategy_tags["regime_filter"],
                        "pivot_low": tophunter_signal.pivot_low,
                        "pivot_high": tophunter_signal.pivot_high,
                        "atr": tophunter_signal.atr if tophunter_signal.atr is not None else atr_m,
                        "slope": slope_raw,
                    },
                )
                edge_score = 100.0
                if tophunter_signal.entry_price and tophunter_signal.tp2_price and tophunter_signal.entry_price > 0:
                    expected_move = (
                        (tophunter_signal.entry_price - tophunter_signal.tp2_price)
                        / tophunter_signal.entry_price
                    ) * 10000.0
                verdict.metadata["expected_move"] = expected_move
                verdict.metadata["score"] = edge_score
            else:
                strategy_tags["trigger_state"] = "NO_FIRE"
                verdict = ConsensusVerdict(
                    timestamp=bar.timestamp,
                    decision="NO_GO",
                    direction="HOLD",
                    conviction=0.0,
                    regime=regime,
                    rationale=tophunter_signal.reason,
                    votes=[],
                    metadata={
                        "block_reason": tophunter_signal.reason_code,
                        "strategy_id": strategy_tags["strategy_id"],
                        "trigger_type": strategy_tags["trigger_type"],
                        "regime_filter": strategy_tags["regime_filter"],
                        "slope": slope_raw,
                        "atr": atr_m,
                    },
                )
                if tophunter_signal.reason_code.startswith("REJECT_"):
                    self.reporter.log_reject(
                        bar.timestamp,
                        self.cfg["symbol"],
                        tophunter_signal.reason_code,
                        tophunter_signal.reason,
                    )
                    self.append_reject(
                        bar,
                        tophunter_signal.reason_code,
                        tophunter_signal.reason,
                        strategy_tags=strategy_tags,
                    )
        elif verdict.decision == "GO":
            # Exp Logic (existing council mode)
            adx_bps_m = adx_m * 0.4
            edge_score = (0.6 * slope_bps_abs) + (0.4 * adx_bps_m)

            atr_base = atr_bps * self.cfg["atr_k"]
            adx_factor = 0.0
            if adx_m > 20:
                adx_factor = min(1.0, (adx_m - 20) / 40.0)
            adx_boost = 1.0 + adx_factor

            expected_move = max(slope_bps_abs, atr_base) * adx_boost * self.cfg["adx_boost"]
            cap_bps = atr_bps * self.cfg["exp_cap_mult"]
            expected_move = min(expected_move, cap_bps)

            verdict.metadata['expected_move'] = expected_move
            verdict.metadata['score'] = edge_score

        # Gates
        # Risk Mult
        r_risk_mult = 1.0
        r_risk_mult *= float(regime_policy.risk_multiplier)
        r_risk_mult *= max(0.10, float(sentinel_score))
        if not use_tophunter:
            if router_res['policy'] == "caution_v5":
                r_risk_mult *= 0.7
            elif router_res['policy'] == "defense_flat":
                if self.cfg.get("soft_defense_override", False):
                    r_risk_mult *= 0.2
                else:
                    r_risk_mult = 0.0

            if verdict.decision == "GO" and r_risk_mult == 0.0:
                verdict.decision = "BLOCK"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "ROUTER_DEFENSE", "Risk=0.0")
                self.append_reject(bar, "ROUTER_DEFENSE", "Risk=0.0")

            # Min ADX
            min_adx = self.cfg["min_adx"] + float(regime_policy.min_adx_bonus)
            if router_res['policy'] == "caution_v5":
                min_adx += 10.0

            if verdict.decision == "GO" and adx_m < min_adx:
                verdict.decision = "BLOCK"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "MIN_ADX", f"{adx_m:.1f} < {min_adx}")
                self.append_reject(bar, "MIN_ADX", f"{adx_m:.1f} < {min_adx}")

            # Max Exp
            max_exp = self.cfg["max_exp_move_bps"] * float(regime_policy.max_exp_multiplier)
            em_check = verdict.metadata.get('expected_move', 0.0)
            if verdict.decision == "GO" and em_check > max_exp:
                verdict.decision = "BLOCK"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "MAX_EXP", f"Exp {em_check:.1f} > {max_exp}")
                self.append_reject(bar, "MAX_EXP", f"Exp {em_check:.1f} > {max_exp}")
        else:
            em_check = verdict.metadata.get('expected_move', expected_move)
            if verdict.decision == "GO" and daily_dd_pct >= float(self.cfg.get("tophunter_daily_loss_cap_pct", 1.5)):
                verdict.decision = "BLOCK"
                detail = f"TopHunter daily loss cap hit ({daily_dd_pct:.2f}% >= {self.cfg.get('tophunter_daily_loss_cap_pct', 1.5):.2f}%)"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "REJECT_RISK_CAP", detail)
                self.append_reject(bar, "REJECT_RISK_CAP", detail, strategy_tags=strategy_tags)
            if verdict.decision == "GO" and len(self.broker.details) >= int(self.cfg.get("tophunter_max_open_positions", 1)):
                verdict.decision = "BLOCK"
                detail = "TopHunter max concurrent positions reached"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "REJECT_RISK_CAP", detail)
                self.append_reject(bar, "REJECT_RISK_CAP", detail, strategy_tags=strategy_tags)
            if verdict.decision == "GO" and self.tophunter_cooldown_remaining > 0:
                verdict.decision = "BLOCK"
                detail = f"Cooldown active: {self.tophunter_cooldown_remaining} bars remaining"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "REJECT_COOLDOWN", detail)
                self.append_reject(bar, "REJECT_COOLDOWN", detail, strategy_tags=strategy_tags)

        if verdict.decision == "GO" and sentinel_halt:
            verdict.decision = "BLOCK"
            detail = f"score={sentinel_score:.3f} reason={self._last_sentinel.get('reason', 'unknown')}"
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "SENTINEL_HALT", detail)
            self.append_reject(bar, "SENTINEL_HALT", detail, strategy_tags=strategy_tags)

        if verdict.decision == "GO" and self.daily_stop_active:
            verdict.decision = "BLOCK"
            detail = f"DailyDD {daily_dd_pct:.2f}% >= {self.cfg['daily_loss_limit_pct']:.2f}%"
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "DAILY_STOP", detail)
            self.append_reject(bar, "DAILY_STOP", detail, strategy_tags=strategy_tags)

        if verdict.decision == "GO" and total_dd_pct >= self.cfg["kill_switch_dd_pct"]:
            verdict.decision = "BLOCK"
            detail = f"DD {total_dd_pct:.2f}% >= {self.cfg['kill_switch_dd_pct']:.2f}%"
            self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "KILL_SWITCH_DD", detail)
            self.append_reject(bar, "KILL_SWITCH_DD", detail, strategy_tags=strategy_tags)
            self.kill_switch_active = True
        if self.v2_bridge is not None:
            try:
                closed_trades = [x for x in self.broker.trades if abs(float(getattr(x, "pnl", 0.0))) > 1e-12]
                expect = float(np.mean([float(t.pnl) for t in closed_trades[-50:]])) if closed_trades else 0.0
                sharpe = 0.0
                if len(closed_trades) >= 5:
                    pnl_vals = np.array([float(t.pnl) for t in closed_trades[-100:]], dtype=float)
                    std = float(np.std(pnl_vals, ddof=1))
                    sharpe = float(np.mean(pnl_vals) / std) if std > 1e-12 else 0.0
                self.v2_bridge.evaluate_lifecycle(
                    strategy_id=self._resolve_strategy_id(strategy_tags),
                    trades=len(closed_trades),
                    expectancy=expect,
                    sharpe=sharpe,
                    max_dd_pct=total_dd_pct,
                    error_rate_pct=(self.health["errors_total"] / max(1, self.counters["bars_seen"])) * 100.0,
                    telemetry_stale_sec=0.0,
                    hard_risk_violations=1 if self.kill_switch_active else 0,
                    consecutive_loss_days=self.consecutive_losses,
                )
                if self.v2_bridge.lifecycle_state in {StrategyState.FROZEN, StrategyState.RETIRED} and verdict.decision == "GO":
                    verdict.decision = "BLOCK"
                    detail = f"LIFECYCLE_{self.v2_bridge.lifecycle_state.value}"
                    self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], detail, self.v2_bridge.last_lifecycle_reason)
                    self.append_reject(bar, detail, self.v2_bridge.last_lifecycle_reason, strategy_tags=strategy_tags)
            except Exception:
                self.log_error("V2_LIFECYCLE_EVAL_FAILED")

        verdict = self._apply_strategy_disable_guard(bar, verdict, strategy_tags=strategy_tags)
        verdict = self._apply_macro_guard(bar, verdict, strategy_tags=strategy_tags)
        if self.mode == "v2" and bool(self.cfg.get("execution_quality_gate_enabled", True)):
            try:
                volume_vals = [float(x.volume) for x in self.history_bars[-20:]]
                volume_mean = float(np.mean(volume_vals)) if volume_vals else max(1.0, float(bar.volume))
                volume_ratio = float(bar.volume) / max(1.0, volume_mean)
                regime_confidence = (
                    float(self.last_v2_snapshot.regime_confidence)
                    if self.last_v2_snapshot is not None
                    else 0.65
                )
                ae_conf = float(getattr(ae_vote, "confidence", 0.0))
                or_conf = float(getattr(or_vote, "confidence", 0.0))
                expected_bps = float(verdict.metadata.get("expected_move", expected_move))
                entry_quality = self.entry_quality_scorer.calculate(
                    adx=float(adx_m),
                    aegean_conviction=ae_conf,
                    orion_conviction=or_conf,
                    volume_ratio=volume_ratio,
                    mrie_shift_score=max(0.0, min(1.0, 1.0 - regime_confidence)),
                    council_decision="GO" if verdict.decision == "GO" else "BLOCK",
                )
                exec_quality = self.execution_quality_gate.evaluate(
                    ExecutionQualityInput(
                        adx=float(adx_m),
                        expected_move_bps=expected_bps,
                        volume_ratio=volume_ratio,
                        regime_confidence=regime_confidence,
                        aegean_confidence=ae_conf,
                        orion_confidence=or_conf,
                        slippage_bps_estimate=float(self.cfg.get("slippage_bps", 2.0)),
                        spread_bps_estimate=float(self.cfg.get("spread_bps", 1.0)),
                    )
                )
                blended_score = max(0.0, min(1.0, (float(entry_quality.score) + float(exec_quality.score)) / 2.0))
                self._last_execution_quality = {
                    "score": blended_score,
                    "grade": ExecutionQualityGate.quality_grade(blended_score),
                    "entry_quality_score": float(entry_quality.score),
                    "execution_quality_score": float(exec_quality.score),
                    "entry_quality_reason": entry_quality.rejection_reason,
                    "execution_quality_reason": exec_quality.reason,
                    "threshold": float(self.cfg.get("execution_quality_threshold", 0.55)),
                }
                if verdict.decision == "GO" and (not entry_quality.passed or not exec_quality.passed):
                    verdict.decision = "BLOCK"
                    detail = (
                        f"entry={entry_quality.score:.3f} exec={exec_quality.score:.3f} "
                        f"reason={exec_quality.reason}"
                    )
                    self.event_counters["execution_quality_blocks_total"] += 1
                    self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "EXEC_QUALITY_LOW", detail)
                    self.append_reject(bar, "EXEC_QUALITY_LOW", detail, strategy_tags=strategy_tags)
            except Exception as exc:
                self._last_execution_quality = {
                    "score": 0.0,
                    "grade": "D",
                    "execution_quality_reason": f"quality_eval_error:{exc}",
                }

        # Log Decision
        em_check = verdict.metadata.get('expected_move', expected_move)
        self.append_decision(
            bar,
            verdict,
            router_res,
            edge_score if verdict.decision == "GO" else 0.0,
            em_check,
            adx_m,
            strategy_tags=strategy_tags,
        )
            
        # 5. Execution
        # Check Exits (Brackets)
        exit_fill = self.broker.check_brackets(self.cfg["symbol"], bar.high, bar.low, bar.timestamp)
        if exit_fill:
             print(f"CLOSE {exit_fill.side} @ {exit_fill.price:.2f} PnL:{exit_fill.pnl:.2f} ({exit_fill.event})")
             sid_hint = self.open_position_strategy.get(self.cfg["symbol"])
             tags = {"strategy_id": sid_hint} if sid_hint else strategy_tags
             self.append_trade(exit_fill, strategy_tags=tags)
             if exit_fill.pnl < 0:
                 self.consecutive_losses += 1
                 if use_tophunter:
                     self.tophunter_cooldown_remaining = max(
                         self.tophunter_cooldown_remaining,
                         int(self.cfg.get("tophunter_loss_cooldown_bars", 3)),
                     )
             elif exit_fill.pnl > 0:
                 self.consecutive_losses = 0

        if self._apply_kill_switch_guard(bar, daily_pnl_pct, current_dd_pct):
            return
        
        if verdict.decision == "GO":
            print(f"ENTER_EXEC_BRANCH: decision={verdict.decision} direction={verdict.direction}")
            # Risk calc matching CLI (approx)
            risk_pct = self.cfg["max_risk_trade_pct"] * r_risk_mult
            custom_sl_price = None
            custom_tp_price = None
            if use_tophunter:
                risk_pct = min(risk_pct, float(self.cfg.get("tophunter_max_risk_trade_pct", 0.005)))
                if tophunter_signal:
                    custom_sl_price = tophunter_signal.stop_price
                    custom_tp_price = tophunter_signal.tp2_price

            risk_pct, alloc_block_reason = self._apply_v2_risk_sizing(
                risk_pct=risk_pct,
                market_price=float(bar.close),
                expected_move_bps=float(verdict.metadata.get("expected_move", em_check)),
                edge_score=float(edge_score),
            )
            if alloc_block_reason:
                verdict.decision = "BLOCK"
                self.reporter.log_reject(bar.timestamp, self.cfg["symbol"], "ALLOCATOR_BLOCK", alloc_block_reason)
                self.append_reject(bar, "ALLOCATOR_BLOCK", alloc_block_reason, strategy_tags=strategy_tags)
                return
            
            # SAFE PAPER: Enforce min floor if we are taking a trade (risk > 0 or safe_mode override)
            if risk_pct > 0 or self.cfg.get("safe_paper", False):
                 min_r = self.cfg.get("min_risk_pct", 0.1)
                 if risk_pct < min_r:
                     risk_pct = min_r # Bump to floor

            self._emit_advisory_card(
                bar=bar,
                verdict=verdict,
                strategy_tags=strategy_tags,
                stop_price=custom_sl_price,
                tp_price=custom_tp_price,
            )
            
            # Execute Strategy (Entry)
            print(f"EXEC_ATTEMPT: ts={bar.timestamp} daemon={self.cfg['daemon_id']} decision={verdict.decision} dir={verdict.direction} risk={risk_pct:.4f} price={bar.close} bal={self.broker.balance:.2f} score={edge_score:.2f}")

            if self.v2_bridge is not None:
                urgency = UrgencyLevel.NORMAL
                if self.last_v2_snapshot is not None and self.last_v2_snapshot.regime_v2 == "HIGH_VOL_CHOP":
                    urgency = UrgencyLevel.HIGH
                success, reason, _payload = self.v2_bridge.execute_with_v2(
                    symbol=self.cfg["symbol"],
                    direction=verdict.direction,
                    market_price=bar.close,
                    timestamp=bar.timestamp,
                    risk_pct=risk_pct,
                    stop_loss=custom_sl_price,
                    take_profit=custom_tp_price,
                    urgency=urgency,
                    expected_post_qty=0.0,
                )
            else:
                success, reason = self.broker.execute_strategy(
                    symbol=self.cfg["symbol"],
                    decision=verdict.decision,
                    direction=verdict.direction,
                    price=bar.close,
                    timestamp=bar.timestamp,
                    risk_pct=risk_pct,
                    leverage=1.0,
                    custom_sl_price=custom_sl_price,
                    custom_tp_price=custom_tp_price,
                )
            
            if success:
                print(f"OPEN {verdict.direction} @ {bar.close} [Score:{edge_score:.2f}]")
                self.reporter.log_decision(verdict, mode_process=None, capital_profile="ACTIVE")
                if self.broker.trades:
                    self.append_trade(self.broker.trades[-1], strategy_tags=strategy_tags)
            else:
                print(f"TRADE REJECTED: {reason} [RiskPct:{risk_pct*100:.2f}%]")
                # Log to rejects
                self.append_reject(bar, "EXEC_REJECT", reason, strategy_tags=strategy_tags)
                # Log to trades as REJECTED (Audit Trail)
                rej_fill = TradeFill(
                    timestamp=bar.timestamp,
                    symbol=self.cfg["symbol"],
                    side=verdict.direction,
                    price=bar.close,
                    quantity=0.0, # Rejected, so 0
                    commission=0.0,
                    pnl=0.0,
                    event="REJECTED"
                )
                self.append_trade(rej_fill, strategy_tags=strategy_tags)

        # elif verdict.decision == "EXIT":
        #    # CLI/Council does not generate EXIT signals currently.
        #    pass
                
        # Update ATR
        if atr_m > 0: self.atr_history.append(atr_m)
        if self.v2_bridge is not None:
            self.v2_bridge.on_bar_close(
                equity=float(self.broker.equity),
                drawdown_pct=float(total_dd_pct),
                bars_seen=int(self.counters["bars_seen"]),
                decisions_total=int(self.counters["decisions_total"]),
                rejects_total=int(self.counters["rejects_total"]),
                trades_total=int(self.counters["trades_total"]),
                errors_total=int(self.health["errors_total"]),
            )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon_id", type=str, default="STRICT")
    parser.add_argument("--run_dir", type=str, default="runs/phase19_twin/STRICT")
    parser.add_argument("--interval", type=str, default="1m")
    parser.add_argument("--min_adx", type=float, default=35.0)
    parser.add_argument("--max_exp_move_bps", type=float, default=80.0)
    parser.add_argument("--max_risk_trade_pct", type=float, default=1.0, help="Max risk percent per trade")
    parser.add_argument("--daily_loss_limit_pct", type=float, default=3.0, help="Daily loss hard stop %%")
    parser.add_argument("--kill_switch_dd_pct", type=float, default=15.0, help="Total drawdown kill switch %%")
    parser.add_argument("--soft_defense_override", action="store_true", help="Allow defense mode triggers with reduced risk.")
    parser.add_argument("--min_risk_pct", type=float, default=0.1, help="Minimum risk %% floor per trade")
    parser.add_argument("--safe_paper", action="store_true", help="Enable safe paper mode (min risk floor + defense override)")
    parser.add_argument("--strategy", type=str, default="council", choices=["council", "tophunter_short_v1"])
    parser.add_argument("--mode", type=str, default="legacy", choices=["legacy", "v2"])
    parser.add_argument("--asset-class", dest="asset_class", type=str, default="crypto", choices=["crypto", "stock", "defi"])
    parser.add_argument("--venue-id", dest="venue_id", type=str, default="auto")
    parser.add_argument("--macro-events-file", dest="macro_events_file", type=str, default="")
    parser.add_argument("--strategy-registry-file", dest="strategy_registry_file", type=str, default="")
    parser.add_argument("--disabled-strategies-file", dest="disabled_strategies_file", type=str, default="")
    parser.add_argument("--allocator-risk-budget-pct", dest="allocator_risk_budget_pct", type=float, default=1.0)
    parser.add_argument("--allocator-max-asset-exposure-pct", dest="allocator_max_asset_exposure_pct", type=float, default=35.0)
    parser.add_argument("--allocator-assumed-stop-loss-pct", dest="allocator_assumed_stop_loss_pct", type=float, default=2.0)
    parser.add_argument("--correlation-threshold", dest="correlation_threshold", type=float, default=0.7)
    parser.add_argument("--correlation-min-scale", dest="correlation_min_scale", type=float, default=0.3)
    parser.add_argument("--advisory-cards", dest="advisory_cards", action="store_true", default=True)
    parser.add_argument("--no-advisory-cards", dest="advisory_cards", action="store_false")
    parser.add_argument("--execution-quality-threshold", dest="execution_quality_threshold", type=float, default=0.55)
    parser.add_argument("--execution-quality-min-expected-move-bps", dest="execution_quality_min_expected_move_bps", type=float, default=3.0)
    parser.add_argument("--disable-execution-quality-gate", dest="execution_quality_gate_enabled", action="store_false", default=True)
    parser.add_argument("--disable-sentinel", dest="data_quality_sentinel_enabled", action="store_false", default=True)
    parser.add_argument("--sentinel-degraded-threshold", dest="sentinel_degraded_threshold", type=float, default=0.70)
    parser.add_argument("--sentinel-halt-threshold", dest="sentinel_halt_threshold", type=float, default=0.40)
    parser.add_argument("--regime-policy-pack", dest="regime_policy_pack", type=str, default="legacy", choices=["legacy", "balanced", "strict"])
    parser.add_argument("--exposure-total-cap-pct", dest="exposure_total_cap_pct", type=float, default=90.0)
    parser.add_argument("--exposure-symbol-cap-pct", dest="exposure_symbol_cap_pct", type=float, default=35.0)
    parser.add_argument("--exposure-asset-cap-crypto-pct", dest="exposure_asset_cap_crypto_pct", type=float, default=75.0)
    parser.add_argument("--exposure-asset-cap-stock-pct", dest="exposure_asset_cap_stock_pct", type=float, default=70.0)
    parser.add_argument("--exposure-asset-cap-defi-pct", dest="exposure_asset_cap_defi_pct", type=float, default=40.0)
    parser.add_argument("--disable-optimizer", dest="optimizer_enabled", action="store_false", default=True)
    parser.add_argument("--optimizer-gross-cap-pct", dest="optimizer_gross_cap_pct", type=float, default=100.0)
    parser.add_argument("--optimizer-per-symbol-cap-pct", dest="optimizer_per_symbol_cap_pct", type=float, default=20.0)
    parser.add_argument("--optimizer-per-asset-cap-crypto-pct", dest="optimizer_per_asset_cap_crypto_pct", type=float, default=70.0)
    parser.add_argument("--optimizer-per-asset-cap-stock-pct", dest="optimizer_per_asset_cap_stock_pct", type=float, default=70.0)
    parser.add_argument("--optimizer-per-asset-cap-defi-pct", dest="optimizer_per_asset_cap_defi_pct", type=float, default=35.0)
    parser.add_argument("--optimizer-cvar-limit-pct", dest="optimizer_cvar_limit_pct", type=float, default=2.5)
    parser.add_argument("--tophunter_adx_max", type=float, default=20.0)
    parser.add_argument("--tophunter_pivot_left", type=int, default=2)
    parser.add_argument("--tophunter_pivot_right", type=int, default=2)
    parser.add_argument("--tophunter_daily_loss_cap_pct", type=float, default=1.5)
    parser.add_argument("--tophunter_max_risk_trade_pct", type=float, default=0.5, help="TopHunter max risk %% per trade")
    parser.add_argument("--tophunter_max_open_positions", type=int, default=1)
    parser.add_argument("--tophunter_loss_cooldown_bars", type=int, default=3)
    parser.add_argument("--heartbeat_interval_sec", type=int, default=5)
    
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
    cfg["interval"] = args.interval
    cfg["max_exp_move_bps"] = args.max_exp_move_bps
    cfg["daily_loss_limit_pct"] = args.daily_loss_limit_pct
    cfg["kill_switch_dd_pct"] = args.kill_switch_dd_pct
    cfg["soft_defense_override"] = args.soft_defense_override
    cfg["strategy"] = args.strategy
    cfg["mode"] = args.mode
    cfg["asset_class"] = args.asset_class
    cfg["venue_id"] = args.venue_id
    cfg["macro_events_file"] = args.macro_events_file or cfg.get("macro_events_file")
    cfg["strategy_registry_file"] = args.strategy_registry_file or cfg.get("strategy_registry_file")
    cfg["disabled_strategies_file"] = args.disabled_strategies_file or cfg.get("disabled_strategies_file")
    cfg["allocator_risk_budget_pct"] = float(args.allocator_risk_budget_pct)
    cfg["allocator_max_asset_exposure_pct"] = float(args.allocator_max_asset_exposure_pct)
    cfg["allocator_assumed_stop_loss_pct"] = float(args.allocator_assumed_stop_loss_pct)
    cfg["correlation_threshold"] = float(args.correlation_threshold)
    cfg["correlation_min_scale"] = float(args.correlation_min_scale)
    cfg["advisory_cards_enabled"] = bool(args.advisory_cards)
    cfg["execution_quality_threshold"] = float(args.execution_quality_threshold)
    cfg["execution_quality_min_expected_move_bps"] = float(args.execution_quality_min_expected_move_bps)
    cfg["execution_quality_gate_enabled"] = bool(args.execution_quality_gate_enabled)
    cfg["data_quality_sentinel_enabled"] = bool(args.data_quality_sentinel_enabled)
    cfg["sentinel_degraded_threshold"] = float(args.sentinel_degraded_threshold)
    cfg["sentinel_halt_threshold"] = float(args.sentinel_halt_threshold)
    cfg["regime_policy_pack"] = str(args.regime_policy_pack)
    cfg["exposure_total_cap_pct"] = float(args.exposure_total_cap_pct)
    cfg["exposure_symbol_cap_pct"] = float(args.exposure_symbol_cap_pct)
    cfg["exposure_asset_cap_crypto_pct"] = float(args.exposure_asset_cap_crypto_pct)
    cfg["exposure_asset_cap_stock_pct"] = float(args.exposure_asset_cap_stock_pct)
    cfg["exposure_asset_cap_defi_pct"] = float(args.exposure_asset_cap_defi_pct)
    cfg["optimizer_enabled"] = bool(args.optimizer_enabled)
    cfg["optimizer_gross_cap_pct"] = float(args.optimizer_gross_cap_pct)
    cfg["optimizer_per_symbol_cap_pct"] = float(args.optimizer_per_symbol_cap_pct)
    cfg["optimizer_per_asset_cap_crypto_pct"] = float(args.optimizer_per_asset_cap_crypto_pct)
    cfg["optimizer_per_asset_cap_stock_pct"] = float(args.optimizer_per_asset_cap_stock_pct)
    cfg["optimizer_per_asset_cap_defi_pct"] = float(args.optimizer_per_asset_cap_defi_pct)
    cfg["optimizer_cvar_limit_pct"] = float(args.optimizer_cvar_limit_pct)
    cfg["tophunter_adx_max"] = args.tophunter_adx_max
    cfg["tophunter_pivot_left"] = args.tophunter_pivot_left
    cfg["tophunter_pivot_right"] = args.tophunter_pivot_right
    cfg["tophunter_daily_loss_cap_pct"] = args.tophunter_daily_loss_cap_pct
    cfg["tophunter_max_open_positions"] = args.tophunter_max_open_positions
    cfg["tophunter_loss_cooldown_bars"] = args.tophunter_loss_cooldown_bars
    cfg["heartbeat_interval_sec"] = max(1, int(args.heartbeat_interval_sec))
    # Convert percentages to fractions (1.0 -> 0.01)
    cfg["max_risk_trade_pct"] = args.max_risk_trade_pct / 100.0
    cfg["tophunter_max_risk_trade_pct"] = args.tophunter_max_risk_trade_pct / 100.0
    cfg["min_risk_pct"] = args.min_risk_pct / 100.0
    cfg["safe_paper"] = args.safe_paper
    if cfg["safe_paper"]:
        cfg["soft_defense_override"] = True # Implies override
    if cfg["strategy"] == "tophunter_short_v1" and cfg["interval"] != "1h":
        print("WARN: TopHunter Short V1 requires 1h candles; overriding interval to 1h.")
        cfg["interval"] = "1h"
    
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
    print(f"  Interval: {cfg['interval']}")
    print(f"  MaxRisk: {cfg['max_risk_trade_pct']:.4f} (Min {cfg['min_risk_pct']:.4f})")
    print(f"  DailyStop: {cfg['daily_loss_limit_pct']:.2f}% | KillSwitchDD: {cfg['kill_switch_dd_pct']:.2f}%")
    print(f"  SafePaper: {cfg['safe_paper']}")
    print(f"  Strategy: {cfg['strategy']}")
    print(f"  Mode: {cfg['mode']}")
    print(f"  AssetClass: {cfg['asset_class']} | Venue: {cfg['venue_id']}")
    print(
        "  V2Extras:"
        f" exec_gate={'on' if cfg['execution_quality_gate_enabled'] else 'off'}"
        f" sentinel={'on' if cfg['data_quality_sentinel_enabled'] else 'off'}"
        f" policy_pack={cfg['regime_policy_pack']}"
        f" optimizer={'on' if cfg['optimizer_enabled'] else 'off'}"
    )
    print(f"  RunDir: {cfg['run_dir']}")
    
    d = PaperDaemon(cfg)
    d.warmup()
    d.run_loop()
