"""
Unit Tests for Kill-Switch Module

Tests P20-001, P20-002, P20-004 acceptance criteria:
- SOFT triggers on 3% daily loss
- HARD triggers on 5% daily loss
- HALT triggers on 8% total drawdown
- Level cannot decrease without explicit recovery
- HALT recovery requires confirm=True
- All transitions logged

Author: Opus (implementing P20-003)
Date: 2026-02-07
"""

import pytest
import time
from pathlib import Path
import tempfile

from argus_py.risk.kill_switch import (
    KillSwitch,
    KillSwitchConfig,
    RiskLevel,
    check_and_activate
)


class TestRiskLevelOrdering:
    """Test RiskLevel enum ordering."""
    
    def test_normal_is_lowest(self):
        assert RiskLevel.NORMAL < RiskLevel.SOFT
        assert RiskLevel.NORMAL < RiskLevel.HARD
        assert RiskLevel.NORMAL < RiskLevel.HALT
    
    def test_halt_is_highest(self):
        assert RiskLevel.HALT > RiskLevel.NORMAL
        assert RiskLevel.HALT > RiskLevel.SOFT
        assert RiskLevel.HALT > RiskLevel.HARD
    
    def test_ordering_chain(self):
        assert RiskLevel.NORMAL < RiskLevel.SOFT < RiskLevel.HARD < RiskLevel.HALT


class TestKillSwitchInitialization:
    """Test initialization and defaults."""
    
    def test_default_config(self):
        ks = KillSwitch()
        assert ks.config.soft_daily_loss_pct == 3.0
        assert ks.config.hard_daily_loss_pct == 5.0
        assert ks.config.halt_dd_pct == 8.0
    
    def test_starts_at_normal(self):
        ks = KillSwitch()
        assert ks.get_level() == RiskLevel.NORMAL
    
    def test_can_trade_initially(self):
        ks = KillSwitch()
        assert ks.can_trade() is True
    
    def test_custom_config(self):
        config = KillSwitchConfig(soft_daily_loss_pct=2.0, halt_dd_pct=10.0)
        ks = KillSwitch(config)
        assert ks.config.soft_daily_loss_pct == 2.0
        assert ks.config.halt_dd_pct == 10.0


class TestSoftTriggers:
    """Test SOFT level triggers."""
    
    def test_soft_on_3pct_daily_loss(self):
        """SOFT triggers on 3% daily loss."""
        ks = KillSwitch()
        level = ks.check_triggers({'daily_pnl_pct': -3.5})
        assert level == RiskLevel.SOFT
    
    def test_no_trigger_under_threshold(self):
        """No trigger if under 3% loss."""
        ks = KillSwitch()
        level = ks.check_triggers({'daily_pnl_pct': -2.5})
        assert level == RiskLevel.NORMAL
    
    def test_soft_on_consecutive_losses(self):
        """SOFT triggers on 3 consecutive losses."""
        ks = KillSwitch()
        level = ks.check_triggers({'consecutive_losses': 3})
        assert level == RiskLevel.SOFT
    
    def test_soft_on_api_errors(self):
        """SOFT triggers on 5 API errors per hour."""
        ks = KillSwitch()
        level = ks.check_triggers({'api_errors_1h': 5})
        assert level == RiskLevel.SOFT


class TestHardTriggers:
    """Test HARD level triggers."""
    
    def test_hard_on_5pct_daily_loss(self):
        """HARD triggers on 5% daily loss."""
        ks = KillSwitch()
        level = ks.check_triggers({'daily_pnl_pct': -5.5})
        assert level == RiskLevel.HARD
    
    def test_hard_on_5_consecutive_losses(self):
        """HARD triggers on 5 consecutive losses."""
        ks = KillSwitch()
        level = ks.check_triggers({'consecutive_losses': 5})
        assert level == RiskLevel.HARD
    
    def test_hard_on_10_api_errors(self):
        """HARD triggers on 10 API errors per hour."""
        ks = KillSwitch()
        level = ks.check_triggers({'api_errors_1h': 10})
        assert level == RiskLevel.HARD


class TestHaltTriggers:
    """Test HALT level triggers."""
    
    def test_halt_on_8pct_drawdown(self):
        """HALT triggers on 8% total drawdown."""
        ks = KillSwitch()
        level = ks.check_triggers({'total_dd_pct': -8.5})
        assert level == RiskLevel.HALT
    
    def test_halt_overrides_lower_triggers(self):
        """HALT takes precedence over SOFT/HARD triggers."""
        ks = KillSwitch()
        level = ks.check_triggers({
            'daily_pnl_pct': -3.5,  # Would trigger SOFT
            'total_dd_pct': -9.0    # Triggers HALT
        })
        assert level == RiskLevel.HALT


class TestActivation:
    """Test kill-switch activation."""
    
    def test_activate_soft(self):
        ks = KillSwitch()
        ks.activate(RiskLevel.SOFT, "Test activation")
        assert ks.get_level() == RiskLevel.SOFT
        assert ks.can_trade() is False
    
    def test_activate_hard(self):
        ks = KillSwitch()
        ks.activate(RiskLevel.HARD, "Test activation")
        assert ks.get_level() == RiskLevel.HARD
        assert ks.should_close_all() is True
    
    def test_activate_halt(self):
        ks = KillSwitch()
        ks.activate(RiskLevel.HALT, "Test activation")
        assert ks.get_level() == RiskLevel.HALT
        assert ks.should_disconnect() is True
    
    def test_cannot_decrease_level_via_activate(self):
        """Level cannot decrease without explicit recovery."""
        ks = KillSwitch()
        ks.activate(RiskLevel.HARD, "Initial")
        
        with pytest.raises(ValueError) as exc_info:
            ks.activate(RiskLevel.SOFT, "Try to decrease")
        
        assert "Cannot decrease level" in str(exc_info.value)
        assert ks.get_level() == RiskLevel.HARD  # Unchanged
    
    def test_activation_records_transition(self):
        ks = KillSwitch()
        ks.activate(RiskLevel.SOFT, "First activation")
        ks.activate(RiskLevel.HARD, "Escalation")
        
        assert len(ks.state.transitions) == 2
        assert ks.state.transitions[0][2] == "SOFT"
        assert ks.state.transitions[1][2] == "HARD"


class TestRecovery:
    """Test recovery logic."""
    
    def test_halt_recovery_requires_confirm(self):
        """HALT recovery requires confirm=True."""
        ks = KillSwitch(KillSwitchConfig(halt_recovery_hours=0))  # No wait
        ks.activate(RiskLevel.HALT, "Test")
        
        # Without confirm=True, recovery fails
        result = ks.attempt_recovery(RiskLevel.NORMAL, confirm=False)
        assert result is False
        assert ks.get_level() == RiskLevel.HALT
        
        # With confirm=True, recovery succeeds
        result = ks.attempt_recovery(RiskLevel.NORMAL, confirm=True)
        assert result is True
        assert ks.get_level() == RiskLevel.NORMAL
    
    def test_recovery_respects_wait_time(self):
        """Recovery fails if wait time not elapsed."""
        ks = KillSwitch(KillSwitchConfig(soft_recovery_hours=1.0))
        ks.activate(RiskLevel.SOFT, "Test")
        
        # Immediate recovery should fail
        result = ks.attempt_recovery(RiskLevel.NORMAL)
        assert result is False
        assert ks.get_level() == RiskLevel.SOFT
    
    def test_force_recovery_bypasses_wait(self):
        """Force recovery bypasses wait times."""
        ks = KillSwitch(KillSwitchConfig(soft_recovery_hours=100.0))
        ks.activate(RiskLevel.SOFT, "Test")
        
        ks.force_recovery(RiskLevel.NORMAL, "Emergency override")
        assert ks.get_level() == RiskLevel.NORMAL


class TestStatePersistence:
    """Test state save/load."""
    
    def test_save_and_load_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "kill_switch_state.json"
            
            # Create and activate
            ks1 = KillSwitch()
            ks1.activate(RiskLevel.SOFT, "Test reason")
            ks1.save_state(path)
            
            # Load in new instance
            ks2 = KillSwitch.load_state(path)
            assert ks2.get_level() == RiskLevel.SOFT
    
    def test_load_nonexistent_file_starts_normal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"
            ks = KillSwitch.load_state(path)
            assert ks.get_level() == RiskLevel.NORMAL


class TestConvenienceFunctions:
    """Test helper functions."""
    
    def test_check_and_activate(self):
        ks = KillSwitch()
        level = check_and_activate(ks, {'daily_pnl_pct': -4.0})
        
        assert level == RiskLevel.SOFT
        assert ks.get_level() == RiskLevel.SOFT  # Actually activated
    
    def test_check_and_activate_no_escalation_if_same(self):
        ks = KillSwitch()
        ks.activate(RiskLevel.SOFT, "Already soft")
        
        # Same level trigger should not change anything
        level = check_and_activate(ks, {'daily_pnl_pct': -3.5})
        assert level == RiskLevel.SOFT


class TestBypassPrevention:
    """Test that bypass attempts are blocked (P20-004)."""
    
    def test_cannot_skip_levels(self):
        """Activating at HARD when at SOFT is allowed (escalation)."""
        ks = KillSwitch()
        ks.activate(RiskLevel.SOFT, "First")
        ks.activate(RiskLevel.HARD, "Escalate")  # Should work
        assert ks.get_level() == RiskLevel.HARD
    
    def test_cannot_bypass_via_new_instance(self):
        """New instance starts at NORMAL, but saved state should be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            
            ks1 = KillSwitch()
            ks1.activate(RiskLevel.HALT, "Critical")
            ks1.save_state(path)
            
            # Creating new instance and loading saved state
            ks2 = KillSwitch.load_state(path)
            assert ks2.get_level() == RiskLevel.HALT
            assert ks2.can_trade() is False
    
    def test_recovery_to_higher_level_fails(self):
        """Cannot 'recover' to a higher level."""
        ks = KillSwitch()
        ks.activate(RiskLevel.SOFT, "Test")
        
        result = ks.attempt_recovery(RiskLevel.HARD)
        assert result is False  # Not a valid recovery


class TestLogging:
    """Test audit logging."""
    
    def test_all_checks_logged(self):
        ks = KillSwitch()
        ks.check_triggers({'daily_pnl_pct': -1.0})
        ks.check_triggers({'daily_pnl_pct': -4.0})
        
        log = ks.get_log()
        assert len(log) == 2
        assert all(entry['action'] == 'check_triggers' for entry in log)
    
    def test_activations_logged(self):
        ks = KillSwitch()
        ks.activate(RiskLevel.SOFT, "Test")
        
        log = ks.get_log()
        activation_logs = [e for e in log if e['action'] == 'activate']
        assert len(activation_logs) == 1
        assert activation_logs[0]['to_level'] == 'SOFT'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
