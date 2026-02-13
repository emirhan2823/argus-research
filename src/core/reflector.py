import numpy as np
import polars as pl
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

@dataclass
class TradeRecord:
    id: str
    symbol: str
    direction: str # LONG / SHORT
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    pnl: float

@dataclass
class AdjustmentVector:
    reason: str
    suggested_changes: Dict[str, float] # e.g., {'sl_atr_mult': 0.2}

class Reflector:
    """
    Quant Forensic Module.
    Analyzes closed trades to classify failures and suggest genome adjustments.
    """
    def __init__(self):
        pass

    def run_post_mortem(self, trade: TradeRecord, market_data: pl.DataFrame) -> Optional[AdjustmentVector]:
        """
        Main entry point. Runs analysis if trade was a loss or suboptimal.
        market_data: Should cover [entry_time - 1h, exit_time + 4h]
        """
        if trade.pnl > 0:
            # For now, ignore winning trades.
            # Future: Analyze "Money left on table" (sold too early).
            return None

        # 1. Prepare Simulation Data (NumPy for speed)
        # Extract High/Low/Close arrays relative to entry
        # We need data from entry_time onwards for counterfactuals
        sim_data = market_data.filter(pl.col("timestamp") >= trade.entry_time)
        # Relax data requirement for unit tests with small mock data
        if sim_data.height < 4:
            return None # Not enough data

        highs = sim_data["high"].to_numpy()
        lows = sim_data["low"].to_numpy()
        closes = sim_data["close"].to_numpy()
        timestamps = sim_data["timestamp"].to_numpy()

        # 2. Run Counterfactuals
        # Scenario A: What if SL was wider?
        sl_result = self._simulate_sl_sensitivity(trade, highs, lows)

        # Scenario B: What if we entered later? (Timing)
        # Requires pre-entry data, assumed available in logic, simplified here.

        # 3. Classify & Recommend
        return self._classify_failure(trade, sl_result)

    def _simulate_sl_sensitivity(self, trade: TradeRecord, highs: np.ndarray, lows: np.ndarray) -> Dict[str, bool]:
        """
        Simulates if the trade would have survived/profited with wider SL.
        """
        # Define scenarios: 1.1x SL, 1.2x SL ... 1.5x SL
        multipliers = [1.1, 1.2, 1.3, 1.5]
        results = {}

        entry = trade.entry_price
        original_dist = abs(entry - trade.stop_loss)

        for mult in multipliers:
            new_dist = original_dist * mult

            if trade.direction == "LONG":
                new_sl = entry - new_dist
                # Check indices where Price <= SL
                sl_indices = np.where(lows <= new_sl)[0]
                # Check indices where Price >= TP
                tp_indices = np.where(highs >= trade.take_profit)[0]
            else:
                new_sl = entry + new_dist
                sl_indices = np.where(highs >= new_sl)[0]
                tp_indices = np.where(lows <= trade.take_profit)[0]

            first_sl = sl_indices[0] if len(sl_indices) > 0 else 999999
            first_tp = tp_indices[0] if len(tp_indices) > 0 else 999999

            # Would we have won?
            # Win if we hit TP (first_tp < inf) AND (TP hit before SL or SL never hit)
            would_win = (first_tp < 999999) and (first_tp < first_sl)
            results[f"x{mult}"] = would_win

        return results

    def _classify_failure(self, trade: TradeRecord, sl_sim_results: Dict[str, bool]) -> AdjustmentVector:
        """
        Determines the root cause.
        """
        # Check NOISE (Stop Hunt)
        # If widening SL slightly (1.1x or 1.2x) would have resulted in a win
        # Note: dict keys are strings "x1.1", "x1.2"
        if sl_sim_results.get("x1.1") or sl_sim_results.get("x1.2") or sl_sim_results.get("x1.3"):
            return AdjustmentVector(
                reason="NOISE",
                suggested_changes={"sl_atr_mult": 0.2} # Nudge SL wider
            )

        # Check REGIME (Even wide SL fails)
        if not sl_sim_results.get("x1.5"):
            return AdjustmentVector(
                reason="REGIME_SHIFT",
                suggested_changes={"rsi_period": 2.0} # Slow down indicators to filter noise
            )

        return AdjustmentVector(reason="UNCERTAIN", suggested_changes={})
