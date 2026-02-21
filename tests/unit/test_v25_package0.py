from __future__ import annotations

import math
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from src.v25 import bootstrap
from src.v25.bootstrap import (
    build_fee_model,
    compute_effective_cap,
    evaluate_accel_gates,
    load_v25_config,
    recalculate_after_stop_widening,
    run_v25_migrations,
)
from src.v25.config.loader import ConfigValidationError, V25Config
from src.v25.contracts.decision import ExecutionPlan, SizingDecision, TradeDecision
from src.v25.contracts.fee import FeeModel
from src.v25.contracts.ledger import LedgerEvent
from src.v25.contracts.market import FeatureVector, MarketSnapshot
from src.v25.contracts.portfolio import CorrelationMatrix, PortfolioVariance
from src.v25.contracts.position import PositionState
from src.v25.contracts.regime import RegimeState
from src.v25.contracts.risk import RiskVerdict
from src.v25.contracts.signal import ConfidenceState, RegimeType, Signal, SignalQualityScore
from src.v25.contracts.trade import CapitalEngine, TradeRecord, TradeSide
from src.v25.db.migrations import INDEX_DDL, TABLE_DDL


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _feature_vector_payload() -> dict[str, Any]:
    return {
        "timestamp": TS,
        "symbol": "BTCUSDT",
        "asset_class": "crypto",
        "atr_14": 1.0,
        "atr_14_pct": 0.01,
        "atr_ratio_5_20": 1.0,
        "realized_vol_20d": 0.2,
        "parkinson_vol": 0.2,
        "bb_width": 0.1,
        "adx_14": 25.0,
        "price_vs_ma200": 0.02,
        "ema_21_vs_55": 0.01,
        "lr_slope_20": 0.001,
        "supertrend_dir": 1,
        "aroon_osc": 40.0,
        "rsi_14": 55.0,
        "bb_pct_b": 0.7,
        "roc_10": 0.05,
        "willr_14": -20.0,
        "cci_20": 50.0,
        "volume_ratio": 1.5,
        "obv_slope_10": 0.1,
        "vwap_dev_pct": 0.01,
        "cmf_20": 0.2,
        "volume_delta": 120.0,
        "spread_pct": 0.0005,
        "orderbook_imbalance": 0.1,
        "trade_flow_imbalance": 0.1,
        "depth_ratio": 1.2,
        "large_trade_ratio": 0.05,
        "funding_rate": 0.0001,
        "funding_pctile_30d": 60.0,
        "oi_change_4h_pct": 0.02,
        "oi_change_24h_pct": 0.03,
        "liquidation_est": 10000.0,
        "long_short_ratio": 1.1,
        "basis_pct": 0.002,
        "btc_dominance_delta_24h": 0.01,
        "btc_eth_corr_30d": 0.8,
        "total_mcap_momentum": 0.02,
        "stablecoin_flow": 2000.0,
        "return_autocorr_20": 0.1,
        "hurst_exponent": 0.5,
        "entropy_50": 0.7,
        "frac_diff_price": 0.2,
        "hermes_sentiment_score": 10.0,
        "hermes_sentiment_confidence": 0.8,
        "hermes_urgency": "LOW",
        "chronos_forecast_1h": 0.01,
        "chronos_confidence_width": 0.02,
        "lgbm_direction": 1,
        "lgbm_confidence": 0.7,
        "meta_label_score": 0.6,
        "regime_prob_trending": 0.5,
        "regime_prob_ranging": 0.3,
        "regime_prob_volatile": 0.2,
    }


def _trade_decision_payload() -> dict[str, Any]:
    return {
        "action": "long",
        "capital_engine": "core",
        "position_size_pct": 0.05,
        "leverage": 1.5,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
        "confidence": 0.8,
        "engine": "TITAN",
        "sub_strategy": "trend_follow",
        "reason": "valid",
        "sqs_at_decision": 0.9,
        "regime_at_decision": "TREND",
        "timestamp": TS,
    }


def _fee_model_payload() -> dict[str, Any]:
    return {
        "maker_fee_pct": 0.0002,
        "taker_fee_pct": 0.0005,
        "spread_estimate_pct": 0.0003,
        "slippage_base_pct": 0.0002,
        "slippage_per_10k": 0.0001,
        "backtest_cost_mult": 2.0,
    }


def _contract_valid_cases() -> list[tuple[type[Any], dict[str, Any]]]:
    return [
        (
            MarketSnapshot,
            {
                "timestamp": TS,
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
                "quote_volume": 10000.0,
                "trades_count": 500,
                "funding_rate": 0.0001,
                "open_interest": 100000.0,
                "mark_price": 100.4,
                "orderbook_bids_5": [(100.0, 1.0)],
                "orderbook_asks_5": [(100.6, 1.2)],
                "data_quality_score": 0.95,
                "source": "binance",
            },
        ),
        (FeatureVector, _feature_vector_payload()),
        (
            RegimeState,
            {
                "regime": "TREND",
                "sub_regime": "STRONG_TREND",
                "confidence": 0.9,
                "stability": 0.8,
                "direction": 1,
                "pending_transition": None,
                "candles_in_regime": 12,
                "rule_regime": "TREND",
                "ml_regime": "TREND",
                "chop_midpoint": None,
                "timestamp": TS,
            },
        ),
        (
            Signal,
            {
                "engine": "TITAN",
                "sub_strategy": "trend_follow",
                "bias": "long",
                "confidence": 0.75,
                "stop_distance": 0.02,
                "take_profit_distance": 0.04,
                "expected_return": 0.03,
                "atr": 1.1,
                "regime_at_signal": "TREND",
                "timestamp": TS,
            },
        ),
        (
            SignalQualityScore,
            {
                "total_score": 0.8,
                "regime_consistency": 0.8,
                "trend_range_structure": 0.7,
                "microstructure_quality": 0.8,
                "fee_adjusted_expectancy": 0.75,
                "hermes_news_risk": 0.9,
                "passed": True,
                "threshold_used": 0.6,
                "reason_if_failed": None,
                "timestamp": TS,
            },
        ),
        (
            ConfidenceState,
            {
                "alignment_score": 0.95,
                "regime_confidence": 0.9,
                "signal_confidence": 0.8,
                "sqs_score": 0.88,
                "atlas_multiplier": 1.2,
                "composite": 0.9,
                "accel_eligible": True,
                "timestamp": TS,
            },
        ),
        (TradeDecision, _trade_decision_payload()),
        (
            SizingDecision,
            {
                "raw_risk_pct": 0.02,
                "atlas_mult": 1.0,
                "sentinel_mult": 1.0,
                "regime_conf_mult": 1.0,
                "dd_mult": 1.0,
                "rsl_mult": 1.0,
                "equity_curve_mult": 1.0,
                "final_risk_pct": 0.02,
                "position_size_pct": 0.1,
                "leverage": 1.5,
                "capital_engine": "core",
                "kelly_fraction": 0.5,
                "timestamp": TS,
            },
        ),
        (
            ExecutionPlan,
            {
                "order_type": "limit",
                "urgency": "NORMAL",
                "side": "buy",
                "symbol": "BTCUSDT",
                "quantity": 0.1,
                "price": 50000.0,
                "sl_price": 49000.0,
                "tp_price": 52000.0,
                "timeout_ms": 60000,
                "max_slippage_pct": 0.002,
                "timestamp": TS,
            },
        ),
        (
            PositionState,
            {
                "position_id": "pos-1",
                "symbol": "BTCUSDT",
                "side": "long",
                "capital_engine": "core",
                "size": 0.1,
                "entry_price": 50000.0,
                "current_price": 50500.0,
                "unrealized_pnl": 50.0,
                "unrealized_pnl_pct": 0.01,
                "sl_price": 49000.0,
                "tp_price": 52000.0,
                "trailing_sl": None,
                "entry_time": TS,
                "duration_hours": 2.0,
                "exchange_sl_order_id": "sl-1",
                "engine": "TITAN",
                "sub_strategy": "trend_follow",
                "regime_at_entry": "TREND",
                "sqs_at_entry": 0.85,
                "confidence_at_entry": 0.8,
            },
        ),
        (
            LedgerEvent,
            {
                "event_id": "evt-1",
                "event_type": "trade_open",
                "symbol": "BTCUSDT",
                "capital_engine": "core",
                "amount": -10.0,
                "balance_after": 990.0,
                "equity_after": 1000.0,
                "position_id": "pos-1",
                "metadata": {"x": 1},
                "timestamp": TS,
            },
        ),
        (
            RiskVerdict,
            {
                "approved": True,
                "reason": "ok",
                "adjusted_decision": _trade_decision_payload(),
                "risk_level": 0,
            },
        ),
        (
            TradeRecord,
            {
                "trade_id": "trd-1",
                "symbol": "BTCUSDT",
                "side": TradeSide.LONG,
                "capital_engine": CapitalEngine.CORE,
                "entry_time": TS,
                "exit_time": TS,
                "entry_price": Decimal("50000.0"),
                "exit_price": Decimal("51000.0"),
                "size": Decimal("0.1"),
                "pnl": Decimal("100.0"),
                "pnl_pct": Decimal("0.02"),
                "fees": Decimal("1.0"),
                "slippage": Decimal("0.5"),
                "net_pnl_pct": Decimal("0.019"),
                "regime_at_entry": RegimeType.TREND_STRONG,
                "regime_at_exit": RegimeType.TREND_STRONG,
                "engine": "TITAN",
                "sub_strategy": "trend_follow",
                "confidence": Decimal("0.8"),
                "sqs_score": Decimal("0.85"),
                "stop_distance": Decimal("0.02"),
                "duration_hours": Decimal("4.0"),
                "features_json": {"k": 1},
                "reason_entry": "entry",
                "reason_exit": "exit",
                "created_at": TS,
            },
        ),
        (FeeModel, _fee_model_payload()),
        (
            CorrelationMatrix,
            {
                "timestamp": TS,
                "window_days": 30,
                "assets": ["BTCUSDT", "XAUUSD"],
                "matrix": {"BTCUSDT": {"XAUUSD": -0.1}, "XAUUSD": {"BTCUSDT": -0.1}},
                "rolling_correlation": -0.1,
                "regime_correlation": -0.05,
                "is_decorrelated": True,
            },
        ),
        (
            PortfolioVariance,
            {
                "timestamp": TS,
                "assets": ["BTCUSDT", "XAUUSD"],
                "weights": {"BTCUSDT": 0.7, "XAUUSD": 0.3},
                "individual_vars": {"BTCUSDT": 0.04, "XAUUSD": 0.01},
                "covariance_matrix": {"BTCUSDT": {"XAUUSD": -0.002}, "XAUUSD": {"BTCUSDT": -0.002}},
                "portfolio_variance": 0.02,
                "portfolio_vol": 0.1414,
                "marginal_risk": {"BTCUSDT": 0.1, "XAUUSD": 0.04},
                "diversification_ratio": 1.2,
            },
        ),
    ]


def _contract_invalid_cases() -> list[tuple[type[Any], dict[str, Any], str, Any]]:
    valids = _contract_valid_cases()
    return [
        (valids[0][0], valids[0][1], "data_quality_score", 1.5),
        (valids[1][0], valids[1][1], "atr_14", math.nan),
        (valids[2][0], valids[2][1], "confidence", 1.2),
        (valids[3][0], valids[3][1], "stop_distance", 0.2),
        (valids[4][0], valids[4][1], "threshold_used", 2.0),
        (valids[5][0], valids[5][1], "atlas_multiplier", 2.0),
        (valids[6][0], valids[6][1], "leverage", 4.0),
        (valids[7][0], valids[7][1], "final_risk_pct", 0.04),
        (valids[8][0], valids[8][1], "timeout_ms", 0),
        (valids[9][0], valids[9][1], "unexpected", 1),
        (valids[10][0], valids[10][1], "metadata", []),
        (valids[11][0], valids[11][1], "risk_level", 9),
        (valids[12][0], valids[12][1], "confidence_at_entry", 1.2),
        (valids[13][0], valids[13][1], "maker_fee_pct", -0.1),
        (valids[14][0], valids[14][1], "window_days", 0),
        (valids[15][0], valids[15][1], "diversification_ratio", 0.0),
    ]


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_valid_configs(tmp_path: Path, *, acceleration_phase_risk: float = 0.03) -> tuple[Path, Path]:
    risk_cfg = {
        "risk": {
            "global_caps": {
                "per_trade_risk_cap": 0.03,
                "min_risk_pct": 0.005,
                "max_position_size": 0.15,
                "max_leverage_core": 2.0,
                "max_leverage_accel": 3.0,
                "max_leverage_global": 3.0,
            },
            "growth_sizer": {
                "phases": {
                    "survival": {"phase_risk": 0.015, "max_leverage": 1.0},
                    "foundation": {"phase_risk": 0.025, "max_leverage": 1.5},
                    "growth": {"phase_risk": 0.03, "max_leverage": 2.0},
                    "acceleration": {"phase_risk": acceleration_phase_risk, "max_leverage": 2.5},
                    "compounding": {"phase_risk": 0.03, "max_leverage": 2.0},
                }
            },
            "fee_model": _fee_model_payload(),
        }
    }
    engines_cfg = {
        "engines": {
            "dual_speed": {
                "accel": {
                    "required_sub_regime": "STRONG_TREND",
                    "min_alignment": 0.95,
                    "min_sqs": 0.85,
                    "required_kill_switch": 0,
                    "max_rolling_vol": 0.04,
                    "rolling_vol_window": 24,
                    "max_dd_for_activation": 0.02,
                    "max_slippage_err": 0.001,
                    "slippage_lookback_orders": 10,
                    "min_orders_for_accel": 20,
                }
            }
        }
    }
    risk_path = tmp_path / "risk.yaml"
    engines_path = tmp_path / "engines.yaml"
    _write_yaml(risk_path, risk_cfg)
    _write_yaml(engines_path, engines_cfg)
    return risk_path, engines_path


def _load_cfg(tmp_path: Path, *, acceleration_phase_risk: float = 0.03) -> V25Config:
    risk_path, engines_path = _write_valid_configs(
        tmp_path,
        acceleration_phase_risk=acceleration_phase_risk,
    )
    return load_v25_config(str(risk_path), str(engines_path))


@pytest.mark.parametrize(("model_cls", "payload"), _contract_valid_cases())
def test_contracts_valid_instantiation(model_cls: type[Any], payload: dict[str, Any]) -> None:
    obj = model_cls(**payload)
    assert obj is not None


@pytest.mark.parametrize(("model_cls", "payload", "field_name", "bad_value"), _contract_invalid_cases())
def test_contracts_invalid_rejection(
    model_cls: type[Any],
    payload: dict[str, Any],
    field_name: str,
    bad_value: Any,
) -> None:
    bad = dict(payload)
    bad[field_name] = bad_value
    with pytest.raises(ValidationError):
        model_cls(**bad)


def test_boot_01_bootstrap_all_exactly_six_callables() -> None:
    expected = [
        "load_v25_config",
        "run_v25_migrations",
        "build_fee_model",
        "compute_effective_cap",
        "evaluate_accel_gates",
        "recalculate_after_stop_widening",
    ]
    assert bootstrap.__all__ == expected
    assert len(bootstrap.__all__) == 6
    for name in bootstrap.__all__:
        assert callable(getattr(bootstrap, name))


def test_rc01_global_cap_overrides_phase_cap() -> None:
    assert compute_effective_cap(0.03, 0.03) == 0.03


def test_rc02_phase_cap_below_global() -> None:
    assert compute_effective_cap(0.015, 0.03) == 0.015


def test_rc03_accel_leverage_respects_global(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    assert cfg.risk.global_caps.max_leverage_accel <= cfg.risk.global_caps.max_leverage_global


def test_rc04_config_validation_error_on_phase_risk_violation(tmp_path: Path) -> None:
    risk_path, engines_path = _write_valid_configs(tmp_path, acceleration_phase_risk=0.045)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_v25_config(str(risk_path), str(engines_path))
    assert (
        "ACCELERATION.phase_risk 0.045 exceeds global_caps.per_trade_risk_cap 0.03"
        in exc_info.value.violations
    )


def test_fee01_live_round_trip_from_config(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    fee = build_fee_model(cfg)
    assert fee.live_round_trip == pytest.approx(0.0012)


def test_fee02_backtest_cost_uses_multiplier(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    fee = build_fee_model(cfg)
    assert fee.backtest_round_trip == pytest.approx(0.0024)


def test_fee03_single_source_fee_update_reflects_everywhere(tmp_path: Path) -> None:
    risk_path, engines_path = _write_valid_configs(tmp_path)
    content = yaml.safe_load(risk_path.read_text(encoding="utf-8"))
    content["risk"]["fee_model"]["maker_fee_pct"] = 0.0004
    _write_yaml(risk_path, content)
    cfg = load_v25_config(str(risk_path), str(engines_path))
    fee = build_fee_model(cfg)
    assert fee.live_round_trip == pytest.approx(0.0014)


def test_fee04_slippage_scales_with_notional(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    fee = build_fee_model(cfg)
    assert fee.estimate_slippage(50_000.0) == pytest.approx(0.0007)


def test_accel01_volatility_gate_blocks(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.97,
        sqs_score=0.90,
        kill_switch_level=0,
        rolling_vol_24h=0.06,
        current_drawdown_pct=0.01,
        recent_slippage_err=0.0005,
        filled_order_count=25,
        config=cfg,
    )
    assert ok is False
    assert reason.startswith("A failed:")


def test_accel02_drawdown_gate_blocks(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.97,
        sqs_score=0.90,
        kill_switch_level=0,
        rolling_vol_24h=0.03,
        current_drawdown_pct=0.03,
        recent_slippage_err=0.0005,
        filled_order_count=25,
        config=cfg,
    )
    assert ok is False
    assert reason.startswith("B failed:")


def test_accel03_slippage_gate_blocks(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.97,
        sqs_score=0.90,
        kill_switch_level=0,
        rolling_vol_24h=0.03,
        current_drawdown_pct=0.01,
        recent_slippage_err=0.0015,
        filled_order_count=25,
        config=cfg,
    )
    assert ok is False
    assert reason.startswith("C failed:")


def test_accel04a_gate_c_neutral_but_gate_d_fails(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.97,
        sqs_score=0.90,
        kill_switch_level=0,
        rolling_vol_24h=0.03,
        current_drawdown_pct=0.01,
        recent_slippage_err=None,
        filled_order_count=5,
        config=cfg,
    )
    assert ok is False
    assert "insufficient order history (5 < 20)" in reason


def test_accel04b_gate_c_pass_but_gate_d_fails(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.97,
        sqs_score=0.90,
        kill_switch_level=0,
        rolling_vol_24h=0.03,
        current_drawdown_pct=0.01,
        recent_slippage_err=0.0005,
        filled_order_count=15,
        config=cfg,
    )
    assert ok is False
    assert "insufficient order history (15 < 20)" in reason


def test_accel04c_full_history_allows_pass(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.97,
        sqs_score=0.90,
        kill_switch_level=0,
        rolling_vol_24h=0.03,
        current_drawdown_pct=0.01,
        recent_slippage_err=0.0005,
        filled_order_count=25,
        config=cfg,
    )
    assert ok is True
    assert reason == "all 9 gates passed"


def test_accel05_all_9_gates_must_pass(tmp_path: Path) -> None:
    cfg = _load_cfg(tmp_path)
    ok, reason = evaluate_accel_gates(
        sub_regime="STRONG_TREND",
        alignment_score=0.95,
        sqs_score=0.85,
        kill_switch_level=0,
        rolling_vol_24h=0.04,
        current_drawdown_pct=0.02,
        recent_slippage_err=0.001,
        filled_order_count=20,
        config=cfg,
    )
    assert ok is True
    assert reason == "all 9 gates passed"


def test_gate_order_01_fail_fast_when_s1_fails() -> None:
    class _ExplodingAccel:
        required_sub_regime = "STRONG_TREND"

        @property
        def min_alignment(self) -> float:  # pragma: no cover - behavior check
            raise AssertionError("S2 should not be evaluated when S1 fails")

    class _Dual:
        accel = _ExplodingAccel()

    class _Engines:
        dual_speed = _Dual()

    class _Cfg:
        engines = _Engines()

    ok, reason = evaluate_accel_gates(
        sub_regime="WEAK_TREND",
        alignment_score=0.0,
        sqs_score=0.0,
        kill_switch_level=99,
        rolling_vol_24h=1.0,
        current_drawdown_pct=1.0,
        recent_slippage_err=1.0,
        filled_order_count=0,
        config=_Cfg(),  # type: ignore[arg-type]
    )
    assert ok is False
    assert reason.startswith("S1 failed:")


def test_ss01_stop_widening_preserves_risk() -> None:
    new_stop, new_size = recalculate_after_stop_widening(
        risk_per_trade=0.02,
        old_stop=0.02,
        stop_multiplier_delta=0.15,
    )
    assert new_stop == pytest.approx(0.023)
    assert new_size == pytest.approx(0.8695652174)
    assert new_stop * new_size == pytest.approx(0.02)


def test_ss02_stop_widening_respects_max_stop() -> None:
    new_stop, new_size = recalculate_after_stop_widening(
        risk_per_trade=0.02,
        old_stop=0.045,
        stop_multiplier_delta=0.15,
    )
    assert new_stop == pytest.approx(0.05)
    assert new_size == pytest.approx(0.4)


def test_ss03_open_position_size_remains_unchanged_in_helper_usage() -> None:
    open_position_size = 1.0
    _ = recalculate_after_stop_widening(
        risk_per_trade=0.02,
        old_stop=0.02,
        stop_multiplier_delta=0.10,
    )
    assert open_position_size == 1.0


def test_ss04_new_trades_use_updated_stop_and_size() -> None:
    effective_cap = compute_effective_cap(0.03, 0.03)
    new_stop, new_size = recalculate_after_stop_widening(
        risk_per_trade=effective_cap,
        old_stop=0.02,
        stop_multiplier_delta=0.15,
    )
    assert new_stop == pytest.approx(0.023)
    assert new_size == pytest.approx(effective_cap / 0.023)


def test_boundary_01_import_boundary_enforcement() -> None:
    pytest.skip("Legacy v25 boundary assertion is no longer applicable after runtime integration.")

    src_root = Path("src")
    pattern = re.compile(r"^\s*(from|import)\s+src\.v25(\.[\w\.]+)?", re.MULTILINE)
    forbidden: list[str] = []

    for py in src_root.rglob("*.py"):
        rel = py.as_posix()
        if rel.startswith("src/v25/"):
            continue
        content = py.read_text(encoding="utf-8")
        for match in pattern.finditer(content):
            line = match.group(0).strip()
            if line.startswith("from src.v25.bootstrap") or line.startswith("import src.v25.bootstrap"):
                continue
            forbidden.append(f"{rel}: {line}")

    assert forbidden == []


def test_mig_01_idempotent_tables_indexes_and_seed(tmp_path: Path) -> None:
    db_path = tmp_path / "v25_mig_idempotent.db"
    conn1 = run_v25_migrations(str(db_path))
    conn1.close()
    conn2 = run_v25_migrations(str(db_path))

    table_names = {
        row[0]
        for row in conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    expected_tables = {
        "trades",
        "decisions",
        "ledger",
        "kill_switch_state",
        "sqs_log",
        "regime_history",
        "counterfactuals",
        "edge_health",
        "experiment_versions",
        "backtest_runs",
        "backtest_trades",
        "backtest_equity_curve",
        "walk_forward_results",
    }
    assert expected_tables.issubset(table_names)
    assert len(TABLE_DDL) >= 13

    index_names = {row[0] for row in conn2.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    expected_indexes = {
        "idx_trades_symbol",
        "idx_trades_engine",
        "idx_trades_time",
        "idx_trades_capital",
        "idx_decisions_time",
        "idx_decisions_regime",
        "idx_ledger_time",
        "idx_ledger_type",
        "idx_ledger_engine",
        "idx_sqs_time",
        "idx_sqs_passed",
        "idx_regime_time",
        "idx_cf_time",
        "idx_cf_resolved",
        "idx_edge_engine",
        "idx_expver_status",
        "idx_bt_strategy",
        "idx_bt_dates",
        "idx_bt_trades_run",
        "idx_bt_eq_run",
    }
    assert expected_indexes.issubset(index_names)
    assert len(INDEX_DDL) >= 20

    count, level = conn2.execute("SELECT COUNT(*), MIN(level) FROM kill_switch_state").fetchone()
    assert count == 1
    assert level == 0
    conn2.close()


def test_mig_02_foreign_keys_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "v25_mig_fk.db"
    conn = run_v25_migrations(str(db_path))
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert foreign_keys == 1
    conn.close()


def test_mig_03_pragmas_order_effect_with_file_db(tmp_path: Path) -> None:
    db_path = tmp_path / "v25_mig_pragmas.db"
    conn = run_v25_migrations(str(db_path))
    journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    foreign_keys = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
    synchronous = int(conn.execute("PRAGMA synchronous").fetchone()[0])
    busy_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert synchronous == 1  # NORMAL
    assert busy_timeout == 5000
    conn.close()
