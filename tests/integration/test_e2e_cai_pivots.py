"""E2E integration tests for ARGUS CAI Pivots — composed module validation.

Covers:
  1. Pre-trade sizing → Gate 9 approval/rejection
  2. Dynamic exit FSM progression (LONG & SHORT)
  3. Shadow intent emission
  4. Hyper-precision entry → execution → dynamic exit → partial close
  5. Whale momentum boost in pipeline context
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from src.risk.validated_sizer import compute_validated_size
from src.v25.contracts.validated_sizing import ValidatedSizing
from src.execution.dynamic_exit import init_dynamic_exit, update_dynamic_exit_with_action
from src.v25.contracts.dynamic_exit import ExitStage, ExitActionType
from src.execution.hermes_position_manager import HermesPositionManager
from src.v25.contracts.order_intent import OrderIntentType
from src.execution.executor import Executor
from src.execution.hyper_precision import snipe_entry, compute_trailing_sl
from src.engines.hermes.whale_momentum import (
    compute_whale_momentum,
    apply_whale_boost_to_signal,
)
from src.v25.contracts.intelligence import WhaleAlert, WhaleDirection, WhaleMomentumSignal
from src.core.types import Decision, ExecutionResult


# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------
_NOW = datetime.now(timezone.utc)


class FakeBroker:
    """Minimal broker double implementing both BrokerAdapter and HermesBrokerAdapter."""

    def __init__(self) -> None:
        self.orders: list[dict[str, Any]] = []
        self.stop_modifications: list[dict[str, Any]] = []
        self.tp_modifications: list[dict[str, Any]] = []
        self.closed_positions: list[dict[str, Any]] = []

    # --- BrokerAdapter (Executor) ---
    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        size: float,
        order_type: str,
        urgency: str,
    ) -> dict[str, Any]:
        record = {
            "order_id": f"ORD-{len(self.orders)+1}",
            "symbol": symbol,
            "side": side,
            "size": size,
            "order_type": order_type,
            "urgency": urgency,
            "fill_price": 100.0,
            "fill_quantity": size,
            "slippage": 0.0001,
            "fees": 0.01,
        }
        self.orders.append(record)
        return record

    # --- HermesBrokerAdapter ---
    def modify_stop_loss(self, *, symbol: str, stop_price: float) -> None:
        self.stop_modifications.append({"symbol": symbol, "stop_price": stop_price})

    def modify_take_profit(self, *, symbol: str, tp_price: float) -> None:
        self.tp_modifications.append({"symbol": symbol, "tp_price": tp_price})

    def close_position(self, *, symbol: str, reason: str) -> None:
        self.closed_positions.append({"symbol": symbol, "reason": reason})


def _make_decision(**overrides: Any) -> Decision:
    """Build a minimal Decision with sensible defaults."""
    defaults: dict[str, Any] = {
        "action": "long",
        "asset_class": "crypto",
        "symbol": "BTCUSDT",
        "execution_mode": "auto",
        "position_size": 0.02,
        "leverage": 1.0,
        "stop_loss": 0.01,
        "take_profit": 0.03,
        "confidence": 0.85,
        "reason": "test_signal",
        "suggested_entry_price": 100.0,
        "timestamp": _NOW,
    }
    defaults.update(overrides)
    return Decision(**defaults)


# ===================================================================
# 1. TestSizingToGate9Flow
# ===================================================================
class TestSizingToGate9Flow:
    """Validated sizing → Gate 9 breakeven-R approval / rejection."""

    def test_approved_trade_passes_gate9(self) -> None:
        """Normal trade: fees are small fraction of risk → approved."""
        vs = compute_validated_size(
            symbol="BTCUSDT",
            ts=_NOW,
            risk_usd=Decimal("100"),
            sl_pct=Decimal("0.01"),     # 1 % stop
            fee_bps=Decimal("5"),       # 0.05 %
            slippage_bps=Decimal("3"),   # 0.03 %
        )
        assert isinstance(vs, ValidatedSizing)
        assert vs.passed_gate9 is True
        assert vs.reason == "ok"
        assert vs.fee_risk_ratio < Decimal("0.30")

    def test_rejected_trade_fails_gate9(self) -> None:
        """Fees > 30 % of risk budget → Gate 9 rejection."""
        # Use a very tight stop (0.01 %) with large fee basis points
        # so fee_round_trip_pct dominates sl_pct.
        vs = compute_validated_size(
            symbol="BTCUSDT",
            ts=_NOW,
            risk_usd=Decimal("100"),
            sl_pct=Decimal("0.0001"),   # 0.01 % (very tight)
            fee_bps=Decimal("50"),      # 0.5 %
            slippage_bps=Decimal("30"), # 0.3 %
        )
        assert vs.passed_gate9 is False
        assert "gate9_fail" in vs.reason
        assert vs.fee_risk_ratio > Decimal("0.30")

    def test_fee_adjusted_formula_total_risk_within_budget(self) -> None:
        """Verify math: notional * sl_pct + fee_est_usd == risk_usd."""
        risk = Decimal("200")
        sl_pct = Decimal("0.02")
        vs = compute_validated_size(
            symbol="ETHUSDT",
            ts=_NOW,
            risk_usd=risk,
            sl_pct=sl_pct,
            fee_bps=Decimal("8"),
            slippage_bps=Decimal("4"),
        )
        sl_loss = vs.notional_usd * sl_pct
        total_risk = sl_loss + vs.fee_est_usd
        # Allow tiny rounding drift (< 0.01 USD)
        assert abs(total_risk - risk) < Decimal("0.01"), (
            f"sl_loss({sl_loss}) + fee({vs.fee_est_usd}) = {total_risk} != risk({risk})"
        )


# ===================================================================
# 2. TestDynamicExitProgression
# ===================================================================
class TestDynamicExitProgression:
    """Full FSM progression ENTRY → BREAKEVEN_LOCK → PROFIT_CAPTURE → TREND_RIDER."""

    _ENTRY = Decimal("100")
    _SL_PCT = Decimal("0.02")
    _R_VALUE = Decimal("0.02")
    _ATR = Decimal("0.005")

    # R-multiples at which transitions fire (defaults: 0.5, 1.5, 3.0)
    # Price offsets for LONG: entry * (1 + r_value * r_mult)
    # +0.5R → 100*(1+0.02*0.5) = 101.0
    # +1.5R → 100*(1+0.02*1.5) = 103.0
    # +3.0R → 100*(1+0.02*3.0) = 106.0

    def _init_long(self) -> Any:
        return init_dynamic_exit(
            entry_price=self._ENTRY,
            sl_pct=self._SL_PCT,
            r_value_pct=self._R_VALUE,
            atr_pct=self._ATR,
            ts=_NOW,
            side="LONG",
        )

    def _init_short(self) -> Any:
        return init_dynamic_exit(
            entry_price=self._ENTRY,
            sl_pct=self._SL_PCT,
            r_value_pct=self._R_VALUE,
            atr_pct=self._ATR,
            ts=_NOW,
            side="SHORT",
        )

    def test_long_full_progression(self) -> None:
        state = self._init_long()
        assert state.stage == ExitStage.ENTRY

        # +0.5R → BREAKEVEN_LOCK
        price_be = Decimal("101.1")  # slightly above +0.5R threshold
        state, action = update_dynamic_exit_with_action(
            state=state, current_price=price_be, atr_pct=self._ATR, ts=_NOW,
        )
        assert state.stage == ExitStage.BREAKEVEN_LOCK
        assert action.action_type == ExitActionType.UPDATE_STOP

        # +1.5R → PROFIT_CAPTURE
        price_pc = Decimal("103.1")
        state, action = update_dynamic_exit_with_action(
            state=state, current_price=price_pc, atr_pct=self._ATR, ts=_NOW,
        )
        assert state.stage == ExitStage.PROFIT_CAPTURE
        assert action.action_type == ExitActionType.TAKE_PARTIAL

        # +3.0R → TREND_RIDER
        price_tr = Decimal("106.1")
        state, action = update_dynamic_exit_with_action(
            state=state, current_price=price_tr, atr_pct=self._ATR, ts=_NOW,
        )
        assert state.stage == ExitStage.TREND_RIDER
        assert action.action_type == ExitActionType.TAKE_PARTIAL

    def test_short_full_progression(self) -> None:
        state = self._init_short()
        assert state.stage == ExitStage.ENTRY

        # For SHORT: prices must decrease.
        # entry * (1 - r_value * r_mult)
        # +0.5R → 100*(1-0.02*0.5) = 99.0
        price_be = Decimal("98.9")
        state, action = update_dynamic_exit_with_action(
            state=state, current_price=price_be, atr_pct=self._ATR, ts=_NOW,
        )
        assert state.stage == ExitStage.BREAKEVEN_LOCK
        assert action.action_type == ExitActionType.UPDATE_STOP

        # +1.5R → 100*(1-0.02*1.5) = 97.0
        price_pc = Decimal("96.9")
        state, action = update_dynamic_exit_with_action(
            state=state, current_price=price_pc, atr_pct=self._ATR, ts=_NOW,
        )
        assert state.stage == ExitStage.PROFIT_CAPTURE
        assert action.action_type == ExitActionType.TAKE_PARTIAL

        # +3.0R → 100*(1-0.02*3.0) = 94.0
        price_tr = Decimal("93.9")
        state, action = update_dynamic_exit_with_action(
            state=state, current_price=price_tr, atr_pct=self._ATR, ts=_NOW,
        )
        assert state.stage == ExitStage.TREND_RIDER
        assert action.action_type == ExitActionType.TAKE_PARTIAL

    def test_monotonic_sl_long(self) -> None:
        """Stop-loss must only move UP through LONG progression."""
        state = self._init_long()
        stops: list[Decimal] = [state.stop_price]

        for price in [Decimal("101.1"), Decimal("103.1"), Decimal("106.1")]:
            state, _ = update_dynamic_exit_with_action(
                state=state, current_price=price, atr_pct=self._ATR, ts=_NOW,
            )
            stops.append(state.stop_price)

        for i in range(1, len(stops)):
            assert stops[i] >= stops[i - 1], (
                f"LONG stop moved down: {stops[i-1]} -> {stops[i]}"
            )

    def test_monotonic_sl_short(self) -> None:
        """Stop-loss must only move DOWN through SHORT progression."""
        state = self._init_short()
        stops: list[Decimal] = [state.stop_price]

        for price in [Decimal("98.9"), Decimal("96.9"), Decimal("93.9")]:
            state, _ = update_dynamic_exit_with_action(
                state=state, current_price=price, atr_pct=self._ATR, ts=_NOW,
            )
            stops.append(state.stop_price)

        for i in range(1, len(stops)):
            assert stops[i] <= stops[i - 1], (
                f"SHORT stop moved up: {stops[i-1]} -> {stops[i]}"
            )


# ===================================================================
# 3. TestShadowIntentEmission
# ===================================================================
class TestShadowIntentEmission:
    """Shadow dynamic exit intents emit correct OrderIntents."""

    def _make_manager(self) -> tuple[HermesPositionManager, FakeBroker]:
        broker = FakeBroker()
        mgr = HermesPositionManager(broker=broker, shadow_enabled=True)
        return mgr, broker

    def _make_position(
        self,
        entry: float,
        current: float,
        *,
        side: str = "LONG",
        symbol: str = "BTCUSDT",
        position_id: str = "pos-1",
    ) -> dict[str, float | str]:
        return {
            "symbol": symbol,
            "position_id": position_id,
            "entry_price": entry,
            "current_price": current,
            "side": side,
            "sl_pct": 0.02,
            "r_value_pct": 0.02,
            "atr_pct": 0.005,
        }

    def test_shadow_emits_update_stop_intent(self) -> None:
        """Price at +0.5R should emit UPDATE_STOP intent."""
        mgr, _ = self._make_manager()
        # entry=100, +0.5R for LONG = 101.0; use 101.1 to be safely above
        positions = [self._make_position(100.0, 101.1)]
        intents = mgr.shadow_dynamic_exit_intents(positions=positions, ts=_NOW)
        assert len(intents) >= 1
        stop_intents = [i for i in intents if i.action_type == OrderIntentType.UPDATE_STOP]
        assert len(stop_intents) == 1
        assert stop_intents[0].symbol == "BTCUSDT"

    def test_shadow_emits_take_partial_intent(self) -> None:
        """Price at +1.5R should emit TAKE_PARTIAL intent (after breakeven)."""
        mgr, _ = self._make_manager()
        pos = self._make_position(100.0, 101.1)
        # First call: triggers BREAKEVEN_LOCK → UPDATE_STOP
        mgr.shadow_dynamic_exit_intents(positions=[pos], ts=_NOW)

        # Second call: push price to +1.5R (103.1) → PROFIT_CAPTURE
        pos2 = self._make_position(100.0, 103.1)
        intents = mgr.shadow_dynamic_exit_intents(positions=[pos2], ts=_NOW)
        partial_intents = [i for i in intents if i.action_type == OrderIntentType.TAKE_PARTIAL]
        assert len(partial_intents) == 1

    def test_shadow_suppresses_noop(self) -> None:
        """NOOP intents must NOT appear in emitted intents."""
        mgr, _ = self._make_manager()
        # Price at entry level — no transition → NOOP (should be suppressed)
        positions = [self._make_position(100.0, 100.0)]
        intents = mgr.shadow_dynamic_exit_intents(positions=positions, ts=_NOW)
        noop_intents = [i for i in intents if i.action_type == OrderIntentType.NOOP]
        assert len(noop_intents) == 0


# ===================================================================
# 4. TestPrecisionExecutionFlow
# ===================================================================
class TestPrecisionExecutionFlow:
    """Hyper-precision entry → execution → dynamic exit → partial close."""

    def test_precision_entry_limit_then_partial_close(self) -> None:
        """Execute with precision (good OBI) then partial-close."""
        broker = FakeBroker()
        executor = Executor(broker=broker)
        decision = _make_decision(
            action="long",
            suggested_entry_price=100.0,
            confidence=0.85,
        )

        # Execute with precision — OBI=0.75 (above 0.60 threshold) favours LONG limit
        exec_result, precision = executor.execute_with_precision(
            decision=decision,
            urgency="NORMAL",
            obi=0.75,
            vwap_dev_pct=0.001,
            spread_pct=0.001,
            median_spread_pct=0.001,
            atr_pct=0.01,
        )

        assert exec_result.success is True
        assert precision.order_type == "limit"
        assert precision.reason == "obi_ok_limit"
        assert len(broker.orders) == 1
        assert broker.orders[0]["order_type"] == "limit"

        # Now do a partial close
        exec_partial, pr_exit = executor.execute_partial_close(
            symbol="BTCUSDT",
            direction="LONG",
            pct_to_close=0.30,
            current_price=103.0,
            obi=-0.40,   # sellers appearing → reversal
            vwap_dev_pct=0.001,
            spread_pct=0.001,
            median_spread_pct=0.001,
            urgency="NORMAL",
            total_quantity=0.02,
        )

        assert exec_partial is not None
        assert exec_partial.success is True
        assert len(broker.orders) == 2
        close_order = broker.orders[1]
        assert close_order["side"] == "short"  # closing a LONG
        assert close_order["size"] == pytest.approx(0.02 * 0.30)

    def test_live_exit_updates_broker_sl(self) -> None:
        """live_dynamic_exit_intents should call broker.modify_stop_loss."""
        broker = FakeBroker()
        mgr = HermesPositionManager(broker=broker, shadow_enabled=True)

        # Position at +0.5R → triggers BREAKEVEN_LOCK → UPDATE_STOP
        positions: list[dict[str, float | str]] = [
            {
                "symbol": "BTCUSDT",
                "position_id": "pos-live-1",
                "entry_price": 100.0,
                "current_price": 101.1,
                "side": "LONG",
                "sl_pct": 0.02,
                "r_value_pct": 0.02,
                "atr_pct": 0.005,
            }
        ]

        intents = mgr.live_dynamic_exit_intents(positions=positions, ts=_NOW)
        stop_intents = [i for i in intents if i.action_type == OrderIntentType.UPDATE_STOP]
        assert len(stop_intents) >= 1
        # Broker should have been called
        assert len(broker.stop_modifications) >= 1
        assert broker.stop_modifications[0]["symbol"] == "BTCUSDT"
        assert broker.stop_modifications[0]["stop_price"] > 0


# ===================================================================
# 5. TestWhaleBoostE2E
# ===================================================================
class TestWhaleBoostE2E:
    """Whale momentum boost in pipeline context."""

    @staticmethod
    def _make_whale_alerts(n: int = 3, direction: WhaleDirection = WhaleDirection.OUTFLOW) -> list[WhaleAlert]:
        alerts: list[WhaleAlert] = []
        for i in range(n):
            alerts.append(
                WhaleAlert(
                    chain="ethereum",
                    symbol="BTCUSDT",
                    direction=direction,
                    amount_asset=Decimal("10"),
                    amount_usd=Decimal("500000"),
                    wallet_address=f"0xabc{12345+i:05d}",
                    confidence=Decimal("0.8500000000"),
                    source="whale_alert_api",
                )
            )
        return alerts

    def test_whale_boost_increases_confidence_in_trending(self) -> None:
        """Whale accumulation + TRENDING regime → confidence boosted."""
        alerts = self._make_whale_alerts(n=5, direction=WhaleDirection.OUTFLOW)
        signal = compute_whale_momentum(alerts)

        # Signal should be bullish (outflow = drain = bullish)
        assert signal.is_bullish_flow is True
        assert signal.momentum_score > Decimal("0")

        base_confidence = 0.70
        boosted, was_applied, reason = apply_whale_boost_to_signal(
            base_confidence=base_confidence,
            whale=signal,
            regime="TRENDING",
            regime_confidence=0.80,
            regime_stability=0.75,
        )

        # Should have been applied since TRENDING + high conf/stab = TREND_STRONG
        assert was_applied is True
        assert reason == "whale_boost_applied"
        assert boosted > base_confidence

    def test_whale_boost_blocked_in_ranging(self) -> None:
        """RANGING regime → no whale boost regardless of signal strength."""
        alerts = self._make_whale_alerts(n=5, direction=WhaleDirection.OUTFLOW)
        signal = compute_whale_momentum(alerts)

        base_confidence = 0.70
        boosted, was_applied, reason = apply_whale_boost_to_signal(
            base_confidence=base_confidence,
            whale=signal,
            regime="RANGING",
            regime_confidence=0.90,
            regime_stability=0.90,
        )

        assert was_applied is False
        assert reason == "regime_not_trend_strong"
        assert boosted == base_confidence
