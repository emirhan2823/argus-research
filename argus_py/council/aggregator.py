from typing import List
from argus_py.council.defs import Vote, ConsensusVerdict

class Council:
    def __init__(self):
        # Base Weights
        self.weights = {
            "Aegean": 1.0,
            "Orion": 1.0
        }
    
    def deliberate(self, votes: List[Vote], regime: str, timestamp: float, threshold: float = 0.4, trend_floor: float = None, chop_floor: float = None) -> ConsensusVerdict:
        # 1. Adjust Weights based on Regime
        active_weights = self.weights.copy()
        
        regime_rationale = ""
        current_threshold = threshold
        
        if regime == "TREND":
            active_weights["Orion"] = 2.0 
            regime_rationale = "Regime: TREND (Orion 2x)"
            if trend_floor is not None: current_threshold = trend_floor
            
        elif regime == "CHOP":
            active_weights["Aegean"] = 0.5 
            regime_rationale = "Regime: CHOP (Reduced Weights)"
            if chop_floor is not None: current_threshold = chop_floor
            
        # 2. Aggregate
        total_score_impact = 0.0
        total_weight = 0.0
        
        dirs = {"LONG": 1, "SHORT": -1, "FLAT": 0}
        
        meta_agg = {
            "aegean_valid": True,
            "orion_valid": True,
            "raw_scores": {}
        }
        
        for v in votes:
            w = active_weights.get(v.module, 1.0)
            d = dirs.get(v.direction, 0)
            
            # Metadata Aggregation
            if v.metadata:
                if "aegean_valid" in v.metadata and not v.metadata["aegean_valid"]:
                    meta_agg["aegean_valid"] = False
                if "orion_valid" in v.metadata and not v.metadata["orion_valid"]:
                    meta_agg["orion_valid"] = False
                
                # Copy raw values
                for k, val in v.metadata.items():
                    if k not in ["aegean_valid", "orion_valid", "reason"]:
                        meta_agg[k] = val
            
            # Score contribution
            total_score_impact += (d * v.confidence * w)
            total_weight += w
            meta_agg["raw_scores"][v.module] = d * v.confidence
            
        normalized_score = 0.0
        if total_weight > 0:
            normalized_score = total_score_impact / total_weight
            
        decision = "NO_GO"
        final_dir = "HOLD"
        conviction = abs(normalized_score) * 100.0
        
        rationale = f"{regime_rationale}. Score: {normalized_score:.2f}."
        block_reason = None
        
        # Check Validity first
        if not meta_agg["aegean_valid"] or not meta_agg["orion_valid"]:
            decision = "NO_GO"
            block_reason = "WARMUP"
            rationale += " [WARMUP]"
        elif normalized_score > current_threshold:
            decision = "GO"
            final_dir = "BUY"
            rationale += " Bullish Consensus."
        elif normalized_score < -current_threshold:
            decision = "GO"
            final_dir = "SELL"
            rationale += " Bearish Consensus."
        else:
            decision = "NO_GO"
            block_reason = "LOW_CONVICTION"
            rationale += f" Low Conviction (<{current_threshold})."
            
        # Veto Checks 
        for v in votes:
             if final_dir == "BUY" and v.direction == "SHORT" and v.confidence > 0.8:
                 decision = "NO_GO"
                 block_reason = "VETO"
                 rationale += f" VETO: {v.module} Strong Short."
             if final_dir == "SELL" and v.direction == "LONG" and v.confidence > 0.8:
                 decision = "NO_GO"
                 block_reason = "VETO"
                 rationale += f" VETO: {v.module} Strong Long."

        meta_agg["block_reason"] = block_reason

        return ConsensusVerdict(
            timestamp=timestamp,
            decision=decision,
            direction=final_dir,
            conviction=conviction,
            regime=regime,
            rationale=rationale,
            votes=votes,
            metadata=meta_agg
        )
