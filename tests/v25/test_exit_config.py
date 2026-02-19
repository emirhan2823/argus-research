"""Tests for PR-EXIT-CONFIG: dynamic exit config extraction and wiring."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.execution.dynamic_exit import init_dynamic_exit, update_dynamic_exit_with_action
from src.v25.config.loader import DynamicExitConfig
from src.v25.contracts.dynamic_exit import ExitActionType, ExitStage


_TS = datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)
_ENTRY = Decimal("100")
_SL = Decimal("0.02")
_R_VAL = Decimal("0.02")
_ATR = Decimal("0.01")


# ---------------------------------------------------------------------------
# 1. DynamicExitConfig defaults match old hard-coded values
# ---------------------------------------------------------------------------


def test_default_config_matches_old_constants() -> None:
    """DynamicExitConfig() with no args matches the original hard-coded values."""
    cfg = DynamicExitConfig()
    assert cfg.r_breakeven == 0.5
    assert cfg.r_profit_capture == 1.5
    assert cfg.r_trend_rider == 3.0
    assert cfg.atr_mult_profit_capture == 2.0
    assert cfg.atr_mult_trend_rider == 1.2
    assert cfg.partial_fraction_profit_capture == 0.30
    assert cfg.partial_fraction_trend_rider == 0.20


# ---------------------------------------------------------------------------
# 2. init_dynamic_exit uses config R thresholds for TP prices
# ---------------------------------------------------------------------------


def test_init_uses_config_r_thresholds_long() -> None:
    """Custom R thresholds change TP price placement."""
    cfg = DynamicExitConfig(r_breakeven=1.0, r_profit_capture=2.0, r_trend_rider=4.0)

    state = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, side="LONG", config=cfg,
    )
    # tp1 = entry * (1 + r_val * r_breakeven) = 100 * (1 + 0.02 * 1.0) = 102
    assert state.tp1_price == Decimal("100") * (Decimal("1") + Decimal("0.02") * Decimal("1.0"))
    # tp2 = 100 * (1 + 0.02 * 2.0) = 104
    assert state.tp2_price == Decimal("100") * (Decimal("1") + Decimal("0.02") * Decimal("2.0"))
    # tp3 = 100 * (1 + 0.02 * 4.0) = 108
    assert state.tp3_price == Decimal("100") * (Decimal("1") + Decimal("0.02") * Decimal("4.0"))


def test_init_uses_config_r_thresholds_short() -> None:
    """Custom R thresholds work for SHORT positions too."""
    cfg = DynamicExitConfig(r_breakeven=1.0, r_profit_capture=2.0, r_trend_rider=4.0)

    state = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, side="SHORT", config=cfg,
    )
    # tp1 = entry * (1 - r_val * 1.0) = 100 * 0.98 = 98
    assert state.tp1_price == Decimal("100") * (Decimal("1") - Decimal("0.02") * Decimal("1.0"))
    assert state.tp3_price == Decimal("100") * (Decimal("1") - Decimal("0.02") * Decimal("4.0"))


def test_init_without_config_uses_defaults() -> None:
    """config=None produces same result as default DynamicExitConfig()."""
    state_none = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, config=None,
    )
    state_default = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, config=DynamicExitConfig(),
    )
    assert state_none.tp1_price == state_default.tp1_price
    assert state_none.tp2_price == state_default.tp2_price
    assert state_none.tp3_price == state_default.tp3_price


# ---------------------------------------------------------------------------
# 3. update_dynamic_exit_with_action uses config R thresholds
# ---------------------------------------------------------------------------


def test_update_uses_config_breakeven_threshold() -> None:
    """With r_breakeven=1.0, transition requires +1.0R not +0.5R."""
    cfg = DynamicExitConfig(r_breakeven=1.0, r_profit_capture=2.0, r_trend_rider=4.0)

    state = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, config=cfg,
    )

    # At +0.5R (price=101), should NOT transition with r_breakeven=1.0
    price_half_r = Decimal("101")  # 0.5R
    next_state, action = update_dynamic_exit_with_action(
        state=state, current_price=price_half_r, atr_pct=_ATR, ts=_TS, config=cfg,
    )
    assert next_state.stage == ExitStage.ENTRY
    assert action.action_type == ExitActionType.NOOP

    # At +1.0R (price=102), SHOULD transition
    price_one_r = Decimal("102")
    next_state, action = update_dynamic_exit_with_action(
        state=state, current_price=price_one_r, atr_pct=_ATR, ts=_TS, config=cfg,
    )
    assert next_state.stage == ExitStage.BREAKEVEN_LOCK
    assert action.action_type == ExitActionType.UPDATE_STOP


# ---------------------------------------------------------------------------
# 4. Config ATR multipliers affect trailing stop
# ---------------------------------------------------------------------------


def test_update_uses_config_atr_multipliers() -> None:
    """Custom ATR multipliers change trailing stop distance.

    With atr_mult_profit_capture=1.0 (tight) and a high price, the trailing candidate
    exceeds entry so the stop moves up from the breakeven level.
    """
    cfg = DynamicExitConfig(atr_mult_profit_capture=1.0, atr_mult_trend_rider=0.5)

    state = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, config=cfg,
    )

    # Move to BREAKEVEN_LOCK
    price_be = Decimal("101")  # +0.5R
    state, _ = update_dynamic_exit_with_action(
        state=state, current_price=price_be, atr_pct=_ATR, ts=_TS, config=cfg,
    )
    assert state.stage == ExitStage.BREAKEVEN_LOCK

    # Move to PROFIT_CAPTURE at a high price
    price_pc = Decimal("103")  # +1.5R
    state, _ = update_dynamic_exit_with_action(
        state=state, current_price=price_pc, atr_pct=_ATR, ts=_TS, config=cfg,
    )
    assert state.stage == ExitStage.PROFIT_CAPTURE
    # Trailing stop = max(entry, price * (1 - atr * 1.0)) = max(100, 103 * 0.99) = max(100, 101.97) = 101.97
    expected_stop = Decimal("103") * (Decimal("1") - Decimal("0.01") * Decimal("1.0"))
    assert state.stop_price == expected_stop
    assert state.stop_price > _ENTRY  # stop moved above entry due to tight ATR mult


# ---------------------------------------------------------------------------
# 5. Config partial fractions affect action output
# ---------------------------------------------------------------------------


def test_update_uses_config_partial_fractions() -> None:
    """Custom partial fractions appear in TAKE_PARTIAL actions."""
    cfg = DynamicExitConfig(partial_fraction_profit_capture=0.40, partial_fraction_trend_rider=0.15)

    state = init_dynamic_exit(
        entry_price=_ENTRY, sl_pct=_SL, r_value_pct=_R_VAL,
        atr_pct=_ATR, ts=_TS, config=cfg,
    )

    # ENTRY -> BREAKEVEN_LOCK (UPDATE_STOP, no partial)
    state, _ = update_dynamic_exit_with_action(
        state=state, current_price=Decimal("101"), atr_pct=_ATR, ts=_TS, config=cfg,
    )

    # BREAKEVEN_LOCK -> PROFIT_CAPTURE (TAKE_PARTIAL with 0.40)
    state, action = update_dynamic_exit_with_action(
        state=state, current_price=Decimal("103"), atr_pct=_ATR, ts=_TS, config=cfg,
    )
    assert action.action_type == ExitActionType.TAKE_PARTIAL
    assert action.take_profit_fraction == Decimal("0.40")

    # PROFIT_CAPTURE -> TREND_RIDER (TAKE_PARTIAL with 0.15)
    state, action = update_dynamic_exit_with_action(
        state=state, current_price=Decimal("106"), atr_pct=_ATR, ts=_TS, config=cfg,
    )
    assert action.action_type == ExitActionType.TAKE_PARTIAL
    assert action.take_profit_fraction == Decimal("0.15")


# ---------------------------------------------------------------------------
# 6. Config loader from YAML
# ---------------------------------------------------------------------------


def test_config_loader_parses_dynamic_exit(tmp_path) -> None:
    """load_v25_config reads dynamic_exit section from engines.yaml."""
    import yaml

    risk_yaml = tmp_path / "risk.yaml"
    risk_yaml.write_text(yaml.dump({
        "risk": {
            "global_caps": {
                "per_trade_risk_cap": 0.03,
                "min_risk_pct": 0.005,
                "max_position_size": 0.15,
                "max_leverage_core": 2.0,
                "max_leverage_accel": 3.0,
                "max_leverage_global": 3.0,
            },
            "growth_sizer": {"phases": {}},
            "fee_model": {
                "maker_fee_pct": 0.0002,
                "taker_fee_pct": 0.0005,
                "spread_estimate_pct": 0.0001,
                "slippage_base_pct": 0.0003,
                "slippage_per_10k": 0.0001,
                "backtest_cost_mult": 1.5,
            },
        }
    }), encoding="utf-8")

    engines_yaml = tmp_path / "engines.yaml"
    engines_yaml.write_text(yaml.dump({
        "engines": {
            "hermes": {
                "dynamic_exit": {
                    "r_breakeven": 0.75,
                    "r_profit_capture": 2.0,
                    "r_trend_rider": 5.0,
                    "atr_mult_profit_capture": 2.5,
                    "atr_mult_trend_rider": 1.0,
                    "partial_fraction_profit_capture": 0.35,
                    "partial_fraction_trend_rider": 0.25,
                }
            },
            "dual_speed": {"accel": {}},
        }
    }), encoding="utf-8")

    from src.v25.config.loader import load_v25_config
    cfg = load_v25_config(
        risk_yaml_path=str(risk_yaml),
        engines_yaml_path=str(engines_yaml),
    )

    de = cfg.engines.dynamic_exit
    assert de.r_breakeven == 0.75
    assert de.r_profit_capture == 2.0
    assert de.r_trend_rider == 5.0
    assert de.atr_mult_profit_capture == 2.5
    assert de.atr_mult_trend_rider == 1.0
    assert de.partial_fraction_profit_capture == 0.35
    assert de.partial_fraction_trend_rider == 0.25


def test_config_loader_defaults_when_no_dynamic_exit_section(tmp_path) -> None:
    """Missing dynamic_exit section uses defaults."""
    import yaml

    risk_yaml = tmp_path / "risk.yaml"
    risk_yaml.write_text(yaml.dump({
        "risk": {
            "global_caps": {},
            "growth_sizer": {"phases": {}},
            "fee_model": {
                "maker_fee_pct": 0.0002,
                "taker_fee_pct": 0.0005,
                "spread_estimate_pct": 0.0001,
                "slippage_base_pct": 0.0003,
                "slippage_per_10k": 0.0001,
                "backtest_cost_mult": 1.5,
            },
        }
    }), encoding="utf-8")

    engines_yaml = tmp_path / "engines.yaml"
    engines_yaml.write_text(yaml.dump({
        "engines": {
            "dual_speed": {"accel": {}},
        }
    }), encoding="utf-8")

    from src.v25.config.loader import load_v25_config
    cfg = load_v25_config(
        risk_yaml_path=str(risk_yaml),
        engines_yaml_path=str(engines_yaml),
    )

    de = cfg.engines.dynamic_exit
    assert de.r_breakeven == 0.5
    assert de.r_profit_capture == 1.5
    assert de.r_trend_rider == 3.0


# ---------------------------------------------------------------------------
# 7. Config validation
# ---------------------------------------------------------------------------


def test_config_validation_rejects_non_increasing_r_thresholds(tmp_path) -> None:
    """R thresholds must be strictly increasing."""
    import yaml
    from src.v25.config.loader import ConfigValidationError

    risk_yaml = tmp_path / "risk.yaml"
    risk_yaml.write_text(yaml.dump({
        "risk": {
            "global_caps": {},
            "growth_sizer": {"phases": {}},
            "fee_model": {
                "maker_fee_pct": 0.0002,
                "taker_fee_pct": 0.0005,
                "spread_estimate_pct": 0.0001,
                "slippage_base_pct": 0.0003,
                "slippage_per_10k": 0.0001,
                "backtest_cost_mult": 1.5,
            },
        }
    }), encoding="utf-8")

    engines_yaml = tmp_path / "engines.yaml"
    engines_yaml.write_text(yaml.dump({
        "engines": {
            "hermes": {
                "dynamic_exit": {
                    "r_breakeven": 2.0,       # > r_profit_capture: invalid!
                    "r_profit_capture": 1.5,
                    "r_trend_rider": 3.0,
                }
            },
            "dual_speed": {"accel": {}},
        }
    }), encoding="utf-8")

    from src.v25.config.loader import load_v25_config
    with pytest.raises(ConfigValidationError) as exc_info:
        load_v25_config(
            risk_yaml_path=str(risk_yaml),
            engines_yaml_path=str(engines_yaml),
        )
    assert "strictly increasing" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 8. HermesPositionManager passes config through
# ---------------------------------------------------------------------------


def test_hermes_position_manager_uses_custom_config() -> None:
    """HermesPositionManager forwards config to FSM functions."""
    from src.execution.hermes_position_manager import HermesPositionManager

    class NoopBroker:
        def close_position(self, **kw): pass
        def modify_stop_loss(self, **kw): pass
        def modify_take_profit(self, **kw): pass

    cfg = DynamicExitConfig(r_breakeven=1.0, r_profit_capture=2.0, r_trend_rider=4.0)
    mgr = HermesPositionManager(
        broker=NoopBroker(),
        shadow_enabled=True,
        dynamic_exit_config=cfg,
    )

    positions = [
        {
            "position_id": "pos-1",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": 100,
            "current_price": 101,  # +0.5R — NOT enough for r_breakeven=1.0
            "sl_pct": 0.02,
            "r_value_pct": 0.02,
            "atr_pct": 0.01,
        }
    ]

    ts = _TS
    intents = mgr.shadow_dynamic_exit_intents(positions=positions, ts=ts)
    # With r_breakeven=1.0, price=101 (+0.5R) should NOT trigger transition -> NOOP -> no intents
    assert len(intents) == 0

    # Now at +1.0R (price=102), should trigger breakeven lock
    positions[0]["current_price"] = 102
    intents = mgr.shadow_dynamic_exit_intents(positions=positions, ts=ts)
    assert len(intents) == 1
    assert intents[0].action_type.value == "UPDATE_STOP"
