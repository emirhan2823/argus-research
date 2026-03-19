"""
Kill-Switch Module: 3-Level Risk Circuit Breaker

Levels:
- NORMAL: Trading allowed
- SOFT: Block new trades, existing positions run
- HARD: Close all positions  
- HALT: Disconnect from exchange

Author: Opus (Architect) implementing P20-001
Date: 2026-02-07
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time
import json
from pathlib import Path


class RiskLevel(Enum):
    """Risk levels in order of severity."""
    NORMAL = "NORMAL"  # Trading allowed
    SOFT = "SOFT"      # Block new trades, existing run
    HARD = "HARD"      # Close all positions
    HALT = "HALT"      # Disconnect from exchange
    
    def __lt__(self, other):
        order = [RiskLevel.NORMAL, RiskLevel.SOFT, RiskLevel.HARD, RiskLevel.HALT]
        return order.index(self) < order.index(other)
    
    def __le__(self, other):
        return self == other or self < other
    
    def __gt__(self, other):
        return not self <= other
    
    def __ge__(self, other):
        return not self < other


@dataclass
class KillSwitchConfig:
    """Configuration for kill-switch triggers."""
    # Daily loss thresholds (as positive percentages)
    soft_daily_loss_pct: float = 3.0       # Daily loss % to trigger SOFT
    hard_daily_loss_pct: float = 5.0       # Daily loss % to trigger HARD
    
    # Total drawdown threshold
    halt_dd_pct: float = 8.0               # Total DD % to trigger HALT
    
    # Consecutive losses
    soft_consecutive_losses: int = 3       # Losses to trigger SOFT
    hard_consecutive_losses: int = 5       # Losses to trigger HARD
    
    # API errors (per hour)
    soft_api_errors: int = 5               # API errors/hour to trigger SOFT
    hard_api_errors: int = 10              # API errors/hour to trigger HARD
    
    # Recovery wait times (hours)
    soft_recovery_hours: float = 4.0
    hard_recovery_hours: float = 24.0
    halt_recovery_hours: float = 48.0      # Requires manual confirm anyway


@dataclass
class KillSwitchState:
    """Current state of the kill-switch."""
    level: RiskLevel = RiskLevel.NORMAL
    activated_at: Optional[float] = None
    reason: str = ""
    transitions: List[Tuple[float, str, str, str]] = field(default_factory=list)
    # (timestamp, from_level, to_level, reason)
    
    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "activated_at": self.activated_at,
            "activated_at_iso": datetime.fromtimestamp(self.activated_at).isoformat() if self.activated_at else None,
            "reason": self.reason,
            "transitions_count": len(self.transitions)
        }


class KillSwitch:
    """
    3-level risk circuit breaker.
    
    INVARIANTS:
    - Level can only increase (NORMAL→SOFT→HARD→HALT) without explicit recovery
    - HALT requires manual confirmation to recover
    - All level changes are logged with reason
    
    Example:
        ks = KillSwitch(KillSwitchConfig())
        level = ks.check_triggers({
            'daily_pnl_pct': -3.5,
            'total_dd_pct': -7.0,
            'consecutive_losses': 2,
            'api_errors_1h': 0
        })
        if level >= RiskLevel.SOFT:
            print("Trading blocked!")
    """
    
    def __init__(self, config: Optional[KillSwitchConfig] = None) -> None:
        """Initialize with configuration."""
        self.config = config or KillSwitchConfig()
        self.state = KillSwitchState()
        self._log: List[dict] = []
    
    def check_triggers(self, metrics: Dict[str, float]) -> RiskLevel:
        """
        Evaluate current metrics against trigger thresholds.
        
        Args:
            metrics: {
                'daily_pnl_pct': float,      # e.g., -3.5 for 3.5% loss (negative = loss)
                'total_dd_pct': float,       # e.g., -7.0 for 7% drawdown (negative)
                'consecutive_losses': int,
                'api_errors_1h': int
            }
        
        Returns:
            Highest triggered RiskLevel (does NOT auto-activate)
        """
        triggered_level = RiskLevel.NORMAL
        trigger_reasons = []
        
        daily_pnl = metrics.get('daily_pnl_pct', 0.0)
        total_dd = metrics.get('total_dd_pct', 0.0)
        consecutive_losses = int(metrics.get('consecutive_losses', 0))
        api_errors = int(metrics.get('api_errors_1h', 0))
        
        # Check HALT triggers first (most severe)
        if total_dd <= -self.config.halt_dd_pct:
            triggered_level = RiskLevel.HALT
            trigger_reasons.append(f"Total DD {total_dd:.1f}% exceeds -{self.config.halt_dd_pct}%")
        
        # Check HARD triggers
        if daily_pnl <= -self.config.hard_daily_loss_pct:
            if triggered_level < RiskLevel.HARD:
                triggered_level = RiskLevel.HARD
            trigger_reasons.append(f"Daily loss {daily_pnl:.1f}% exceeds -{self.config.hard_daily_loss_pct}%")
        
        if consecutive_losses >= self.config.hard_consecutive_losses:
            if triggered_level < RiskLevel.HARD:
                triggered_level = RiskLevel.HARD
            trigger_reasons.append(f"Consecutive losses {consecutive_losses} >= {self.config.hard_consecutive_losses}")
        
        if api_errors >= self.config.hard_api_errors:
            if triggered_level < RiskLevel.HARD:
                triggered_level = RiskLevel.HARD
            trigger_reasons.append(f"API errors {api_errors}/h >= {self.config.hard_api_errors}")
        
        # Check SOFT triggers
        if daily_pnl <= -self.config.soft_daily_loss_pct:
            if triggered_level < RiskLevel.SOFT:
                triggered_level = RiskLevel.SOFT
            if f"Daily loss" not in str(trigger_reasons):
                trigger_reasons.append(f"Daily loss {daily_pnl:.1f}% exceeds -{self.config.soft_daily_loss_pct}%")
        
        if consecutive_losses >= self.config.soft_consecutive_losses:
            if triggered_level < RiskLevel.SOFT:
                triggered_level = RiskLevel.SOFT
            if f"Consecutive losses" not in str(trigger_reasons):
                trigger_reasons.append(f"Consecutive losses {consecutive_losses} >= {self.config.soft_consecutive_losses}")
        
        if api_errors >= self.config.soft_api_errors:
            if triggered_level < RiskLevel.SOFT:
                triggered_level = RiskLevel.SOFT
            if f"API errors" not in str(trigger_reasons):
                trigger_reasons.append(f"API errors {api_errors}/h >= {self.config.soft_api_errors}")
        
        # Log check
        self._log.append({
            "timestamp": time.time(),
            "action": "check_triggers",
            "metrics": metrics,
            "triggered_level": triggered_level.value,
            "reasons": trigger_reasons
        })
        
        return triggered_level
    
    def activate(self, level: RiskLevel, reason: str) -> None:
        """
        Activate kill-switch at specified level.
        
        Args:
            level: Target level (must be >= current)
            reason: Human-readable reason for activation
        
        Raises:
            ValueError: If level < current level (use attempt_recovery instead)
        """
        if level < self.state.level:
            raise ValueError(
                f"Cannot decrease level from {self.state.level.value} to {level.value}. "
                f"Use attempt_recovery() instead."
            )
        
        if level == self.state.level:
            # Already at this level, just update reason
            self.state.reason = reason
            return
        
        # Record transition
        old_level = self.state.level
        now = time.time()
        
        self.state.transitions.append((
            now,
            old_level.value,
            level.value,
            reason
        ))
        
        self.state.level = level
        self.state.activated_at = now
        self.state.reason = reason
        
        self._log.append({
            "timestamp": now,
            "action": "activate",
            "from_level": old_level.value,
            "to_level": level.value,
            "reason": reason
        })
    
    def attempt_recovery(self, target_level: RiskLevel, confirm: bool = False) -> bool:
        """
        Attempt to recover to a lower risk level.
        
        Args:
            target_level: Desired level (must be < current)
            confirm: Required True for HALT recovery
        
        Returns:
            True if recovery successful, False if conditions not met
        """
        if target_level >= self.state.level:
            return False  # Not a recovery
        
        # HALT recovery requires explicit confirmation
        if self.state.level == RiskLevel.HALT and not confirm:
            self._log.append({
                "timestamp": time.time(),
                "action": "recovery_denied",
                "reason": "HALT recovery requires confirm=True"
            })
            return False
        
        # Check recovery wait times
        if self.state.activated_at:
            hours_elapsed = (time.time() - self.state.activated_at) / 3600
            
            required_hours = 0
            if self.state.level == RiskLevel.SOFT:
                required_hours = self.config.soft_recovery_hours
            elif self.state.level == RiskLevel.HARD:
                required_hours = self.config.hard_recovery_hours
            elif self.state.level == RiskLevel.HALT:
                required_hours = self.config.halt_recovery_hours
            
            if hours_elapsed < required_hours:
                self._log.append({
                    "timestamp": time.time(),
                    "action": "recovery_denied",
                    "reason": f"Only {hours_elapsed:.1f}h elapsed, need {required_hours}h"
                })
                return False
        
        # Perform recovery
        old_level = self.state.level
        now = time.time()
        
        self.state.transitions.append((
            now,
            old_level.value,
            target_level.value,
            f"Recovery after {hours_elapsed:.1f}h" if self.state.activated_at else "Manual recovery"
        ))
        
        self.state.level = target_level
        if target_level == RiskLevel.NORMAL:
            self.state.activated_at = None
            self.state.reason = ""
        
        self._log.append({
            "timestamp": now,
            "action": "recovery",
            "from_level": old_level.value,
            "to_level": target_level.value
        })
        
        return True
    
    def force_recovery(self, target_level: RiskLevel, reason: str) -> None:
        """
        Force recovery (emergency use only, bypasses wait times).
        
        This should only be used by the system owner with full understanding
        of the risks involved.
        """
        old_level = self.state.level
        now = time.time()
        
        self.state.transitions.append((
            now,
            old_level.value,
            target_level.value,
            f"FORCED: {reason}"
        ))
        
        self.state.level = target_level
        if target_level == RiskLevel.NORMAL:
            self.state.activated_at = None
            self.state.reason = ""
        
        self._log.append({
            "timestamp": now,
            "action": "force_recovery",
            "from_level": old_level.value,
            "to_level": target_level.value,
            "reason": reason,
            "WARNING": "Recovery wait times bypassed"
        })
    
    def get_level(self) -> RiskLevel:
        """Return current risk level."""
        return self.state.level
    
    def get_state(self) -> dict:
        """Return full state for serialization."""
        return {
            **self.state.to_dict(),
            "config": {
                "soft_daily_loss_pct": self.config.soft_daily_loss_pct,
                "hard_daily_loss_pct": self.config.hard_daily_loss_pct,
                "halt_dd_pct": self.config.halt_dd_pct
            }
        }
    
    def can_trade(self) -> bool:
        """Check if new trades are allowed."""
        return self.state.level == RiskLevel.NORMAL
    
    def should_close_all(self) -> bool:
        """Check if all positions should be closed."""
        return self.state.level >= RiskLevel.HARD
    
    def should_disconnect(self) -> bool:
        """Check if exchange connection should be terminated."""
        return self.state.level == RiskLevel.HALT
    
    def get_log(self) -> List[dict]:
        """Return activity log for audit."""
        return self._log.copy()
    
    def save_state(self, path: Path) -> None:
        """Save state to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.get_state(), f, indent=2)
    
    @classmethod
    def load_state(cls, path: Path, config: Optional[KillSwitchConfig] = None) -> 'KillSwitch':
        """Load state from JSON file."""
        ks = cls(config)
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
                ks.state.level = RiskLevel(data.get('level', 'NORMAL'))
                ks.state.activated_at = data.get('activated_at')
                ks.state.reason = data.get('reason', '')
        return ks


# Convenience functions for integration
def check_and_activate(ks: KillSwitch, metrics: Dict[str, float]) -> RiskLevel:
    """
    Check triggers and automatically activate if triggered.
    
    Returns the resulting level.
    """
    triggered = ks.check_triggers(metrics)
    if triggered > ks.get_level():
        ks.activate(triggered, f"Auto-triggered by metrics")
    return ks.get_level()
