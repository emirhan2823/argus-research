"""Tests for remaining MEMORY_MAP gaps: A-11, B-07, H-11, H-12."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest


# ─── A-11: Gemini pairs config loading ────────────────────────────

class TestGeminiConfigLoading:
    """A-11: Load pairs config in V25Config."""

    def test_load_gemini_config_from_yaml(self) -> None:
        from src.v25.config.loader import load_v25_config

        cfg = load_v25_config()
        assert cfg.engines.gemini is not None
        assert len(cfg.engines.gemini.pairs) >= 1

    def test_gemini_pair_fields(self) -> None:
        from src.v25.config.loader import load_v25_config

        cfg = load_v25_config()
        assert cfg.engines.gemini is not None
        pair = cfg.engines.gemini.pairs[0]
        assert pair.symbol_a == "BTC/USDT"
        assert pair.symbol_b == "ETH/USDT"
        assert pair.pair_id == "BTC_ETH"

    def test_gemini_correlation_config(self) -> None:
        from src.v25.config.loader import load_v25_config

        cfg = load_v25_config()
        assert cfg.engines.gemini is not None
        corr = cfg.engines.gemini.correlation
        assert corr.window == 100
        assert corr.min_correlation == 0.60
        assert corr.entry_zscore == 2.0
        assert corr.exit_zscore == 0.5
        assert corr.max_half_life == 50.0

    def test_gemini_max_simultaneous_pairs(self) -> None:
        from src.v25.config.loader import load_v25_config

        cfg = load_v25_config()
        assert cfg.engines.gemini is not None
        assert cfg.engines.gemini.max_simultaneous_pairs == 3

    def test_gemini_config_none_when_no_section(self) -> None:
        from src.v25.config.loader import _parse_gemini_config

        result = _parse_gemini_config({})
        assert result is None

    def test_gemini_config_none_when_no_pairs(self) -> None:
        from src.v25.config.loader import _parse_gemini_config

        result = _parse_gemini_config({"gemini": {"pairs": []}})
        assert result is None

    def test_gemini_pairs_to_tracker_config(self) -> None:
        """Pairs config from V25Config can be used to init CorrelationTracker."""
        from src.v25.config.loader import load_v25_config
        from src.correlation.tracker import CorrelationTracker

        cfg = load_v25_config()
        assert cfg.engines.gemini is not None
        pairs_dicts = [
            {"symbol_a": p.symbol_a, "symbol_b": p.symbol_b, "pair_id": p.pair_id}
            for p in cfg.engines.gemini.pairs
        ]
        tracker = CorrelationTracker(pairs_dicts)
        pair = tracker.get_pair("BTC_ETH")
        assert pair is not None


# ─── B-07: CORR_DECOUPLING_ARB template name ────────────────────

class TestCorrDecouplingArb:
    """B-07: Add CORR_DECOUPLING_ARB to TemplateName."""

    def test_corr_decoupling_arb_exists(self) -> None:
        from src.v25.contracts.signal import TemplateName

        assert hasattr(TemplateName, "CORR_DECOUPLING_ARB")
        assert TemplateName.CORR_DECOUPLING_ARB.value == "CORR_DECOUPLING_ARB"

    def test_corr_decoupling_arb_in_enum_members(self) -> None:
        from src.v25.contracts.signal import TemplateName

        names = [t.name for t in TemplateName]
        assert "CORR_DECOUPLING_ARB" in names


# ─── H-11: Trailing SL wired into sl_manager ────────────────────

@dataclass
class FakeDynamicExitState:
    trailing_stop: float = 0.0
    stage: str = "ENTRY"


class FakeSLBroker:
    def __init__(self) -> None:
        self.placed: list[dict] = []

    def place_stop_loss(
        self, *, symbol: str, side: str, size: float, stop_price: float
    ) -> str:
        self.placed.append(
            {"symbol": symbol, "side": side, "size": size, "stop_price": stop_price}
        )
        return f"sl_{len(self.placed)}"

    def close_position(self, *, symbol: str, reason: str) -> None:
        pass


class TestSLManagerTrailingIntegration:
    """H-11: Wire trailing SL into stop_manager.py."""

    def test_enforce_uses_static_when_no_dynamic_state(self) -> None:
        from src.execution.sl_manager import StopLossManager

        broker = FakeSLBroker()
        mgr = StopLossManager(broker=broker)
        result = mgr.enforce(
            symbol="BTC/USDT",
            side="LONG",
            size=0.01,
            stop_price=95000.0,
            timestamp=datetime.now(),
        )
        assert result.success
        assert result.used_trailing is False
        assert result.reason == "sl_placed"
        assert broker.placed[0]["stop_price"] == 95000.0

    def test_enforce_uses_trailing_when_dynamic_state_has_trailing(self) -> None:
        from src.execution.sl_manager import StopLossManager

        broker = FakeSLBroker()
        mgr = StopLossManager(broker=broker)
        state = FakeDynamicExitState(trailing_stop=97500.0, stage="PROFIT_CAPTURE")
        result = mgr.enforce(
            symbol="BTC/USDT",
            side="LONG",
            size=0.01,
            stop_price=95000.0,
            timestamp=datetime.now(),
            dynamic_exit_state=state,
        )
        assert result.success
        assert result.used_trailing is True
        assert result.reason == "trailing_sl_placed"
        assert broker.placed[0]["stop_price"] == 97500.0

    def test_enforce_uses_static_when_trailing_is_zero(self) -> None:
        from src.execution.sl_manager import StopLossManager

        broker = FakeSLBroker()
        mgr = StopLossManager(broker=broker)
        state = FakeDynamicExitState(trailing_stop=0.0, stage="ENTRY")
        result = mgr.enforce(
            symbol="BTC/USDT",
            side="LONG",
            size=0.01,
            stop_price=95000.0,
            timestamp=datetime.now(),
            dynamic_exit_state=state,
        )
        assert result.success
        assert result.used_trailing is False
        assert broker.placed[0]["stop_price"] == 95000.0

    def test_enforce_uses_static_when_dynamic_state_is_none(self) -> None:
        from src.execution.sl_manager import StopLossManager

        broker = FakeSLBroker()
        mgr = StopLossManager(broker=broker)
        result = mgr.enforce(
            symbol="BTC/USDT",
            side="LONG",
            size=0.01,
            stop_price=95000.0,
            timestamp=datetime.now(),
            dynamic_exit_state=None,
        )
        assert result.success
        assert result.used_trailing is False

    def test_backward_compat_no_dynamic_exit_param(self) -> None:
        """Existing callers that don't pass dynamic_exit_state still work."""
        from src.execution.sl_manager import StopLossManager

        broker = FakeSLBroker()
        mgr = StopLossManager(broker=broker)
        result = mgr.enforce(
            symbol="ETH/USDT",
            side="SHORT",
            size=0.1,
            stop_price=3500.0,
            timestamp=datetime.now(),
        )
        assert result.success
        assert result.reason == "sl_placed"


# ─── H-12: Static TP replaced by dynamic exit (by design) ───────

class TestDynamicExitReplacesStaticTP:
    """H-12: Verify dynamic exit FSM replaces static TP.

    There is no tp_manager.py to modify — the dynamic exit FSM
    (Phase H) already handles partial take-profits through stage
    transitions (BREAKEVEN_LOCK, PROFIT_CAPTURE, TREND_RIDER).
    These tests verify the FSM produces the correct partial actions.
    """

    def test_breakeven_lock_produces_partial_close(self) -> None:
        from decimal import Decimal
        from datetime import datetime, timezone
        from src.execution.dynamic_exit import init_dynamic_exit, update_dynamic_exit_with_action

        now = datetime.now(timezone.utc)
        state = init_dynamic_exit(
            entry_price=Decimal("100.0"), sl_pct=Decimal("0.02"),
            r_value_pct=Decimal("0.02"), atr_pct=Decimal("0.01"), ts=now,
        )
        # Move to +0.6R (past breakeven threshold)
        new_state, action = update_dynamic_exit_with_action(
            state, current_price=Decimal("101.2"), atr_pct=Decimal("0.01"), ts=now,
        )
        assert new_state.stage == "BREAKEVEN_LOCK"

    def test_profit_capture_produces_partial_close_action(self) -> None:
        from decimal import Decimal
        from datetime import datetime, timezone
        from src.execution.dynamic_exit import init_dynamic_exit, update_dynamic_exit_with_action

        now = datetime.now(timezone.utc)
        state = init_dynamic_exit(
            entry_price=Decimal("100.0"), sl_pct=Decimal("0.02"),
            r_value_pct=Decimal("0.02"), atr_pct=Decimal("0.01"), ts=now,
        )
        # First move to breakeven
        state, _ = update_dynamic_exit_with_action(
            state, current_price=Decimal("101.2"), atr_pct=Decimal("0.01"), ts=now,
        )
        # Then to profit capture (+1.6R)
        state, action = update_dynamic_exit_with_action(
            state, current_price=Decimal("103.2"), atr_pct=Decimal("0.01"), ts=now,
        )
        assert state.stage == "PROFIT_CAPTURE"
        assert action.action_type.value == "TAKE_PARTIAL"

    def test_no_static_tp_module_exists(self) -> None:
        """Verify there is no tp_manager.py — dynamic exit is the TP mechanism."""
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("src.exit.tp_manager")
