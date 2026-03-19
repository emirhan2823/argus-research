"""
Entry Quality Score Module

Calculates a quality score (0-1) for each trading signal before entry.
Higher scores indicate higher conviction setups.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class EntryQuality:
    """Result of entry quality assessment."""
    score: float                  # 0.0 to 1.0
    passed: bool                  # True if score >= threshold
    trend_strength: float         # ADX contribution
    confirmation_score: float     # Multi-model agreement
    volume_score: float           # Volume confirmation
    regime_stability: float       # MRIE shift score (inverted)
    rejection_reason: Optional[str] = None


class EntryQualityScorer:
    """
    Gate keeper that ensures only high-quality setups are traded.
    
    Components:
    - Trend Strength (30%): ADX normalized (0-60 range)
    - Confirmation (30%): Aegean + Orion agreement
    - Volume (20%): Volume vs average
    - Regime Stability (20%): 1 - MRIE shift_score
    
    Default threshold: 0.5 (50% quality minimum)
    """
    
    # Weight configuration
    WEIGHT_TREND = 0.30
    WEIGHT_CONFIRMATION = 0.30
    WEIGHT_VOLUME = 0.20
    WEIGHT_REGIME = 0.20
    
    # Normalization parameters
    ADX_MIN = 20      # Below this, no trend
    ADX_MAX = 50      # Maximum effective ADX
    VOL_BASELINE = 1.0  # Volume ratio baseline
    
    def __init__(self, min_quality_threshold: float = 0.50):
        """
        Args:
            min_quality_threshold: Minimum score to pass (0.0 to 1.0)
        """
        self.threshold = min_quality_threshold
        
    def calculate(
        self,
        adx: float,
        aegean_conviction: float,
        orion_conviction: float,
        volume_ratio: float,
        mrie_shift_score: float,
        council_decision: str = "GO"
    ) -> EntryQuality:
        """
        Calculate entry quality score.
        
        Args:
            adx: Current ADX value
            aegean_conviction: Aegean model conviction (0 to 1)
            orion_conviction: Orion model conviction (0 to 1)
            volume_ratio: Current volume / Average volume
            mrie_shift_score: MRIE shift score (0 to 1, higher = more regime risk)
            council_decision: Council decision ("GO", "BLOCK", etc.)
            
        Returns:
            EntryQuality with score and breakdown
        """
        # 1. Trend Strength (normalize ADX)
        if adx < self.ADX_MIN:
            trend_strength = 0.0
        elif adx > self.ADX_MAX:
            trend_strength = 1.0
        else:
            trend_strength = (adx - self.ADX_MIN) / (self.ADX_MAX - self.ADX_MIN)
            
        # 2. Confirmation Score (average of both models)
        confirmation_score = (aegean_conviction + orion_conviction) / 2.0
        
        # 3. Volume Score (cap at 2x average)
        volume_score = min(volume_ratio / 2.0, 1.0) if volume_ratio > 0 else 0.0
        
        # 4. Regime Stability (invert shift score - higher stability = better)
        regime_stability = 1.0 - min(mrie_shift_score, 1.0)
        
        # Calculate weighted score
        score = (
            self.WEIGHT_TREND * trend_strength +
            self.WEIGHT_CONFIRMATION * confirmation_score +
            self.WEIGHT_VOLUME * volume_score +
            self.WEIGHT_REGIME * regime_stability
        )
        
        # Determine if passed
        passed = score >= self.threshold and council_decision == "GO"
        
        # Rejection reason
        rejection_reason = None
        if not passed:
            if council_decision != "GO":
                rejection_reason = f"Council: {council_decision}"
            elif score < self.threshold:
                # Find weakest component
                components = [
                    ("TREND", trend_strength),
                    ("CONFIRMATION", confirmation_score),
                    ("VOLUME", volume_score),
                    ("REGIME", regime_stability)
                ]
                weakest = min(components, key=lambda x: x[1])
                rejection_reason = f"Low quality ({score:.2f}), weakest: {weakest[0]}"
        
        return EntryQuality(
            score=score,
            passed=passed,
            trend_strength=trend_strength,
            confirmation_score=confirmation_score,
            volume_score=volume_score,
            regime_stability=regime_stability,
            rejection_reason=rejection_reason
        )
    
    def should_trade(
        self,
        quality: EntryQuality,
        allow_marginal: bool = False
    ) -> bool:
        """
        Final trade decision based on quality.
        
        Args:
            quality: EntryQuality result
            allow_marginal: If True, allow trades with score >= threshold * 0.8
            
        Returns:
            True if trade should proceed
        """
        if quality.passed:
            return True
            
        if allow_marginal:
            marginal_threshold = self.threshold * 0.8
            return quality.score >= marginal_threshold
            
        return False
