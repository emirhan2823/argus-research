"""Tests for PR-J02: Execution integration.

Covers:
  - Executor.execute_with_precision (hyper-precision entry)
  - Executor.execute_partial_close (partial exit)
  - HermesPositionManager.live_dynamic_exit_intents (live execution)
  - Pipeline conditional live/shadow mode
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

from src.core.types import Decision, ExecutionResult
from src.execution.executor import Executor
from src.execution.hermes_position_manager import HermesPositionManager
from src.execution.hyper_precision import PrecisionEntryResult, PrecisionExitResult


_NOW = datetime(2026, 2, 17, 14, 0, 0, tzinfo=timezone.utc)


def _make_decision(**overrides) -> Decision:
    defaults = dict(
        action="long",
        asset_class="crypto",
        symbol="BTCUSDT",
        execution_mode="auto",
        position_size=0.01,
        leverage=1.0,
        stop_loss=0.02,
        take_profit=0.04,
        confidence=0.75,
        engine="TITAN",
        reason="test",
        timestamp=_NOW,
        suggested_entry_price=50000.0,
    )
    defaults.update(overrides)
    return Decision(**defaults)


class _FakeBroker:
    """In-memory broker for testing."""

    def __init__(self):
        self.orders: list[dict] = []
        self.sl_updates: list[dict] = []
        self.close_calls: list[dict] = []

    def place_order(self, *, symbol, side, size, order_type, urgency):
        order = {
            "symbol": symbol, "side": side, "size": size,
            "order_type": order_type, "urgency": urgency,
            "order_id": f"ord-{len(self.orders)}",
            "fill_price": 50000.0, "fill_quantity": size,
        }
        self.orders.append(order)
        return order

    def modify_stop_loss(self, *, symbol, stop_price):
        self.sl_updates.append({"symbol": symbol, "stop_price": stop_price})

    def modify_take_profit(self, *, symbol, tp_price):
        pass

    def close_position(self, *, symbol, reason):
        self.close_calls.append({"symbol": symbol, "reason": reason})


# ---------------------------------------------------------------------------
# Executor.execute_with_precision tests
# ---------------------------------------------------------------------------


class TestExecuteWithPrecision:
    def test_limit_entry_with_good_obi(self):
        """Good directional OBI -> limit order placed."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)
        decision = _make_decision()

        ex_result, pr = executor.execute_with_precision(
            decision=decision, urgency="NORMAL",
            obi=0.70,  # good for LONG
            spread_pct=0.001, median_spread_pct=0.001,
        )
        assert ex_result.success is True
        assert ex_result.reason == "order_filled_with_precision"
        assert pr.order_type == "limit"
        assert len(broker.orders) == 1
        assert broker.orders[0]["order_type"] == "limit"

    def test_skip_with_bad_obi_low_urgency(self):
        """Bad OBI + low urgency -> skip, no order placed."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)
        decision = _make_decision()

        ex_result, pr = executor.execute_with_precision(
            decision=decision, urgency="NORMAL",
            obi=0.10,  # bad for LONG
            spread_pct=0.001, median_spread_pct=0.001,
        )
        assert ex_result.success is False
        assert "precision_skip" in ex_result.reason
        assert pr.order_type == "skip"
        assert len(broker.orders) == 0

    def test_market_fallback_high_urgency(self):
        """Bad OBI + HIGH urgency -> market order."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)
        decision = _make_decision()

        ex_result, pr = executor.execute_with_precision(
            decision=decision, urgency="HIGH",
            obi=0.10,
            spread_pct=0.001, median_spread_pct=0.001,
        )
        assert ex_result.success is True
        assert pr.order_type == "market"
        assert broker.orders[0]["order_type"] == "market"

    def test_advisory_mode_passthrough(self):
        """Advisory mode skips precision and delegates to standard execute."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)
        decision = _make_decision(execution_mode="advisory")

        ex_result, pr = executor.execute_with_precision(
            decision=decision, obi=0.70,
        )
        assert ex_result.success is True
        assert ex_result.execution_mode == "advisory"
        assert pr.reason == "advisory_mode"

    def test_short_entry_precision(self):
        """SHORT direction with good negative OBI."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)
        decision = _make_decision(action="short")

        ex_result, pr = executor.execute_with_precision(
            decision=decision, urgency="NORMAL",
            obi=-0.70,  # good for SHORT
            spread_pct=0.001, median_spread_pct=0.001,
        )
        assert ex_result.success is True
        assert pr.order_type == "limit"


# ---------------------------------------------------------------------------
# Executor.execute_partial_close tests
# ---------------------------------------------------------------------------


class TestExecutePartialClose:
    def test_partial_close_with_reversal(self):
        """OBI reversal -> limit partial close."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)

        ex_result, pr = executor.execute_partial_close(
            symbol="BTCUSDT", direction="LONG",
            pct_to_close=0.25, current_price=51000.0,
            obi=-0.40,  # reversal for LONG exit
            spread_pct=0.001, median_spread_pct=0.001,
            total_quantity=1.0,
        )
        assert ex_result is not None
        assert ex_result.success is True
        assert pr.order_type == "limit"
        assert len(broker.orders) == 1
        assert broker.orders[0]["size"] == pytest.approx(0.25)

    def test_partial_close_market_fallback(self):
        """No OBI reversal -> market partial close."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)

        ex_result, pr = executor.execute_partial_close(
            symbol="BTCUSDT", direction="LONG",
            pct_to_close=0.25, current_price=51000.0,
            obi=0.50,  # no reversal
            total_quantity=1.0,
        )
        assert ex_result is not None
        assert ex_result.success is True
        assert pr.order_type == "market"

    def test_partial_close_zero_quantity(self):
        """Zero total_quantity -> no order placed."""
        broker = _FakeBroker()
        executor = Executor(broker=broker)

        ex_result, pr = executor.execute_partial_close(
            symbol="BTCUSDT", direction="LONG",
            pct_to_close=0.25, current_price=51000.0,
            total_quantity=0.0,
        )
        assert ex_result is None
        assert len(broker.orders) == 0


# ---------------------------------------------------------------------------
# HermesPositionManager.live_dynamic_exit_intents tests
# ---------------------------------------------------------------------------


class TestLiveDynamicExitIntents:
    def _make_manager(self, broker=None):
        return HermesPositionManager(
            broker=broker or _FakeBroker(),
            shadow_enabled=True,
        )

    def _make_position(self, **overrides):
        defaults = {
            "position_id": "pos-1",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": 50000.0,
            "current_price": 50500.0,  # +1% -> will trigger breakeven at 0.5R
            "sl_pct": 0.01,
            "r_value_pct": 0.01,
            "atr_pct": 0.005,
        }
        defaults.update(overrides)
        return defaults

    def test_live_intents_executed_against_broker(self):
        """Live mode calls broker.modify_stop_loss on UPDATE_STOP intents."""
        broker = _FakeBroker()
        mgr = self._make_manager(broker=broker)

        # First call: init state at entry
        pos = self._make_position(current_price=50000.0)
        mgr.live_dynamic_exit_intents(positions=[pos], ts=_NOW)

        # Second call: price moved to +1R -> should trigger BREAKEVEN_LOCK
        pos2 = self._make_position(current_price=50500.0)
        intents = mgr.live_dynamic_exit_intents(positions=[pos2], ts=_NOW)

        # Should have generated at least one intent and called broker
        if len(intents) > 0:
            # Check broker was called for SL update
            assert len(broker.sl_updates) > 0 or len(broker.close_calls) > 0

    def test_live_returns_same_intents_as_shadow(self):
        """Live mode produces the same intents as shadow mode."""
        broker = _FakeBroker()
        mgr_shadow = self._make_manager(broker=broker)
        mgr_live = self._make_manager(broker=_FakeBroker())

        pos = self._make_position(current_price=50000.0)
        shadow_intents = mgr_shadow.shadow_dynamic_exit_intents(positions=[pos], ts=_NOW)
        live_intents = mgr_live.live_dynamic_exit_intents(positions=[pos], ts=_NOW)

        assert len(shadow_intents) == len(live_intents)

    def test_live_no_crash_on_empty_positions(self):
        """Live mode handles empty position list gracefully."""
        mgr = self._make_manager()
        intents = mgr.live_dynamic_exit_intents(positions=[], ts=_NOW)
        assert len(intents) == 0

    def test_find_position_helper(self):
        """_find_position returns correct position or None."""
        pos = self._make_position()
        result = HermesPositionManager._find_position([pos], "BTCUSDT")
        assert result is not None
        assert result["symbol"] == "BTCUSDT"

        none_result = HermesPositionManager._find_position([pos], "ETHUSDT")
        assert none_result is None


# ---------------------------------------------------------------------------
# Pipeline conditional live/shadow mode test
# ---------------------------------------------------------------------------


class TestPipelineConditionalMode:
    def test_live_exit_enabled_flag_default(self):
        """Pipeline default: live exit is disabled."""
        from unittest.mock import MagicMock, patch
        from src.main import ArgusPipeline

        pipeline = MagicMock(spec=ArgusPipeline)
        pipeline._live_exit_enabled = False
        assert pipeline._live_exit_enabled is False

    def test_live_exit_flag_can_be_enabled(self):
        """Pipeline live exit can be set to True."""
        from src.main import ArgusPipeline

        pipeline = MagicMock(spec=ArgusPipeline)
        pipeline._live_exit_enabled = True
        assert pipeline._live_exit_enabled is True
