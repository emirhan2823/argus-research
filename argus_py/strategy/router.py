
from typing import Dict, Any, Optional

class ModeRouter:
    """
    Phase 8: Mode Router & Execution Policy
    
    Translates passive MRIE signals (ShiftScore/ModeSuggest) into active Execution Modes
    with hysteresis to prevent flapping.
    
    State Machine:
    - ATTACK -> CAUTION -> DEFENSE
    - Hysteresis: CAUTION (15 bars), DEFENSE (30 bars).
    """
    
    def __init__(self, cooldown_defense: int = 30, cooldown_caution: int = 15):
        self.cooldown_defense = cooldown_defense
        self.cooldown_caution = cooldown_caution
        
        # State
        self.current_mode = "ATTACK"  # Default start
        self.cooldown_counter = 0
        self.last_shift_score = 0.0
        
    def update(self, mode_suggest: str, shift_score: float) -> Dict[str, Any]:
        """
        Updates router state and returns final mode and policy.
        """
        self.last_shift_score = shift_score
        
        # 1. Decrement Cooldown
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            
        # 2. Determine Candidate Mode (Input)
        candidate_mode = mode_suggest
        
        # 3. State Transition Logic
        # If we are in restricted mode (DEFENSE/CAUTION) and cooler is active, hold state.
        # Unless we are upgrading to a MORE restrictive state (e.g. CAUTION -> DEFENSE).
        
        # Hierarchy: DEFENSE > CAUTION > ATTACK
        priority = {"DEFENSE": 3, "CAUTION": 2, "ATTACK": 1}
        
        curr_p = priority.get(self.current_mode, 1)
        cand_p = priority.get(candidate_mode, 1)
        
        new_mode = self.current_mode
        
        if cand_p > curr_p:
            # Escalate immediately (Safety First)
            new_mode = candidate_mode
            # Set Cooldown
            if new_mode == "DEFENSE":
                self.cooldown_counter = self.cooldown_defense
            elif new_mode == "CAUTION":
                self.cooldown_counter = self.cooldown_caution
                
        elif cand_p < curr_p:
            # De-escalate only if cooldown expired
            if self.cooldown_counter <= 0:
                new_mode = candidate_mode
                # Reset cooldown? No, moving to Relaxed mode usually has no forced hold, 
                # unless we want to prevent "Attack" flapping too. 
                # For now: No cooldown on Attack.
            else:
                # Holding restricted mode
                pass
        else:
            # Same mode, refresh cooldown? 
            # Usually: No. If signal persists, we stay anyway. 
            # If signal flickers, counter handles it.
            # But if signal is SOLIDLY Defense, we don't need counter to force it.
            # Counter is for when signal drops to Attack *prematurely*.
            new_mode = candidate_mode

        self.current_mode = new_mode
        
        # 4. Determine Policy
        # Map ModeFinal to Configured Policy
        policy = "attack_v5" # Default
        
        if new_mode == "DEFENSE":
            policy = "defense_flat" # Or defense_strict
        elif new_mode == "CAUTION":
            policy = "caution_v5"
            
        return {
            "mode_final": self.current_mode,
            "policy": policy,
            "cooldown": self.cooldown_counter,
            "suggest": mode_suggest
        }
