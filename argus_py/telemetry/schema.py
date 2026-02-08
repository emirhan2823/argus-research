
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

class TelemetryEvent:
    VERSION = "19.6"
    
    @staticmethod
    def _base(daemon_id: str, run_id: str, event_type: str, 
              symbol: str, interval: str, bar_ts: Optional[float] = None) -> Dict[str, Any]:
        
        return {
            "ts_iso": datetime.now().isoformat(),
            "bar_ts_iso": datetime.fromtimestamp(bar_ts).isoformat() if bar_ts else None,
            "symbol": symbol,
            "interval": interval,
            "run_id": run_id,
            "daemon_id": daemon_id,
            "event": event_type,
            "version": TelemetryEvent.VERSION
        }

    @staticmethod
    def decision(daemon_id, run_id, symbol, interval, bar_ts, 
                 regime, mode, policy, verdict, 
                 scores: Dict[str, float], 
                 params: Dict[str, float],
                 reasons: List[str]):
        
        base = TelemetryEvent._base(daemon_id, run_id, "DECISION", symbol, interval, bar_ts)
        base.update({
            "regime": regime,
            "mode_final": mode,
            "router_policy": policy,
            "decision": verdict.decision, # GO/BLOCK/EXIT/NO_GO
            "direction": verdict.direction,
            "ae_score": scores.get("ae_score", 0.0),
            "edge_score": scores.get("edge_score", 0.0),
            "orion_adx": scores.get("adx", 0.0),
            "atr": scores.get("atr", 0.0),
            "slope": scores.get("slope", 0.0),
            "expected_move_bps": scores.get("expected_move_bps", 0.0),
            "max_exp_move_bps": params.get("max_exp_move_bps", 0.0),
            "min_adx_used": params.get("min_adx", 0.0),
            "block_reason_primary": reasons[0] if reasons else None,
            "block_reasons_all": reasons
        })
        # Optional strategy tags
        if params.get("strategy_id") is not None:
            base["strategy_id"] = params.get("strategy_id")
        if params.get("trigger_type") is not None:
            base["trigger_type"] = params.get("trigger_type")
        if params.get("regime_filter") is not None:
            base["regime_filter"] = params.get("regime_filter")
        if params.get("strategy_timeframe") is not None:
            base["strategy_timeframe"] = params.get("strategy_timeframe")
        if params.get("trigger_state") is not None:
            base["trigger_state"] = params.get("trigger_state")
        return base

    @staticmethod
    def reject(daemon_id, run_id, symbol, interval, bar_ts, 
               code, detail, snapshot: Dict[str, Any]):
        base = TelemetryEvent._base(daemon_id, run_id, "REJECT", symbol, interval, bar_ts)
        base.update({
            "reason_code": code,
            "reason_detail": detail,
            "snapshot": snapshot
        })
        return base

    @staticmethod
    def trade_open(daemon_id, run_id, symbol, interval, bar_ts, 
                   entry_price, qty, side, fees_model: str):
        base = TelemetryEvent._base(daemon_id, run_id, "TRADE_OPEN", symbol, interval, bar_ts)
        base.update({
            "entry_price": entry_price,
            "qty": qty,
            "side": side,
            "fees_model": fees_model
        })
        return base

    @staticmethod
    def trade_close(daemon_id, run_id, symbol, interval, bar_ts, 
                    exit_price, pnl, pnl_pct, reason):
        base = TelemetryEvent._base(daemon_id, run_id, "TRADE_CLOSE", symbol, interval, bar_ts)
        base.update({
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": reason
        })
        return base
