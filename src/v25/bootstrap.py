"""Public integration seam for ARGUS v2.5."""

from __future__ import annotations

import sqlite3

from src.v25.config.loader import V25Config, load_v25_config as _load_v25_config
from src.v25.contracts.fee import FeeModel
from src.v25.db.migrations import run_v25_migrations as _run_v25_migrations
from src.v25.risk.accel_gates import evaluate_accel_gates as _evaluate_accel_gates
from src.v25.risk.caps import compute_effective_cap as _compute_effective_cap
from src.v25.risk.stop_resize import recalculate_after_stop_widening as _recalculate_after_stop_widening


def load_v25_config(
    risk_yaml_path: str = "config/risk.yaml",
    engines_yaml_path: str = "config/engines.yaml",
) -> V25Config:
    return _load_v25_config(risk_yaml_path=risk_yaml_path, engines_yaml_path=engines_yaml_path)


def run_v25_migrations(db_path: str) -> sqlite3.Connection:
    return _run_v25_migrations(db_path=db_path)


def build_fee_model(config: V25Config) -> FeeModel:
    fee_cfg = config.risk.fee_model
    return FeeModel(
        maker_fee_pct=fee_cfg.maker_fee_pct,
        taker_fee_pct=fee_cfg.taker_fee_pct,
        spread_estimate_pct=fee_cfg.spread_estimate_pct,
        slippage_base_pct=fee_cfg.slippage_base_pct,
        slippage_per_10k=fee_cfg.slippage_per_10k,
        backtest_cost_mult=fee_cfg.backtest_cost_mult,
    )


def compute_effective_cap(phase_risk: float, global_per_trade_cap: float) -> float:
    return _compute_effective_cap(phase_risk=phase_risk, global_per_trade_cap=global_per_trade_cap)


def evaluate_accel_gates(
    sub_regime: str,
    alignment_score: float,
    sqs_score: float,
    kill_switch_level: int,
    rolling_vol_24h: float,
    current_drawdown_pct: float,
    recent_slippage_err: float | None,
    filled_order_count: int,
    config: V25Config,
) -> tuple[bool, str]:
    return _evaluate_accel_gates(
        sub_regime=sub_regime,
        alignment_score=alignment_score,
        sqs_score=sqs_score,
        kill_switch_level=kill_switch_level,
        rolling_vol_24h=rolling_vol_24h,
        current_drawdown_pct=current_drawdown_pct,
        recent_slippage_err=recent_slippage_err,
        filled_order_count=filled_order_count,
        config=config,
    )


def recalculate_after_stop_widening(
    risk_per_trade: float,
    old_stop: float,
    stop_multiplier_delta: float,
    min_stop: float = 0.01,
    max_stop: float = 0.05,
) -> tuple[float, float]:
    return _recalculate_after_stop_widening(
        risk_per_trade=risk_per_trade,
        old_stop=old_stop,
        stop_multiplier_delta=stop_multiplier_delta,
        min_stop=min_stop,
        max_stop=max_stop,
    )


__all__ = [
    "load_v25_config",
    "run_v25_migrations",
    "build_fee_model",
    "compute_effective_cap",
    "evaluate_accel_gates",
    "recalculate_after_stop_widening",
]

