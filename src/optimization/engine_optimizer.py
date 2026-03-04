"""Backtest-only walk-forward optimizer for global engine parameters.

This module is intentionally isolated from live/paper execution paths.
It evaluates parameter grids across assets and rolling windows, computes
composite scores, flags overfit candidates, and writes report artifacts.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Protocol

import numpy as np
import pandas as pd

from src.data.replay_loader import ReplayLoader
from src.risk.dynamic_risk_manager import RiskConfig, apply_trailing_stop, compute_risk_decision


ENGINE_PARAMETER_GRID: dict[str, dict[str, list[float]]] = {
    "Titan": {
        "min_adx": [20, 23, 25, 28],
        "min_confidence": [0.55, 0.60, 0.65],
        "atr_mult_trend": [2.0, 2.5, 3.0],
    },
    "Hydra": {
        "rsi_low": [25, 30, 35],
        "rsi_high": [65, 70, 75],
        "bb_threshold": [0.9, 0.95],
    },
    "Nautilus": {
        "bb_width": [1.8, 2.0, 2.2],
        "rsi_mean": [45, 50, 55],
    },
    "Phoenix": {
        "funding_percentile": [85, 90, 95],
    },
    "Hermes": {
        "sentiment_block_threshold": [0.6, 0.7, 0.8],
    },
    "Atlas": {
        "crisis_multiplier": [0.0, 0.2, 0.4],
    },
}

RISK_PARAMETER_GRID: dict[str, list[float]] = {
    "atr_multiplier_long": [1.2, 1.5, 1.8, 2.0],
    "atr_multiplier_short": [1.2, 1.5, 1.8, 2.0],
    "rr_ratio_long": [1.5, 2.0, 2.5, 3.0],
    "rr_ratio_short": [1.5, 2.0, 2.5, 3.0],
    "leverage_cap_long": [3.0, 4.0, 5.0],
    "leverage_cap_short": [2.5, 3.5, 4.5],
    "trailing_activation_long": [0.8, 1.0, 1.2],
    "trailing_activation_short": [0.8, 1.0, 1.2],
    "volatility_threshold": [0.02, 0.03, 0.04],
    "vol_k": [10.0, 15.0, 20.0],
    "drawdown_sensitivity": [0.5, 1.0, 1.5],
    "confidence_floor": [0.55, 0.60, 0.65],
}

RISK_OPTIMIZATION_ENGINE_DEFAULT = "Titan"
RISK_OPTIMIZER_EQUITY_USD = 10_000.0

ASSET_CLASSES: tuple[str, ...] = ("crypto", "equities", "metals", "indices", "unknown")
REGIMES: tuple[str, ...] = ("TRENDING", "RANGING", "CRISIS")
DRAWDOWN_INSTABILITY_THRESHOLD = 0.10
MIN_TRADES_PER_CLASS = 30
MIN_LONG_TRADES_THRESHOLD = 8
MIN_SHORT_TRADES_THRESHOLD = 8
MAX_RISK_PARAMETER_SETS = 4096

# Explicit symbol -> asset_class mapping. Unknown symbols are intentionally not inferred.
SYMBOL_ASSET_CLASS: dict[str, str] = {
    # Crypto (common perpetual/spot tickers)
    "BTCUSDT": "crypto",
    "ETHUSDT": "crypto",
    "SOLUSDT": "crypto",
    "XRPUSDT": "crypto",
    "DOGEUSDT": "crypto",
    "BNBUSDT": "crypto",
    "ADAUSDT": "crypto",
    "AVAXUSDT": "crypto",
    "LINKUSDT": "crypto",
    "TRXUSDT": "crypto",
    "LTCUSDT": "crypto",
    "DOTUSDT": "crypto",
    "BCHUSDT": "crypto",
    "ATOMUSDT": "crypto",
    "NEARUSDT": "crypto",
    # Equities (examples; project may use other tickers)
    "AAPL": "equities",
    "MSFT": "equities",
    "NVDA": "equities",
    "TSLA": "equities",
    "AMZN": "equities",
    "GOOGL": "equities",
    "META": "equities",
    # Metals
    "XAUUSD": "metals",
    "XAGUSD": "metals",
    "GOLD": "metals",
    "SILVER": "metals",
    # Indices
    "SPX": "indices",
    "NDX": "indices",
    "DJI": "indices",
    "NAS100": "indices",
    "US500": "indices",
    "US30": "indices",
}


def asset_class_for_symbol(symbol: str) -> str:
    key = str(symbol).strip().upper().replace("/", "").replace("-", "").replace("_", "")
    return SYMBOL_ASSET_CLASS.get(key, "unknown")


@dataclass(frozen=True)
class WalkForwardSplit:
    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass(frozen=True)
class WindowMetrics:
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    stability: float
    trade_count: int = 0
    long_total_return: float = 0.0
    short_total_return: float = 0.0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_max_drawdown: float = 0.0
    short_max_drawdown: float = 0.0
    long_trade_count: int = 0
    short_trade_count: int = 0
    long_avg_rr: float = 0.0
    short_avg_rr: float = 0.0
    long_max_adverse_excursion: float = 0.0
    short_max_adverse_excursion: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_return": float(self.total_return),
            "sharpe": float(self.sharpe),
            "max_drawdown": float(self.max_drawdown),
            "win_rate": float(self.win_rate),
            "stability": float(self.stability),
            "trade_count": int(self.trade_count),
            "long_total_return": float(self.long_total_return),
            "short_total_return": float(self.short_total_return),
            "long_win_rate": float(self.long_win_rate),
            "short_win_rate": float(self.short_win_rate),
            "long_max_drawdown": float(self.long_max_drawdown),
            "short_max_drawdown": float(self.short_max_drawdown),
            "long_trade_count": int(self.long_trade_count),
            "short_trade_count": int(self.short_trade_count),
            "long_avg_rr": float(self.long_avg_rr),
            "short_avg_rr": float(self.short_avg_rr),
            "long_max_adverse_excursion": float(self.long_max_adverse_excursion),
            "short_max_adverse_excursion": float(self.short_max_adverse_excursion),
        }


@dataclass(frozen=True)
class WindowEvaluation:
    asset: str
    split: WalkForwardSplit
    train: WindowMetrics
    test: WindowMetrics
    test_by_regime: dict[str, WindowMetrics]


@dataclass(frozen=True)
class AssetEvaluation:
    asset: str
    windows: int
    train: WindowMetrics
    test: WindowMetrics
    drawdown_instability: float
    test_by_regime: dict[str, WindowMetrics]

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "windows": int(self.windows),
            "train": self.train.as_dict(),
            "test": self.test.as_dict(),
            "drawdown_instability": float(self.drawdown_instability),
            "test_by_regime": {
                regime: metrics.as_dict() for regime, metrics in sorted(self.test_by_regime.items())
            },
        }


@dataclass
class OptimizationResult:
    engine: str
    parameter_set: dict[str, float]
    per_asset: dict[str, AssetEvaluation]
    class_scores: dict[str, float]
    class_trades: dict[str, int]
    symbol_returns: dict[str, float]
    avg_train_sharpe: float
    avg_test_sharpe: float
    avg_total_return: float
    avg_win_rate: float
    max_drawdown: float
    avg_stability: float
    stability_penalty: float
    long_total_return: float
    short_total_return: float
    long_trade_count: int
    short_trade_count: int
    regime_stability: float
    final_score: float
    overfit_flag: bool
    overfit_reasons: list[str]
    rank: int = 0


@dataclass(frozen=True)
class OptimizationRequest:
    assets: tuple[str, ...]
    optimize_start: date
    optimize_end: date
    walk_window_days: int = 180
    walk_step_days: int = 30
    reports_dir: Path = Path("reports")
    cache_root: str = "data/binance"
    seed: int = 42


@dataclass(frozen=True)
class OptimizationArtifacts:
    summary_path: Path
    results_csv_path: Path
    heatmap_csv_path: Path
    result_count: int
    overfit_count: int
    split_count: int


@dataclass(frozen=True)
class RiskWindowMetrics:
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    volatility: float
    trade_count: int = 0
    long_total_return: float = 0.0
    short_total_return: float = 0.0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_max_drawdown: float = 0.0
    short_max_drawdown: float = 0.0
    long_trade_count: int = 0
    short_trade_count: int = 0
    long_avg_rr: float = 0.0
    short_avg_rr: float = 0.0
    long_max_adverse_excursion: float = 0.0
    short_max_adverse_excursion: float = 0.0
    long_avg_trade: float = 0.0
    short_avg_trade: float = 0.0
    long_profit_factor: float = 0.0
    short_profit_factor: float = 0.0
    long_downside_deviation: float = 0.0
    short_downside_deviation: float = 0.0
    long_tail_loss_p95: float = 0.0
    short_tail_loss_p95: float = 0.0
    sharpe_like_overall: float = 0.0
    sharpe_like_long: float = 0.0
    sharpe_like_short: float = 0.0
    leverage_cap_saturation: float = 0.0
    stability_score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_return": float(self.total_return),
            "sharpe": float(self.sharpe),
            "max_drawdown": float(self.max_drawdown),
            "win_rate": float(self.win_rate),
            "volatility": float(self.volatility),
            "trade_count": int(self.trade_count),
            "long_total_return": float(self.long_total_return),
            "short_total_return": float(self.short_total_return),
            "long_win_rate": float(self.long_win_rate),
            "short_win_rate": float(self.short_win_rate),
            "long_max_drawdown": float(self.long_max_drawdown),
            "short_max_drawdown": float(self.short_max_drawdown),
            "long_trade_count": int(self.long_trade_count),
            "short_trade_count": int(self.short_trade_count),
            "long_avg_rr": float(self.long_avg_rr),
            "short_avg_rr": float(self.short_avg_rr),
            "long_max_adverse_excursion": float(self.long_max_adverse_excursion),
            "short_max_adverse_excursion": float(self.short_max_adverse_excursion),
            "long_avg_trade": float(self.long_avg_trade),
            "short_avg_trade": float(self.short_avg_trade),
            "long_profit_factor": float(self.long_profit_factor),
            "short_profit_factor": float(self.short_profit_factor),
            "long_downside_deviation": float(self.long_downside_deviation),
            "short_downside_deviation": float(self.short_downside_deviation),
            "long_tail_loss_p95": float(self.long_tail_loss_p95),
            "short_tail_loss_p95": float(self.short_tail_loss_p95),
            "sharpe_like_overall": float(self.sharpe_like_overall),
            "sharpe_like_long": float(self.sharpe_like_long),
            "sharpe_like_short": float(self.sharpe_like_short),
            "leverage_cap_saturation": float(self.leverage_cap_saturation),
            "stability_score": float(self.stability_score),
        }


@dataclass(frozen=True)
class RiskWindowEvaluation:
    asset: str
    split: WalkForwardSplit
    train: RiskWindowMetrics
    test: RiskWindowMetrics


@dataclass(frozen=True)
class RiskAssetEvaluation:
    asset: str
    windows: int
    train: RiskWindowMetrics
    test: RiskWindowMetrics

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "windows": int(self.windows),
            "train": self.train.as_dict(),
            "test": self.test.as_dict(),
        }


@dataclass
class RiskOptimizationResult:
    engine: str
    parameter_set: dict[str, float]
    per_asset: dict[str, RiskAssetEvaluation]
    avg_train_return: float
    avg_test_return: float
    avg_test_sharpe: float
    avg_win_rate: float
    max_drawdown: float
    avg_volatility: float
    long_total_return: float
    short_total_return: float
    long_trade_count: int
    short_trade_count: int
    avg_stability_score: float
    avg_leverage_cap_saturation: float
    avg_long_tail_loss_p95: float
    avg_short_tail_loss_p95: float
    score: float
    overfit_flag: bool
    overfit_reasons: list[str]
    rank: int = 0


@dataclass(frozen=True)
class RiskOptimizationArtifacts:
    summary_path: Path
    results_csv_path: Path
    result_count: int = 0
    overfit_count: int = 0
    split_count: int = 0
    best_parameter_set: dict[str, float] | None = None
    heatmap_csv_path: Path | None = None
    best_config_path: Path | None = None


class RiskOptimizationEvaluator(Protocol):
    def evaluate_window_risk(
        self,
        *,
        engine: str,
        engine_parameter_set: Mapping[str, float],
        risk_parameter_set: Mapping[str, float],
        asset: str,
        split: WalkForwardSplit,
    ) -> RiskWindowEvaluation | None:
        """Evaluate one asset/window pair under the provided risk parameters."""


class OptimizationEvaluator(Protocol):
    def evaluate_window(
        self,
        *,
        engine: str,
        parameter_set: Mapping[str, float],
        asset: str,
        split: WalkForwardSplit,
    ) -> WindowEvaluation | None:
        """Evaluate one asset/window pair and return train + test metrics."""


def generate_walk_forward_splits(
    *,
    optimize_start: date,
    optimize_end: date,
    walk_window_days: int,
    walk_step_days: int,
) -> list[WalkForwardSplit]:
    if walk_window_days <= 0 or walk_step_days <= 0:
        raise ValueError("walk_window_days and walk_step_days must be positive")
    if optimize_end <= optimize_start:
        raise ValueError("optimize_end must be after optimize_start")

    splits: list[WalkForwardSplit] = []
    cursor = optimize_start
    while True:
        train_start = cursor
        train_end = train_start + timedelta(days=walk_window_days)
        test_start = train_end
        test_end = test_start + timedelta(days=walk_step_days)
        if test_end > optimize_end:
            break
        splits.append(
            WalkForwardSplit(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        cursor = cursor + timedelta(days=walk_step_days)
    return splits


def parameter_sets_for_engine(engine: str) -> list[dict[str, float]]:
    grid = ENGINE_PARAMETER_GRID.get(engine)
    if not grid:
        raise ValueError(f"unknown engine: {engine}")

    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    sets: list[dict[str, float]] = []
    for combo in product(*values):
        sets.append({k: float(v) for k, v in zip(keys, combo)})
    return sets


def baseline_parameter_set_for_engine(engine: str) -> dict[str, float]:
    """Deterministic baseline alpha parameters (used by risk optimizer).

    We intentionally keep signal logic fixed during risk optimization.
    """

    grid = ENGINE_PARAMETER_GRID.get(engine)
    if not grid:
        raise ValueError(f"unknown engine: {engine}")
    baseline: dict[str, float] = {}
    for key, values in grid.items():
        if not values:
            continue
        idx = int(len(values) // 2)
        baseline[str(key)] = float(values[idx])
    return baseline


def risk_parameter_sets(max_sets: int = MAX_RISK_PARAMETER_SETS) -> list[dict[str, float]]:
    keys = list(RISK_PARAMETER_GRID.keys())
    values = [RISK_PARAMETER_GRID[k] for k in keys]
    total = 1
    for seq in values:
        total *= max(1, len(seq))
    sets: list[dict[str, float]] = []
    if total <= int(max_sets):
        for combo in product(*values):
            sets.append({k: float(v) for k, v in zip(keys, combo)})
        return sets

    stride = int(math.ceil(float(total) / float(max_sets)))
    for idx, combo in enumerate(product(*values)):
        if idx % stride != 0:
            continue
        sets.append({k: float(v) for k, v in zip(keys, combo)})
        if len(sets) >= int(max_sets):
            break
    return sets


def compute_risk_composite_score(
    *,
    sharpe: float,
    total_return: float,
    max_drawdown: float,
    win_rate: float,
    volatility_of_returns: float,
) -> float:
    return (
        0.35 * float(sharpe)
        + 0.25 * float(total_return)
        - 0.20 * abs(float(max_drawdown))
        + 0.10 * float(win_rate)
        - 0.10 * float(volatility_of_returns)
    )


def detect_overfit_risk(
    *,
    avg_train_return: float,
    avg_test_return: float,
    avg_test_sharpe: float,
    max_drawdown: float,
    long_trade_count: int = 0,
    short_trade_count: int = 0,
    short_return_bear: float | None = None,
    leverage_cap_saturation: float | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if avg_test_return != 0.0 and float(avg_train_return) > (2.0 * float(avg_test_return)):
        reasons.append("train_return_gt_2x_test_return")
    if float(avg_test_sharpe) < 0.0:
        reasons.append("test_sharpe_negative")
    if abs(float(max_drawdown)) > 0.35:
        reasons.append("max_drawdown_gt_35pct")
    if float(avg_test_return) < 0.0:
        reasons.append("total_return_all_negative")
    if int(long_trade_count) < MIN_LONG_TRADES_THRESHOLD:
        reasons.append("long_trade_count_below_threshold")
    if int(short_trade_count) < MIN_SHORT_TRADES_THRESHOLD:
        reasons.append("short_trade_count_below_threshold")
    if short_return_bear is not None and float(short_return_bear) <= 0.0:
        reasons.append("short_bear_edge_below_threshold")
    if leverage_cap_saturation is not None and float(leverage_cap_saturation) > 0.70:
        reasons.append("leverage_cap_saturation_excess")
    return bool(reasons), reasons


def compute_composite_score(
    *,
    avg_sharpe: float,
    avg_total_return: float,
    max_drawdown: float,
    stability_penalty: float,
    cross_asset_consistency: float,
    ) -> float:
    return (
        0.35 * float(avg_sharpe)
        + 0.25 * float(avg_total_return)
        - 0.20 * abs(float(max_drawdown))
        + 0.10 * float(stability_penalty)
        + 0.10 * float(cross_asset_consistency)
    )


def compute_side_aware_composite_score(
    *,
    avg_total_return: float,
    long_total_return: float,
    short_total_return: float,
    regime_stability: float,
    max_drawdown_penalty: float,
    overfit_penalty: float,
) -> float:
    return (
        0.25 * float(avg_total_return)
        + 0.20 * float(long_total_return)
        + 0.20 * float(short_total_return)
        + 0.15 * float(regime_stability)
        + 0.10 * float(max_drawdown_penalty)
        + 0.10 * float(overfit_penalty)
    )


def _score_window(metrics: WindowMetrics) -> float:
    """Score a single symbol/window using the base components (no cross-asset term).

    The final optimizer ranking uses class-balanced aggregation; this function is
    used to build per-symbol per-segment scores for that aggregation.
    """

    stability_penalty = _clamp(1.0 - (float(metrics.stability) * 100.0), -1.0, 1.0)
    return (
        0.35 * float(metrics.sharpe)
        + 0.25 * float(metrics.total_return)
        - 0.20 * abs(float(metrics.max_drawdown))
        + 0.10 * float(stability_penalty)
    )


@dataclass(frozen=True)
class BalancedScoreBreakdown:
    class_scores: dict[str, float]
    class_trades: dict[str, int]
    symbol_returns: dict[str, float]
    class_consistency_bonus: float
    symbol_consistency_bonus: float
    final_score: float


def aggregate_balanced_class_scores(
    *,
    symbol_segment_scores: Mapping[str, list[float]],
    symbol_segment_returns: Mapping[str, list[float]],
    symbol_segment_trades: Mapping[str, list[int]],
    symbol_to_asset_class: Mapping[str, str],
) -> BalancedScoreBreakdown:
    per_symbol_score: dict[str, float] = {}
    per_symbol_return: dict[str, float] = {}
    per_symbol_trades: dict[str, int] = {}

    for symbol, scores in symbol_segment_scores.items():
        if not scores:
            continue
        sym = str(symbol).upper()
        per_symbol_score[sym] = _mean([float(x) for x in scores])
        returns = symbol_segment_returns.get(sym, symbol_segment_returns.get(symbol, []))
        trades = symbol_segment_trades.get(sym, symbol_segment_trades.get(symbol, []))
        per_symbol_return[sym] = _mean([float(x) for x in returns])
        per_symbol_trades[sym] = int(sum(int(x) for x in trades))

    if not per_symbol_score:
        return BalancedScoreBreakdown(
            class_scores={},
            class_trades={},
            symbol_returns={},
            class_consistency_bonus=0.0,
            symbol_consistency_bonus=0.0,
            final_score=0.0,
        )

    class_symbols: dict[str, list[str]] = {}
    for sym in per_symbol_score.keys():
        cls = str(symbol_to_asset_class.get(sym, "unknown"))
        class_symbols.setdefault(cls, []).append(sym)

    class_scores: dict[str, float] = {}
    class_trades: dict[str, int] = {}
    for cls, syms in sorted(class_symbols.items()):
        class_scores[cls] = _mean([per_symbol_score[s] for s in syms])
        class_trades[cls] = int(sum(per_symbol_trades.get(s, 0) for s in syms))

    present_class_scores = [float(v) for v in class_scores.values()]
    present_symbol_returns = [float(v) for v in per_symbol_return.values()]

    base = _mean(present_class_scores)
    class_bonus = 0.05 * (1.0 - _pstdev(present_class_scores))
    symbol_bonus = 0.05 * (1.0 - _pstdev(present_symbol_returns))
    final = float(base + class_bonus + symbol_bonus)

    return BalancedScoreBreakdown(
        class_scores={k: float(v) for k, v in class_scores.items()},
        class_trades={k: int(v) for k, v in class_trades.items()},
        symbol_returns={k: float(v) for k, v in sorted(per_symbol_return.items())},
        class_consistency_bonus=float(class_bonus),
        symbol_consistency_bonus=float(symbol_bonus),
        final_score=float(final),
    )


def detect_overfit(
    *,
    avg_train_sharpe: float,
    avg_test_sharpe: float,
    assets: Mapping[str, AssetEvaluation],
    avg_total_return: float = 0.0,
    max_drawdown: float = 0.0,
    long_trade_count: int = 0,
    short_trade_count: int = 0,
    regime_returns: Mapping[str, float] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if avg_test_sharpe <= 0.0:
        if avg_train_sharpe > 0.0:
            reasons.append("train_sharpe_gt_2x_test_sharpe")
    elif avg_train_sharpe > (2.0 * avg_test_sharpe):
        reasons.append("train_sharpe_gt_2x_test_sharpe")

    strong_assets = sum(
        1
        for row in assets.values()
        if row.test.total_return > 0.0 and row.test.sharpe > 0.0
    )
    if len(assets) > 1 and strong_assets <= 1:
        reasons.append("performance_concentrated_single_asset")

    dd_instability = statistics.pstdev(
        [float(v.drawdown_instability) for v in assets.values()]
    ) if len(assets) > 1 else 0.0
    if dd_instability > DRAWDOWN_INSTABILITY_THRESHOLD:
        reasons.append("drawdown_instability_excess")

    avg_test_win_rate = _mean([v.test.win_rate for v in assets.values()])
    if avg_test_win_rate < 0.45:
        reasons.append("test_win_rate_below_45pct")
    if float(avg_total_return) < 0.0:
        reasons.append("total_return_all_negative")
    if float(max_drawdown) < -0.35:
        reasons.append("max_drawdown_gt_35pct")

    if int(long_trade_count) < MIN_LONG_TRADES_THRESHOLD:
        reasons.append("long_trade_count_below_threshold")
    if int(short_trade_count) < MIN_SHORT_TRADES_THRESHOLD:
        reasons.append("short_trade_count_below_threshold")

    by_regime = {str(k).upper(): float(v) for k, v in (regime_returns or {}).items()}
    if by_regime:
        if by_regime.get("TRENDING", 0.0) <= 0.0:
            reasons.append("bull_regime_not_profitable")
        if by_regime.get("CRISIS", 0.0) <= 0.0:
            reasons.append("bear_regime_not_profitable")
        if by_regime.get("RANGING", 0.0) <= 0.0:
            reasons.append("chop_regime_not_profitable")

    return bool(reasons), reasons


class ReplayHeuristicEvaluator:
    """Deterministic replay-based evaluator used by optimizer.

    This evaluator does not alter runtime pipeline behavior and stays fully
    backtest/offline. It computes regime-aware strategy returns from OHLCV.
    """

    def __init__(self, *, cache_root: str = "data/binance", interval: str = "1h") -> None:
        self._loader = ReplayLoader(root=cache_root)
        self._interval = interval

    def evaluate_window(
        self,
        *,
        engine: str,
        parameter_set: Mapping[str, float],
        asset: str,
        split: WalkForwardSplit,
    ) -> WindowEvaluation | None:
        train_df = self._load_window(asset=asset, start=split.train_start, end=split.train_end)
        test_df = self._load_window(asset=asset, start=split.test_start, end=split.test_end)
        if train_df is None or test_df is None:
            return None

        train_metrics, _ = self._evaluate_frame(
            engine=engine,
            parameter_set=parameter_set,
            frame=train_df,
        )
        test_metrics, test_by_regime = self._evaluate_frame(
            engine=engine,
            parameter_set=parameter_set,
            frame=test_df,
        )

        return WindowEvaluation(
            asset=str(asset).upper(),
            split=split,
            train=train_metrics,
            test=test_metrics,
            test_by_regime=test_by_regime,
        )

    def _load_window(self, *, asset: str, start: date, end: date) -> pd.DataFrame | None:
        # End boundary is exclusive in split generation; keep deterministic cut.
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.min, tzinfo=timezone.utc) - timedelta(seconds=1)
        intervals = [self._interval, "1m"] if self._interval != "1m" else [self._interval]
        for interval in intervals:
            try:
                df = self._loader.load_ohlcv(
                    symbol=str(asset).upper(),
                    interval=interval,
                    start=start_dt,
                    end=end_dt,
                    verify=False,
                )
            except Exception:
                continue
            if not df.empty and len(df) >= 64:
                return df
        return None

    def _evaluate_frame(
        self,
        *,
        engine: str,
        parameter_set: Mapping[str, float],
        frame: pd.DataFrame,
    ) -> tuple[WindowMetrics, dict[str, WindowMetrics]]:
        feat = self._build_features(frame)
        positions = self._positions_for_engine(engine=engine, parameter_set=parameter_set, frame=feat)
        shifted = positions.shift(1).fillna(0.0)
        strategy_returns = shifted * feat["ret1"]
        full_metrics = _compute_metrics(strategy_returns, shifted)

        by_regime: dict[str, WindowMetrics] = {}
        for regime in REGIMES:
            mask = feat["regime"] == regime
            by_regime[regime] = _compute_metrics(strategy_returns[mask], shifted[mask])
        return full_metrics, by_regime

    @staticmethod
    def _build_features(df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        if "high" in frame.columns:
            frame["high"] = pd.to_numeric(frame["high"], errors="coerce")
        else:
            frame["high"] = frame["close"]
        if "low" in frame.columns:
            frame["low"] = pd.to_numeric(frame["low"], errors="coerce")
        else:
            frame["low"] = frame["close"]
        frame = frame.dropna(subset=["close"]).reset_index(drop=True)
        frame["ret1"] = frame["close"].pct_change().fillna(0.0)
        frame["mom5"] = frame["close"].pct_change(5).fillna(0.0)
        frame["vol20"] = frame["ret1"].rolling(20, min_periods=20).std().fillna(0.0)
        mean20 = frame["close"].rolling(20, min_periods=20).mean()
        std20 = frame["close"].rolling(20, min_periods=20).std().replace(0.0, np.nan)
        frame["zscore"] = ((frame["close"] - mean20) / std20).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        frame["pseudo_rsi"] = np.clip(50.0 + frame["zscore"] * 10.0, 0.0, 100.0)
        prev_close = frame["close"].shift(1).fillna(frame["close"])
        tr_components = pd.concat(
            [
                (frame["high"] - frame["low"]).abs(),
                (frame["high"] - prev_close).abs(),
                (frame["low"] - prev_close).abs(),
            ],
            axis=1,
        )
        true_range = tr_components.max(axis=1).fillna(0.0)
        atr = true_range.rolling(14, min_periods=14).mean().fillna(0.0)
        frame["atr_pct"] = (atr / frame["close"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        frame["adx_proxy"] = np.clip(frame["mom5"].abs() * 5000.0, 0.0, 100.0)

        vol_threshold = float(frame["vol20"].quantile(0.85)) if len(frame) > 0 else 0.0
        trend_threshold = float(frame["mom5"].abs().quantile(0.65)) if len(frame) > 0 else 0.0
        frame["regime"] = np.where(
            frame["vol20"] >= vol_threshold,
            "CRISIS",
            np.where(frame["mom5"].abs() >= trend_threshold, "TRENDING", "RANGING"),
        )
        return frame

    @staticmethod
    def _positions_for_engine(
        *,
        engine: str,
        parameter_set: Mapping[str, float],
        frame: pd.DataFrame,
    ) -> pd.Series:
        e = str(engine).strip().lower()
        if e == "titan":
            return ReplayHeuristicEvaluator._titan_positions(frame, parameter_set)
        if e == "hydra":
            return ReplayHeuristicEvaluator._hydra_positions(frame, parameter_set)
        if e == "nautilus":
            return ReplayHeuristicEvaluator._nautilus_positions(frame, parameter_set)
        if e == "phoenix":
            return ReplayHeuristicEvaluator._phoenix_positions(frame, parameter_set)
        if e == "hermes":
            return ReplayHeuristicEvaluator._hermes_positions(frame, parameter_set)
        if e == "atlas":
            return ReplayHeuristicEvaluator._atlas_positions(frame, parameter_set)
        return pd.Series(0.0, index=frame.index, dtype=float)

    @staticmethod
    def _titan_positions(frame: pd.DataFrame, params: Mapping[str, float]) -> pd.Series:
        min_adx = float(params.get("min_adx", 25.0))
        min_conf = float(params.get("min_confidence", 0.55))
        atr_mult = max(float(params.get("atr_mult_trend", 2.5)), 0.1)
        adx_proxy = np.clip(frame["mom5"].abs() * 5000.0, 0.0, 100.0)
        conf = np.clip(0.45 + adx_proxy / 100.0, 0.0, 1.0)
        cond = (frame["regime"] == "TRENDING") & (adx_proxy >= min_adx) & (conf >= min_conf)
        return pd.Series(np.where(cond, np.sign(frame["mom5"]) / atr_mult, 0.0), index=frame.index, dtype=float)

    @staticmethod
    def _hydra_positions(frame: pd.DataFrame, params: Mapping[str, float]) -> pd.Series:
        rsi_low = float(params.get("rsi_low", 30.0))
        rsi_high = float(params.get("rsi_high", 70.0))
        bb_threshold = float(params.get("bb_threshold", 0.90))
        z_edge = max(0.5, bb_threshold * 2.0)
        long_cond = (frame["regime"] == "RANGING") & (frame["pseudo_rsi"] <= rsi_low) & (frame["zscore"] <= -z_edge)
        short_cond = (frame["regime"] == "RANGING") & (frame["pseudo_rsi"] >= rsi_high) & (frame["zscore"] >= z_edge)
        return pd.Series(np.where(long_cond, 1.0, np.where(short_cond, -1.0, 0.0)), index=frame.index, dtype=float)

    @staticmethod
    def _nautilus_positions(frame: pd.DataFrame, params: Mapping[str, float]) -> pd.Series:
        bb_width = float(params.get("bb_width", 2.0))
        rsi_mean = float(params.get("rsi_mean", 50.0))
        z_edge = max(0.5, bb_width - 0.8)
        rsi_band = 20.0
        long_cond = (
            (frame["regime"] == "RANGING")
            & (frame["zscore"] <= -z_edge)
            & (frame["pseudo_rsi"] <= (rsi_mean - rsi_band))
        )
        short_cond = (
            (frame["regime"] == "RANGING")
            & (frame["zscore"] >= z_edge)
            & (frame["pseudo_rsi"] >= (rsi_mean + rsi_band))
        )
        return pd.Series(np.where(long_cond, 1.0, np.where(short_cond, -1.0, 0.0)), index=frame.index, dtype=float)

    @staticmethod
    def _phoenix_positions(frame: pd.DataFrame, params: Mapping[str, float]) -> pd.Series:
        funding_pct = float(params.get("funding_percentile", 95.0))
        high_q = min(max(funding_pct / 100.0, 0.50), 0.999)
        low_q = min(max((100.0 - funding_pct) / 100.0, 0.001), 0.50)
        ret = frame["ret1"]
        r_hi = ret.rolling(48, min_periods=48).quantile(high_q).fillna(np.inf)
        r_lo = ret.rolling(48, min_periods=48).quantile(low_q).fillna(-np.inf)
        long_cond = (frame["regime"] != "CRISIS") & (ret <= r_lo)
        short_cond = (frame["regime"] != "CRISIS") & (ret >= r_hi)
        return pd.Series(np.where(long_cond, 1.0, np.where(short_cond, -1.0, 0.0)), index=frame.index, dtype=float)

    @staticmethod
    def _hermes_positions(frame: pd.DataFrame, params: Mapping[str, float]) -> pd.Series:
        block_threshold = float(params.get("sentiment_block_threshold", 0.7))
        block_floor = -100.0 * block_threshold
        sentiment_proxy = (-frame["ret1"]).rolling(6, min_periods=1).mean() * 100.0
        base_pos = np.sign(frame["mom5"])
        blocked = sentiment_proxy <= block_floor
        return pd.Series(np.where(blocked, 0.0, base_pos), index=frame.index, dtype=float)

    @staticmethod
    def _atlas_positions(frame: pd.DataFrame, params: Mapping[str, float]) -> pd.Series:
        crisis_multiplier = max(float(params.get("crisis_multiplier", 0.0)), 0.0)
        base_pos = np.sign(frame["mom5"])
        pos = np.where(frame["regime"] == "CRISIS", base_pos * crisis_multiplier, base_pos)
        return pd.Series(pos, index=frame.index, dtype=float)


class ReplayRiskEvaluator:
    """Deterministic replay evaluator with TP/SL and adaptive leverage rules.

    Used exclusively by the walk-forward risk optimizer.
    """

    def __init__(
        self,
        *,
        cache_root: str = "data/binance",
        interval: str = "1h",
        risk_mode: str = "normal",
        starting_equity: float = RISK_OPTIMIZER_EQUITY_USD,
        engine_confidence: float = 0.75,
    ) -> None:
        self._loader = ReplayLoader(root=cache_root)
        self._interval = interval
        self._risk_mode = str(risk_mode).lower()
        self._starting_equity = float(starting_equity)
        self._engine_confidence = float(engine_confidence)

    def evaluate_window_risk(
        self,
        *,
        engine: str,
        engine_parameter_set: Mapping[str, float],
        risk_parameter_set: Mapping[str, float],
        asset: str,
        split: WalkForwardSplit,
    ) -> RiskWindowEvaluation | None:
        train_df = self._load_window(asset=asset, start=split.train_start, end=split.train_end)
        test_df = self._load_window(asset=asset, start=split.test_start, end=split.test_end)
        if train_df is None or test_df is None:
            return None

        train = self._evaluate_frame_risk(
            engine=engine,
            engine_parameter_set=engine_parameter_set,
            risk_parameter_set=risk_parameter_set,
            asset=asset,
            frame=train_df,
        )
        test = self._evaluate_frame_risk(
            engine=engine,
            engine_parameter_set=engine_parameter_set,
            risk_parameter_set=risk_parameter_set,
            asset=asset,
            frame=test_df,
        )
        return RiskWindowEvaluation(
            asset=str(asset).upper(),
            split=split,
            train=train,
            test=test,
        )

    def _load_window(self, *, asset: str, start: date, end: date) -> pd.DataFrame | None:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.min, tzinfo=timezone.utc) - timedelta(seconds=1)
        intervals = [self._interval, "1m"] if self._interval != "1m" else [self._interval]
        for interval in intervals:
            try:
                df = self._loader.load_ohlcv(
                    symbol=str(asset).upper(),
                    interval=interval,
                    start=start_dt,
                    end=end_dt,
                    verify=False,
                )
            except Exception:
                continue
            if not df.empty and len(df) >= 64:
                return df
        return None

    def _evaluate_frame_risk(
        self,
        *,
        engine: str,
        engine_parameter_set: Mapping[str, float],
        risk_parameter_set: Mapping[str, float],
        asset: str,
        frame: pd.DataFrame,
    ) -> RiskWindowMetrics:
        feat = ReplayHeuristicEvaluator._build_features(frame)
        positions = ReplayHeuristicEvaluator._positions_for_engine(
            engine=engine,
            parameter_set=engine_parameter_set,
            frame=feat,
        )
        return _simulate_risk_frame(
            feat=feat,
            positions=positions,
            symbol=str(asset).upper(),
            engine=str(engine),
            engine_confidence=self._engine_confidence,
            starting_equity=self._starting_equity,
            risk_mode=self._risk_mode,
            risk_parameter_set=risk_parameter_set,
        )


def run_engine_optimization(
    request: OptimizationRequest,
    *,
    evaluator: OptimizationEvaluator | None = None,
) -> OptimizationArtifacts:
    if not request.assets:
        raise ValueError("at least one asset is required")
    np.random.seed(int(request.seed))

    splits = generate_walk_forward_splits(
        optimize_start=request.optimize_start,
        optimize_end=request.optimize_end,
        walk_window_days=int(request.walk_window_days),
        walk_step_days=int(request.walk_step_days),
    )
    if not splits:
        raise ValueError("no walk-forward splits generated for provided date range and windows")

    eval_backend = evaluator or ReplayHeuristicEvaluator(cache_root=request.cache_root)
    results: list[OptimizationResult] = []

    for engine in sorted(ENGINE_PARAMETER_GRID.keys()):
        for parameter_set in parameter_sets_for_engine(engine):
            asset_results: dict[str, AssetEvaluation] = {}
            symbol_segment_scores: dict[str, list[float]] = {}
            symbol_segment_returns: dict[str, list[float]] = {}
            symbol_segment_trades: dict[str, list[int]] = {}
            for asset in request.assets:
                window_rows: list[WindowEvaluation] = []
                for split in splits:
                    out = eval_backend.evaluate_window(
                        engine=engine,
                        parameter_set=parameter_set,
                        asset=asset,
                        split=split,
                    )
                    if out is not None:
                        window_rows.append(out)
                if not window_rows:
                    continue
                for row in window_rows:
                    sym = str(row.asset).upper()
                    symbol_segment_scores.setdefault(sym, []).append(_score_window(row.test))
                    symbol_segment_returns.setdefault(sym, []).append(float(row.test.total_return))
                    symbol_segment_trades.setdefault(sym, []).append(int(row.test.trade_count))
                asset_eval = _aggregate_asset_windows(asset=asset, rows=window_rows)
                asset_results[str(asset).upper()] = asset_eval

            if not asset_results:
                continue

            avg_train_sharpe = _mean([row.train.sharpe for row in asset_results.values()])
            avg_test_sharpe = _mean([row.test.sharpe for row in asset_results.values()])
            avg_total_return = _mean([row.test.total_return for row in asset_results.values()])
            avg_win_rate = _mean([row.test.win_rate for row in asset_results.values()])
            max_drawdown = min([row.test.max_drawdown for row in asset_results.values()])
            avg_stability = _mean([row.test.stability for row in asset_results.values()])
            stability_penalty = _clamp(1.0 - (avg_stability * 100.0), -1.0, 1.0)
            long_total_return = _mean([row.test.long_total_return for row in asset_results.values()])
            short_total_return = _mean([row.test.short_total_return for row in asset_results.values()])
            long_trade_count = int(sum(int(row.test.long_trade_count) for row in asset_results.values()))
            short_trade_count = int(sum(int(row.test.short_trade_count) for row in asset_results.values()))
            regime_returns = {
                regime: _mean(
                    [
                        float(asset_eval.test_by_regime.get(regime, _zero_metrics()).total_return)
                        for asset_eval in asset_results.values()
                    ]
                )
                for regime in REGIMES
            }
            regime_stability = _clamp(1.0 - _pstdev([float(v) for v in regime_returns.values()]), -1.0, 1.0)
            max_drawdown_penalty = _clamp(1.0 - abs(float(max_drawdown)), -1.0, 1.0)
            symbol_to_class = {sym: asset_class_for_symbol(sym) for sym in asset_results.keys()}
            balanced = aggregate_balanced_class_scores(
                symbol_segment_scores=symbol_segment_scores,
                symbol_segment_returns=symbol_segment_returns,
                symbol_segment_trades=symbol_segment_trades,
                symbol_to_asset_class=symbol_to_class,
            )
            overfit_flag, overfit_reasons = detect_overfit(
                avg_train_sharpe=avg_train_sharpe,
                avg_test_sharpe=avg_test_sharpe,
                assets=asset_results,
                avg_total_return=avg_total_return,
                max_drawdown=max_drawdown,
                long_trade_count=long_trade_count,
                short_trade_count=short_trade_count,
                regime_returns=regime_returns,
            )
            overfit_penalty = -1.0 if overfit_flag else 1.0
            final_score = compute_side_aware_composite_score(
                avg_total_return=avg_total_return,
                long_total_return=long_total_return,
                short_total_return=short_total_return,
                regime_stability=regime_stability,
                max_drawdown_penalty=max_drawdown_penalty,
                overfit_penalty=overfit_penalty,
            )
            # Keep class-balanced consistency as a light tiebreaker only.
            final_score += 0.05 * float(balanced.class_consistency_bonus + balanced.symbol_consistency_bonus)

            results.append(
                OptimizationResult(
                    engine=engine,
                    parameter_set=parameter_set,
                    per_asset=asset_results,
                    class_scores=balanced.class_scores,
                    class_trades=balanced.class_trades,
                    symbol_returns=balanced.symbol_returns,
                    avg_train_sharpe=float(avg_train_sharpe),
                    avg_test_sharpe=float(avg_test_sharpe),
                    avg_total_return=float(avg_total_return),
                    avg_win_rate=float(avg_win_rate),
                    max_drawdown=float(max_drawdown),
                    avg_stability=float(avg_stability),
                    stability_penalty=float(stability_penalty),
                    long_total_return=float(long_total_return),
                    short_total_return=float(short_total_return),
                    long_trade_count=int(long_trade_count),
                    short_trade_count=int(short_trade_count),
                    regime_stability=float(regime_stability),
                    final_score=float(final_score),
                    overfit_flag=bool(overfit_flag),
                    overfit_reasons=list(overfit_reasons),
                )
            )

    ranked = sorted(
        results,
        key=lambda r: (
            r.overfit_flag,
            -r.final_score,
            r.engine,
            json.dumps(r.parameter_set, sort_keys=True),
        ),
    )
    for idx, row in enumerate(ranked, start=1):
        row.rank = idx

    reports_dir = Path(request.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = reports_dir / "ENGINE_OPTIMIZATION_SUMMARY.md"
    results_path = reports_dir / "ENGINE_OPTIMIZATION_RESULTS.csv"
    heatmap_path = reports_dir / "ENGINE_OPTIMIZATION_HEATMAP.csv"

    _write_results_csv(results_path, ranked)
    _write_heatmap_csv(heatmap_path, ranked)
    _write_summary_md(summary_path, ranked, request=request, split_count=len(splits))

    return OptimizationArtifacts(
        summary_path=summary_path,
        results_csv_path=results_path,
        heatmap_csv_path=heatmap_path,
        result_count=len(ranked),
        overfit_count=sum(1 for row in ranked if row.overfit_flag),
        split_count=len(splits),
    )


def run_risk_optimization(
    request: OptimizationRequest,
    *,
    engine: str = RISK_OPTIMIZATION_ENGINE_DEFAULT,
    engine_parameter_set: Mapping[str, float] | None = None,
    evaluator: RiskOptimizationEvaluator | None = None,
    risk_mode: str = "normal",
) -> RiskOptimizationArtifacts:
    """Walk-forward optimizer for risk parameters only (alpha params fixed)."""

    if not request.assets:
        raise ValueError("at least one asset is required")
    np.random.seed(int(request.seed))

    splits = generate_walk_forward_splits(
        optimize_start=request.optimize_start,
        optimize_end=request.optimize_end,
        walk_window_days=int(request.walk_window_days),
        walk_step_days=int(request.walk_step_days),
    )
    if not splits:
        raise ValueError("no walk-forward splits generated for provided date range and windows")

    alpha_params = dict(engine_parameter_set) if engine_parameter_set is not None else baseline_parameter_set_for_engine(engine)
    eval_backend = evaluator or ReplayRiskEvaluator(cache_root=request.cache_root, risk_mode=risk_mode)

    results: list[RiskOptimizationResult] = []
    for risk_parameter_set in risk_parameter_sets():
        asset_results: dict[str, RiskAssetEvaluation] = {}
        for asset in request.assets:
            window_rows: list[RiskWindowEvaluation] = []
            for split in splits:
                out = eval_backend.evaluate_window_risk(
                    engine=engine,
                    engine_parameter_set=alpha_params,
                    risk_parameter_set=risk_parameter_set,
                    asset=asset,
                    split=split,
                )
                if out is not None:
                    window_rows.append(out)
            if not window_rows:
                continue
            asset_eval = _aggregate_risk_asset_windows(asset=str(asset).upper(), rows=window_rows)
            asset_results[str(asset).upper()] = asset_eval

        if not asset_results:
            continue

        avg_train_return = _mean([row.train.total_return for row in asset_results.values()])
        avg_test_return = _mean([row.test.total_return for row in asset_results.values()])
        avg_test_sharpe = _mean([row.test.sharpe for row in asset_results.values()])
        avg_win_rate = _mean([row.test.win_rate for row in asset_results.values()])
        max_drawdown = min([row.test.max_drawdown for row in asset_results.values()])
        avg_volatility = _mean([row.test.volatility for row in asset_results.values()])
        long_total_return = _mean([row.test.long_total_return for row in asset_results.values()])
        short_total_return = _mean([row.test.short_total_return for row in asset_results.values()])
        long_trade_count = int(sum(int(row.test.long_trade_count) for row in asset_results.values()))
        short_trade_count = int(sum(int(row.test.short_trade_count) for row in asset_results.values()))
        avg_stability_score = _mean([row.test.stability_score for row in asset_results.values()])
        avg_leverage_cap_saturation = _mean([row.test.leverage_cap_saturation for row in asset_results.values()])
        avg_long_tail_loss_p95 = _mean([row.test.long_tail_loss_p95 for row in asset_results.values()])
        avg_short_tail_loss_p95 = _mean([row.test.short_tail_loss_p95 for row in asset_results.values()])

        score = compute_risk_composite_score(
            sharpe=avg_test_sharpe,
            total_return=avg_test_return,
            max_drawdown=max_drawdown,
            win_rate=avg_win_rate,
            volatility_of_returns=avg_volatility,
        )
        if short_total_return > 0.0:
            score += 0.05
        else:
            score -= 0.05
        if avg_leverage_cap_saturation > 0.70:
            score -= 2.0 * float(avg_leverage_cap_saturation - 0.70)
        overfit_flag, overfit_reasons = detect_overfit_risk(
            avg_train_return=avg_train_return,
            avg_test_return=avg_test_return,
            avg_test_sharpe=avg_test_sharpe,
            max_drawdown=max_drawdown,
            long_trade_count=long_trade_count,
            short_trade_count=short_trade_count,
            short_return_bear=short_total_return,
            leverage_cap_saturation=avg_leverage_cap_saturation,
        )
        results.append(
            RiskOptimizationResult(
                engine=str(engine),
                parameter_set={k: float(v) for k, v in risk_parameter_set.items()},
                per_asset=asset_results,
                avg_train_return=float(avg_train_return),
                avg_test_return=float(avg_test_return),
                avg_test_sharpe=float(avg_test_sharpe),
                avg_win_rate=float(avg_win_rate),
                max_drawdown=float(max_drawdown),
                avg_volatility=float(avg_volatility),
                long_total_return=float(long_total_return),
                short_total_return=float(short_total_return),
                long_trade_count=int(long_trade_count),
                short_trade_count=int(short_trade_count),
                avg_stability_score=float(avg_stability_score),
                avg_leverage_cap_saturation=float(avg_leverage_cap_saturation),
                avg_long_tail_loss_p95=float(avg_long_tail_loss_p95),
                avg_short_tail_loss_p95=float(avg_short_tail_loss_p95),
                score=float(score),
                overfit_flag=bool(overfit_flag),
                overfit_reasons=list(overfit_reasons),
            )
        )

    ranked = sorted(
        results,
        key=lambda r: (
            r.overfit_flag,
            -r.score,
            json.dumps(r.parameter_set, sort_keys=True),
        ),
    )
    for idx, row in enumerate(ranked, start=1):
        row.rank = idx

    reports_dir = Path(request.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = reports_dir / "RISK_OPTIMIZATION_SUMMARY.md"
    results_path = reports_dir / "RISK_OPTIMIZATION_RESULTS.csv"
    heatmap_path = reports_dir / "RISK_OPTIMIZATION_HEATMAP.csv"
    best_config_path = reports_dir / "RISK_CONFIG_BEST.json"

    _write_risk_results_csv(results_path, ranked)
    _write_risk_heatmap_csv(heatmap_path, ranked)
    _write_risk_summary_md(summary_path, ranked, request=request, split_count=len(splits), engine=str(engine))

    best = next((row for row in ranked if not row.overfit_flag), None)
    if best is not None:
        best_payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "engine": str(engine),
            "risk_parameters": dict(best.parameter_set),
        }
        best_config_path.write_text(json.dumps(best_payload, sort_keys=True, indent=2), encoding="utf-8")
    else:
        best_config_path = None
    return RiskOptimizationArtifacts(
        summary_path=summary_path,
        results_csv_path=results_path,
        heatmap_csv_path=heatmap_path,
        best_config_path=best_config_path,
        result_count=len(ranked),
        overfit_count=sum(1 for row in ranked if row.overfit_flag),
        split_count=len(splits),
        best_parameter_set=dict(best.parameter_set) if best else None,
    )


def _aggregate_risk_asset_windows(*, asset: str, rows: list[RiskWindowEvaluation]) -> RiskAssetEvaluation:
    train_metrics = [row.train for row in rows]
    test_metrics = [row.test for row in rows]
    train = _average_risk_metrics(train_metrics)
    test = _average_risk_metrics(test_metrics)
    return RiskAssetEvaluation(
        asset=str(asset).upper(),
        windows=len(rows),
        train=train,
        test=test,
    )


def _average_risk_metrics(rows: list[RiskWindowMetrics]) -> RiskWindowMetrics:
    if not rows:
        return _risk_zero_metrics()
    return RiskWindowMetrics(
        total_return=_mean([x.total_return for x in rows]),
        sharpe=_mean([x.sharpe for x in rows]),
        max_drawdown=_mean([x.max_drawdown for x in rows]),
        win_rate=_mean([x.win_rate for x in rows]),
        volatility=_mean([x.volatility for x in rows]),
        trade_count=int(sum(int(x.trade_count) for x in rows)),
        long_total_return=_mean([x.long_total_return for x in rows]),
        short_total_return=_mean([x.short_total_return for x in rows]),
        long_win_rate=_mean([x.long_win_rate for x in rows]),
        short_win_rate=_mean([x.short_win_rate for x in rows]),
        long_max_drawdown=_mean([x.long_max_drawdown for x in rows]),
        short_max_drawdown=_mean([x.short_max_drawdown for x in rows]),
        long_trade_count=int(sum(int(x.long_trade_count) for x in rows)),
        short_trade_count=int(sum(int(x.short_trade_count) for x in rows)),
        long_avg_rr=_mean([x.long_avg_rr for x in rows]),
        short_avg_rr=_mean([x.short_avg_rr for x in rows]),
        long_max_adverse_excursion=_mean([x.long_max_adverse_excursion for x in rows]),
        short_max_adverse_excursion=_mean([x.short_max_adverse_excursion for x in rows]),
        long_avg_trade=_mean([x.long_avg_trade for x in rows]),
        short_avg_trade=_mean([x.short_avg_trade for x in rows]),
        long_profit_factor=_mean([x.long_profit_factor for x in rows]),
        short_profit_factor=_mean([x.short_profit_factor for x in rows]),
        long_downside_deviation=_mean([x.long_downside_deviation for x in rows]),
        short_downside_deviation=_mean([x.short_downside_deviation for x in rows]),
        long_tail_loss_p95=_mean([x.long_tail_loss_p95 for x in rows]),
        short_tail_loss_p95=_mean([x.short_tail_loss_p95 for x in rows]),
        sharpe_like_overall=_mean([x.sharpe_like_overall for x in rows]),
        sharpe_like_long=_mean([x.sharpe_like_long for x in rows]),
        sharpe_like_short=_mean([x.sharpe_like_short for x in rows]),
        leverage_cap_saturation=_mean([x.leverage_cap_saturation for x in rows]),
        stability_score=_mean([x.stability_score for x in rows]),
    )


def _risk_zero_metrics() -> RiskWindowMetrics:
    return RiskWindowMetrics(
        total_return=0.0,
        sharpe=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        volatility=0.0,
        trade_count=0,
        long_total_return=0.0,
        short_total_return=0.0,
        long_win_rate=0.0,
        short_win_rate=0.0,
        long_max_drawdown=0.0,
        short_max_drawdown=0.0,
        long_trade_count=0,
        short_trade_count=0,
        long_avg_rr=0.0,
        short_avg_rr=0.0,
        long_max_adverse_excursion=0.0,
        short_max_adverse_excursion=0.0,
        long_avg_trade=0.0,
        short_avg_trade=0.0,
        long_profit_factor=0.0,
        short_profit_factor=0.0,
        long_downside_deviation=0.0,
        short_downside_deviation=0.0,
        long_tail_loss_p95=0.0,
        short_tail_loss_p95=0.0,
        sharpe_like_overall=0.0,
        sharpe_like_long=0.0,
        sharpe_like_short=0.0,
        leverage_cap_saturation=0.0,
        stability_score=0.0,
    )


def _aggregate_asset_windows(*, asset: str, rows: list[WindowEvaluation]) -> AssetEvaluation:
    train_metrics = [row.train for row in rows]
    test_metrics = [row.test for row in rows]

    train = _average_metrics(train_metrics)
    test = _average_metrics(test_metrics)
    drawdown_instability = _pstdev([m.max_drawdown for m in test_metrics])

    by_regime: dict[str, WindowMetrics] = {}
    for regime in REGIMES:
        regime_metrics = [row.test_by_regime[regime] for row in rows if regime in row.test_by_regime]
        by_regime[regime] = _average_metrics(regime_metrics) if regime_metrics else _zero_metrics()

    return AssetEvaluation(
        asset=str(asset).upper(),
        windows=len(rows),
        train=train,
        test=test,
        drawdown_instability=float(drawdown_instability),
        test_by_regime=by_regime,
    )


def _average_metrics(rows: list[WindowMetrics]) -> WindowMetrics:
    if not rows:
        return _zero_metrics()
    return WindowMetrics(
        total_return=_mean([x.total_return for x in rows]),
        sharpe=_mean([x.sharpe for x in rows]),
        max_drawdown=_mean([x.max_drawdown for x in rows]),
        win_rate=_mean([x.win_rate for x in rows]),
        stability=_mean([x.stability for x in rows]),
        trade_count=int(sum(int(x.trade_count) for x in rows)),
        long_total_return=_mean([x.long_total_return for x in rows]),
        short_total_return=_mean([x.short_total_return for x in rows]),
        long_win_rate=_mean([x.long_win_rate for x in rows]),
        short_win_rate=_mean([x.short_win_rate for x in rows]),
        long_max_drawdown=_mean([x.long_max_drawdown for x in rows]),
        short_max_drawdown=_mean([x.short_max_drawdown for x in rows]),
        long_trade_count=int(sum(int(x.long_trade_count) for x in rows)),
        short_trade_count=int(sum(int(x.short_trade_count) for x in rows)),
        long_avg_rr=_mean([x.long_avg_rr for x in rows]),
        short_avg_rr=_mean([x.short_avg_rr for x in rows]),
        long_max_adverse_excursion=_mean([x.long_max_adverse_excursion for x in rows]),
        short_max_adverse_excursion=_mean([x.short_max_adverse_excursion for x in rows]),
    )


def _compute_metrics(returns: pd.Series, shifted_positions: pd.Series) -> WindowMetrics:
    if returns.empty:
        return _zero_metrics()

    ret = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    pos = pd.to_numeric(shifted_positions, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    equity = (1.0 + ret).cumprod()
    total_return = float(equity.iloc[-1] - 1.0) if len(equity) else 0.0
    std = float(ret.std(ddof=0))
    mean = float(ret.mean())
    sharpe = (mean / std * math.sqrt(365.0)) if std > 0 else 0.0
    drawdown = float((equity / equity.cummax() - 1.0).min()) if len(equity) else 0.0
    active_mask = pos.abs() > 0
    active_returns = ret[active_mask]
    win_rate = float((active_returns > 0.0).mean()) if len(active_returns) else 0.0
    stability = float(ret.var(ddof=0)) if len(ret) else 0.0
    nonzero = pos.abs() > 1e-12
    prev = pos.shift(1).fillna(0.0)
    prev_nonzero = prev.abs() > 1e-12
    entry = (~prev_nonzero) & nonzero
    flip = prev_nonzero & nonzero & (np.sign(prev) != np.sign(pos))
    trade_count = int((entry | flip).sum())
    long_mask = pos > 1e-12
    short_mask = pos < -1e-12
    long_returns = ret[long_mask]
    short_returns = ret[short_mask]
    prev_sign = np.sign(prev.to_numpy(dtype=float))
    cur_sign = np.sign(pos.to_numpy(dtype=float))
    long_trade_count = int(np.sum((cur_sign > 0) & (prev_sign <= 0)))
    short_trade_count = int(np.sum((cur_sign < 0) & (prev_sign >= 0)))

    return WindowMetrics(
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=drawdown,
        win_rate=win_rate,
        stability=stability,
        trade_count=trade_count,
        long_total_return=_compute_total_return_from_series(long_returns),
        short_total_return=_compute_total_return_from_series(short_returns),
        long_win_rate=float((long_returns > 0.0).mean()) if len(long_returns) else 0.0,
        short_win_rate=float((short_returns > 0.0).mean()) if len(short_returns) else 0.0,
        long_max_drawdown=_compute_max_drawdown_from_series(long_returns),
        short_max_drawdown=_compute_max_drawdown_from_series(short_returns),
        long_trade_count=int(long_trade_count),
        short_trade_count=int(short_trade_count),
        long_avg_rr=_average_rr_from_series(long_returns),
        short_avg_rr=_average_rr_from_series(short_returns),
        long_max_adverse_excursion=float(long_returns.min()) if len(long_returns) else 0.0,
        short_max_adverse_excursion=float(short_returns.min()) if len(short_returns) else 0.0,
    )


def _compute_total_return_from_series(values: pd.Series) -> float:
    if values is None or len(values) == 0:
        return 0.0
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    equity = float((1.0 + clean).prod())
    return float(equity - 1.0)


def _compute_max_drawdown_from_series(values: pd.Series) -> float:
    if values is None or len(values) == 0:
        return 0.0
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    equity = (1.0 + clean).cumprod()
    return float((equity / equity.cummax() - 1.0).min()) if len(equity) else 0.0


def _average_rr_from_series(values: pd.Series) -> float:
    if values is None or len(values) == 0:
        return 0.0
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    wins = clean[clean > 0.0]
    losses = clean[clean < 0.0]
    if len(wins) == 0 or len(losses) == 0:
        return 0.0
    avg_win = float(wins.mean())
    avg_loss = float(abs(losses.mean()))
    if avg_loss <= 1e-12:
        return 0.0
    return float(avg_win / avg_loss)


def _compute_total_return_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    equity = 1.0
    for value in values:
        equity *= (1.0 + float(value))
    return float(equity - 1.0)


def _compute_max_drawdown_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in values:
        equity *= (1.0 + float(value))
        peak = max(peak, equity)
        dd = (equity / peak) - 1.0 if peak > 0.0 else 0.0
        max_dd = min(max_dd, dd)
    return float(max_dd)


def _average_rr_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    wins = [float(v) for v in values if float(v) > 0.0]
    losses = [abs(float(v)) for v in values if float(v) < 0.0]
    if not wins or not losses:
        return 0.0
    avg_win = float(sum(wins) / len(wins))
    avg_loss = float(sum(losses) / len(losses))
    if avg_loss <= 1e-12:
        return 0.0
    return float(avg_win / avg_loss)


def _profit_factor_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    gross_profit = float(sum(float(v) for v in values if float(v) > 0.0))
    gross_loss = float(abs(sum(float(v) for v in values if float(v) < 0.0)))
    if gross_loss <= 1e-12:
        return 0.0
    return float(gross_profit / gross_loss)


def _downside_deviation_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    downside = [float(min(0.0, float(v))) for v in values]
    if not downside:
        return 0.0
    squares = [x * x for x in downside]
    return float(math.sqrt(sum(squares) / len(squares)))


def _tail_loss_p95_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    arr = np.array([float(v) for v in values], dtype=float)
    if arr.size == 0:
        return 0.0
    return float(np.percentile(arr, 5.0))


def _sharpe_like_from_list(values: list[float]) -> float:
    if not values:
        return 0.0
    arr = np.array([float(v) for v in values], dtype=float)
    if arr.size == 0:
        return 0.0
    std = float(arr.std(ddof=0))
    if std <= 1e-12:
        return 0.0
    return float(arr.mean() / std)


def _simulate_risk_frame(
    *,
    feat: pd.DataFrame,
    positions: pd.Series,
    symbol: str,
    engine: str,
    engine_confidence: float,
    starting_equity: float,
    risk_mode: str,
    risk_parameter_set: Mapping[str, float],
) -> RiskWindowMetrics:
    if feat.empty or len(feat) < 2:
        return _risk_zero_metrics()

    close = pd.to_numeric(feat["close"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
    high = pd.to_numeric(feat.get("high", feat["close"]), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(close).to_numpy(dtype=float)
    low = pd.to_numeric(feat.get("low", feat["close"]), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(close).to_numpy(dtype=float)
    atr_pct = pd.to_numeric(feat.get("atr_pct", 0.0), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
    adx = pd.to_numeric(feat.get("adx_proxy", 0.0), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
    regime = feat.get("regime")
    regime_arr = regime.astype(str).to_numpy() if regime is not None else np.array(["UNKNOWN"] * len(close), dtype=object)

    pos_raw = pd.to_numeric(positions, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    pos_sign = np.sign(pos_raw.to_numpy(dtype=float)).astype(int)

    mode = "growth" if str(risk_mode).lower() == "growth" else "normal"
    cfg = RiskConfig(
        atr_multiplier=float(risk_parameter_set.get("atr_multiplier_long", risk_parameter_set.get("atr_multiplier", 1.5))),
        rr_ratio=float(risk_parameter_set.get("rr_ratio_long", risk_parameter_set.get("rr_ratio", 2.0))),
        leverage_cap=float(risk_parameter_set.get("leverage_cap_long", risk_parameter_set.get("leverage_cap", 5.0))),
        atr_multiplier_long=float(
            risk_parameter_set.get("atr_multiplier_long", risk_parameter_set.get("atr_multiplier", 1.5))
        ),
        atr_multiplier_short=float(
            risk_parameter_set.get("atr_multiplier_short", risk_parameter_set.get("atr_multiplier", 1.5))
        ),
        rr_ratio_long=float(risk_parameter_set.get("rr_ratio_long", risk_parameter_set.get("rr_ratio", 2.0))),
        rr_ratio_short=float(risk_parameter_set.get("rr_ratio_short", risk_parameter_set.get("rr_ratio", 2.0))),
        leverage_cap_long=float(
            risk_parameter_set.get("leverage_cap_long", risk_parameter_set.get("leverage_cap", 5.0))
        ),
        leverage_cap_short=float(
            risk_parameter_set.get("leverage_cap_short", risk_parameter_set.get("leverage_cap", 5.0))
        ),
        trailing_activation_long=float(risk_parameter_set.get("trailing_activation_long", 1.0)),
        trailing_activation_short=float(risk_parameter_set.get("trailing_activation_short", 1.0)),
        volatility_threshold=float(risk_parameter_set.get("volatility_threshold", 0.03)),
        vol_k=float(risk_parameter_set.get("vol_k", 15.0)),
        drawdown_sensitivity=float(risk_parameter_set.get("drawdown_sensitivity", 1.0)),
        confidence_floor=float(risk_parameter_set.get("confidence_floor", 0.60)),
    )

    equity = float(starting_equity)
    if not math.isfinite(equity) or equity <= 0.0:
        equity = 0.0
    peak = float(equity)

    bar_returns: list[float] = [0.0]
    equity_curve: list[float] = [float(equity)]
    trade_returns: list[float] = []
    long_trade_returns: list[float] = []
    short_trade_returns: list[float] = []
    long_trade_mae: list[float] = []
    short_trade_mae: list[float] = []
    leverage_used: list[float] = []
    leverage_cap_hits = 0
    leverage_entry_count = 0

    in_pos = False
    side = 0  # -1 short, +1 long
    qty = 0.0
    entry_price = 0.0
    equity_at_entry = 0.0
    initial_sl = 0.0
    sl = 0.0
    tp = 0.0
    trailing_rules = None
    trade_mae = 0.0

    for i in range(1, len(close)):
        prev_close = float(close[i - 1])
        c = float(close[i])
        hi = float(high[i])
        lo = float(low[i])

        equity_before = float(equity)

        if in_pos and qty != 0.0 and prev_close > 0.0:
            if entry_price > 0.0:
                if side > 0:
                    trade_mae = min(float(trade_mae), float((lo - entry_price) / entry_price))
                else:
                    trade_mae = min(float(trade_mae), float((entry_price - hi) / entry_price))
            exit_price: float | None = None
            if side > 0:
                if lo <= sl:
                    exit_price = float(sl)
                elif hi >= tp:
                    exit_price = float(tp)
            else:
                if hi >= sl:
                    exit_price = float(sl)
                elif lo <= tp:
                    exit_price = float(tp)

            if exit_price is not None:
                equity += float(side) * float(qty) * (float(exit_price) - prev_close)
                total_pnl = float(side) * float(qty) * (float(exit_price) - float(entry_price))
                trade_ret = total_pnl / equity_at_entry if equity_at_entry > 0 else 0.0
                trade_returns.append(trade_ret)
                if side > 0:
                    long_trade_returns.append(float(trade_ret))
                    long_trade_mae.append(float(trade_mae))
                else:
                    short_trade_returns.append(float(trade_ret))
                    short_trade_mae.append(float(trade_mae))
                in_pos = False
                side = 0
                qty = 0.0
                entry_price = 0.0
                equity_at_entry = 0.0
                initial_sl = 0.0
                sl = 0.0
                tp = 0.0
                trailing_rules = None
                trade_mae = 0.0
            else:
                equity += float(side) * float(qty) * (c - prev_close)
                if trailing_rules is not None:
                    sl = float(
                        apply_trailing_stop(
                            side="long" if side > 0 else "short",
                            entry_price=entry_price,
                            initial_sl_price=initial_sl,
                            current_sl_price=sl,
                            current_price=c,
                            rules=trailing_rules,
                        )
                    )

        if not math.isfinite(equity) or equity <= 0.0:
            equity = 0.0

        bar_returns.append((equity / equity_before - 1.0) if equity_before > 0 else 0.0)
        equity_curve.append(float(equity))
        peak = max(float(peak), float(equity))

        desired = int(pos_sign[i]) if i < len(pos_sign) else 0

        if in_pos and desired != side:
            # Close at bar close (already marked-to-market).
            total_pnl = float(side) * float(qty) * (c - float(entry_price))
            trade_ret = total_pnl / equity_at_entry if equity_at_entry > 0 else 0.0
            trade_returns.append(trade_ret)
            if side > 0:
                long_trade_returns.append(float(trade_ret))
                long_trade_mae.append(float(trade_mae))
            else:
                short_trade_returns.append(float(trade_ret))
                short_trade_mae.append(float(trade_mae))
            in_pos = False
            side = 0
            qty = 0.0
            entry_price = 0.0
            equity_at_entry = 0.0
            initial_sl = 0.0
            sl = 0.0
            tp = 0.0
            trailing_rules = None
            trade_mae = 0.0

        if not in_pos and desired != 0 and c > 0.0:
            drawdown_pct = ((peak - equity) / peak) if peak > 0 else 0.0
            reg = str(regime_arr[i]).upper() if i < len(regime_arr) else "UNKNOWN"
            decision = compute_risk_decision(
                asset=str(symbol).upper(),
                asset_class=asset_class_for_symbol(symbol),
                regime=reg,
                regime_probability_vector={reg: 1.0},
                engine_name=str(engine),
                engine_confidence=float(engine_confidence),
                atr_pct=float(atr_pct[i]) if i < len(atr_pct) else 0.0,
                adx=float(adx[i]) if i < len(adx) else 0.0,
                rolling_drawdown_pct=float(drawdown_pct),
                account_equity=float(equity),
                risk_mode=mode,  # type: ignore[arg-type]
                entry_price=float(c),
                side="long" if desired > 0 else "short",
                config=cfg,
            )
            if decision.position_size_usd > 0.0 and decision.leverage >= 1.0:
                in_pos = True
                side = int(desired)
                entry_price = float(c)
                equity_at_entry = float(equity)
                qty = float(decision.position_size_usd) / float(entry_price)
                initial_sl = float(decision.sl_price)
                sl = float(decision.sl_price)
                tp = float(decision.tp_price)
                trailing_rules = decision.trailing_rules
                trade_mae = 0.0
                leverage_value = float(decision.leverage)
                leverage_used.append(leverage_value)
                leverage_entry_count += 1
                side_cap = float(cfg.leverage_cap_short) if side < 0 and cfg.leverage_cap_short is not None else float(
                    cfg.leverage_cap_long if cfg.leverage_cap_long is not None else cfg.leverage_cap
                )
                side_cap = max(1.0, float(side_cap))
                if leverage_value >= (0.999 * side_cap):
                    leverage_cap_hits += 1

    ret = np.array(bar_returns[1:], dtype=float)
    mean = float(ret.mean()) if len(ret) else 0.0
    std = float(ret.std(ddof=0)) if len(ret) else 0.0
    sharpe = (mean / std * math.sqrt(365.0)) if std > 0 else 0.0
    equity_arr = np.array(equity_curve, dtype=float)
    if len(equity_arr):
        running_max = np.maximum.accumulate(equity_arr)
        drawdown = float((equity_arr / running_max - 1.0).min())
        total_return = float(equity_arr[-1] / equity_arr[0] - 1.0) if equity_arr[0] > 0 else 0.0
    else:
        drawdown = 0.0
        total_return = 0.0

    win_rate = float(np.mean([1.0 if x > 0.0 else 0.0 for x in trade_returns])) if trade_returns else 0.0
    volatility = float(std)
    long_win_rate = float(np.mean([1.0 if x > 0.0 else 0.0 for x in long_trade_returns])) if long_trade_returns else 0.0
    short_win_rate = float(np.mean([1.0 if x > 0.0 else 0.0 for x in short_trade_returns])) if short_trade_returns else 0.0
    leverage_cap_saturation = float(leverage_cap_hits / leverage_entry_count) if leverage_entry_count > 0 else 0.0

    long_avg_trade = _mean([float(x) for x in long_trade_returns]) if long_trade_returns else 0.0
    short_avg_trade = _mean([float(x) for x in short_trade_returns]) if short_trade_returns else 0.0
    long_profit_factor = _profit_factor_from_list(long_trade_returns)
    short_profit_factor = _profit_factor_from_list(short_trade_returns)
    long_downside_deviation = _downside_deviation_from_list(long_trade_returns)
    short_downside_deviation = _downside_deviation_from_list(short_trade_returns)
    long_tail_loss_p95 = _tail_loss_p95_from_list(long_trade_returns)
    short_tail_loss_p95 = _tail_loss_p95_from_list(short_trade_returns)
    sharpe_like_overall = _sharpe_like_from_list(trade_returns)
    sharpe_like_long = _sharpe_like_from_list(long_trade_returns)
    sharpe_like_short = _sharpe_like_from_list(short_trade_returns)

    all_profit_factor = _profit_factor_from_list(trade_returns)
    all_tail_loss_p95 = _tail_loss_p95_from_list(trade_returns)
    return_quality = _clamp((0.6 * float(total_return)) + (0.4 * float(all_profit_factor - 1.0)), -1.0, 1.0)
    risk_control = _clamp(1.0 - abs(float(drawdown)) - abs(float(all_tail_loss_p95)), -1.0, 1.0)
    consistency = _clamp(float(win_rate), 0.0, 1.0)
    robustness = _clamp(1.0 - float(leverage_cap_saturation), 0.0, 1.0)
    stability_score = _clamp(
        0.35 * return_quality + 0.25 * risk_control + 0.20 * consistency + 0.20 * robustness,
        -1.0,
        1.0,
    )
    return RiskWindowMetrics(
        total_return=float(total_return),
        sharpe=float(sharpe),
        max_drawdown=float(drawdown),
        win_rate=float(win_rate),
        volatility=float(volatility),
        trade_count=int(len(trade_returns)),
        long_total_return=_compute_total_return_from_list(long_trade_returns),
        short_total_return=_compute_total_return_from_list(short_trade_returns),
        long_win_rate=float(long_win_rate),
        short_win_rate=float(short_win_rate),
        long_max_drawdown=_compute_max_drawdown_from_list(long_trade_returns),
        short_max_drawdown=_compute_max_drawdown_from_list(short_trade_returns),
        long_trade_count=int(len(long_trade_returns)),
        short_trade_count=int(len(short_trade_returns)),
        long_avg_rr=_average_rr_from_list(long_trade_returns),
        short_avg_rr=_average_rr_from_list(short_trade_returns),
        long_max_adverse_excursion=float(min(long_trade_mae)) if long_trade_mae else 0.0,
        short_max_adverse_excursion=float(min(short_trade_mae)) if short_trade_mae else 0.0,
        long_avg_trade=float(long_avg_trade),
        short_avg_trade=float(short_avg_trade),
        long_profit_factor=float(long_profit_factor),
        short_profit_factor=float(short_profit_factor),
        long_downside_deviation=float(long_downside_deviation),
        short_downside_deviation=float(short_downside_deviation),
        long_tail_loss_p95=float(long_tail_loss_p95),
        short_tail_loss_p95=float(short_tail_loss_p95),
        sharpe_like_overall=float(sharpe_like_overall),
        sharpe_like_long=float(sharpe_like_long),
        sharpe_like_short=float(sharpe_like_short),
        leverage_cap_saturation=float(leverage_cap_saturation),
        stability_score=float(stability_score),
    )


def _write_results_csv(path: Path, rows: list[OptimizationResult]) -> None:
    class_fieldnames: list[str] = []
    for cls in ASSET_CLASSES:
        class_fieldnames.append(f"class_score_{cls}")
        class_fieldnames.append(f"class_trades_{cls}")

    fieldnames = [
        "rank",
        "engine",
        "parameter_set",
        "per_asset_metrics",
        "avg_train_sharpe",
        "avg_test_sharpe",
        "avg_total_return",
        "avg_win_rate",
        "max_drawdown",
        "avg_stability",
        "stability_penalty",
        "long_total_return",
        "short_total_return",
        "long_trade_count",
        "short_trade_count",
        "regime_stability",
        "final_score",
        *class_fieldnames,
        "overfit_flag",
        "overfit_reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            class_cells: dict[str, str] = {}
            for cls in ASSET_CLASSES:
                score = row.class_scores.get(cls)
                trades = row.class_trades.get(cls)
                class_cells[f"class_score_{cls}"] = f"{float(score):.8f}" if score is not None else ""
                class_cells[f"class_trades_{cls}"] = str(int(trades)) if trades is not None else ""
            writer.writerow(
                {
                    "rank": int(row.rank),
                    "engine": row.engine,
                    "parameter_set": json.dumps(row.parameter_set, sort_keys=True),
                    "per_asset_metrics": json.dumps(
                        {k: v.as_dict() for k, v in sorted(row.per_asset.items())},
                        sort_keys=True,
                    ),
                    "avg_train_sharpe": f"{row.avg_train_sharpe:.8f}",
                    "avg_test_sharpe": f"{row.avg_test_sharpe:.8f}",
                    "avg_total_return": f"{row.avg_total_return:.8f}",
                    "avg_win_rate": f"{row.avg_win_rate:.8f}",
                    "max_drawdown": f"{row.max_drawdown:.8f}",
                    "avg_stability": f"{row.avg_stability:.8f}",
                    "stability_penalty": f"{row.stability_penalty:.8f}",
                    "long_total_return": f"{row.long_total_return:.8f}",
                    "short_total_return": f"{row.short_total_return:.8f}",
                    "long_trade_count": int(row.long_trade_count),
                    "short_trade_count": int(row.short_trade_count),
                    "regime_stability": f"{row.regime_stability:.8f}",
                    "final_score": f"{row.final_score:.8f}",
                    **class_cells,
                    "overfit_flag": int(row.overfit_flag),
                    "overfit_reasons": ";".join(row.overfit_reasons),
                }
            )


def _write_heatmap_csv(path: Path, rows: list[OptimizationResult]) -> None:
    bucket: dict[tuple[str, str, float], list[OptimizationResult]] = {}
    for row in rows:
        for param_name, param_value in row.parameter_set.items():
            key = (row.engine, str(param_name), float(param_value))
            bucket.setdefault(key, []).append(row)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "engine",
                "parameter",
                "value",
                "sample_count",
                "overfit_count",
                "avg_final_score",
                "avg_non_overfit_final_score",
            ]
        )
        for key in sorted(bucket.keys()):
            sample = bucket[key]
            non_overfit = [row.final_score for row in sample if not row.overfit_flag]
            writer.writerow(
                [
                    key[0],
                    key[1],
                    f"{key[2]:.8f}",
                    len(sample),
                    sum(1 for row in sample if row.overfit_flag),
                    f"{_mean([row.final_score for row in sample]):.8f}",
                    f"{_mean(non_overfit):.8f}" if non_overfit else "",
                ]
            )


def _write_summary_md(
    path: Path,
    rows: list[OptimizationResult],
    *,
    request: OptimizationRequest,
    split_count: int,
) -> None:
    overfit_count = sum(1 for row in rows if row.overfit_flag)
    class_map: dict[str, list[str]] = {}
    for sym in request.assets:
        class_map.setdefault(asset_class_for_symbol(sym), []).append(sym)
    present_classes = sorted(class_map.keys())
    lines = [
        "# Engine Optimization Summary",
        "",
        f"- Assets: `{','.join(request.assets)}`",
        f"- Asset Classes: `{json.dumps({k: len(v) for k, v in sorted(class_map.items())}, sort_keys=True)}`",
        f"- Date Range: `{request.optimize_start.isoformat()}` -> `{request.optimize_end.isoformat()}`",
        f"- Walk Window Days: `{int(request.walk_window_days)}`",
        f"- Walk Step Days: `{int(request.walk_step_days)}`",
        f"- Splits: `{int(split_count)}`",
        f"- Parameter Sets Evaluated: `{len(rows)}`",
        f"- Overfit-Rejected Sets: `{int(overfit_count)}`",
        "",
        "## Top Candidates (Non-Overfit)",
        "",
    ]

    for engine in sorted(ENGINE_PARAMETER_GRID.keys()):
        lines.append(f"### {engine}")
        winners = [row for row in rows if row.engine == engine and not row.overfit_flag][:5]
        if not winners:
            lines.append("- No non-overfit candidate found.")
            lines.append("")
            continue
        for row in winners:
            lines.append(
                "- rank={rank} final={score:.6f} sharpe={sharpe:.4f} return={ret:.4f} long={long_ret:.4f} short={short_ret:.4f} dd={dd:.4f} params={params}".format(
                    rank=row.rank,
                    score=row.final_score,
                    sharpe=row.avg_test_sharpe,
                    ret=row.avg_total_return,
                    long_ret=row.long_total_return,
                    short_ret=row.short_total_return,
                    dd=row.max_drawdown,
                    params=json.dumps(row.parameter_set, sort_keys=True),
                )
            )
        lines.append("")

    lines.extend(["## Per-Class Leaderboards (Non-Overfit)", ""])
    for cls in present_classes:
        lines.append(f"### {cls}")
        candidates = [row for row in rows if (not row.overfit_flag and cls in row.class_scores)]
        candidates.sort(
            key=lambda r: (
                -float(r.class_scores.get(cls, 0.0)),
                -float(r.final_score),
                int(r.rank),
            )
        )
        if not candidates:
            lines.append("- No non-overfit candidate found.")
            lines.append("")
            continue
        top = candidates[:5]
        top_trades = int(top[0].class_trades.get(cls, 0))
        if top_trades < MIN_TRADES_PER_CLASS:
            lines.append(
                f"- WARNING: top candidate has only {top_trades} trades for class `{cls}` (<{MIN_TRADES_PER_CLASS})."
            )
        for row in top:
            class_score = float(row.class_scores.get(cls, 0.0))
            class_trades = int(row.class_trades.get(cls, 0))
            lines.append(
                "- rank={rank} class_score={cs:.6f} class_trades={trades} final={final:.6f} engine={engine} params={params}".format(
                    rank=row.rank,
                    cs=class_score,
                    trades=class_trades,
                    final=row.final_score,
                    engine=row.engine,
                    params=json.dumps(row.parameter_set, sort_keys=True),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Artifacts",
            "",
            "- `reports/ENGINE_OPTIMIZATION_RESULTS.csv`",
            "- `reports/ENGINE_OPTIMIZATION_HEATMAP.csv`",
            "- `reports/ENGINE_OPTIMIZATION_SUMMARY.md`",
            "",
            "## Interpretation",
            "",
            "- `final_score` is side-aware: balances long + short returns, regime stability, and drawdown quality.",
            "- Treat overfit rows as rejected even when raw return appears strong.",
            "- Validate top-ranked rows with an out-of-sample holdout before any config promotion.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_risk_results_csv(path: Path, rows: list[RiskOptimizationResult]) -> None:
    fieldnames = [
        "rank",
        "engine",
        "risk_parameter_set",
        "per_asset_metrics",
        "avg_train_return",
        "avg_test_return",
        "avg_test_sharpe",
        "avg_win_rate",
        "max_drawdown",
        "avg_volatility",
        "long_total_return",
        "short_total_return",
        "long_trade_count",
        "short_trade_count",
        "avg_stability_score",
        "avg_leverage_cap_saturation",
        "avg_long_tail_loss_p95",
        "avg_short_tail_loss_p95",
        "score",
        "overfit_flag",
        "overfit_reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "rank": int(row.rank),
                    "engine": row.engine,
                    "risk_parameter_set": json.dumps(row.parameter_set, sort_keys=True),
                    "per_asset_metrics": json.dumps(
                        {k: v.as_dict() for k, v in sorted(row.per_asset.items())},
                        sort_keys=True,
                    ),
                    "avg_train_return": f"{row.avg_train_return:.8f}",
                    "avg_test_return": f"{row.avg_test_return:.8f}",
                    "avg_test_sharpe": f"{row.avg_test_sharpe:.8f}",
                    "avg_win_rate": f"{row.avg_win_rate:.8f}",
                    "max_drawdown": f"{row.max_drawdown:.8f}",
                    "avg_volatility": f"{row.avg_volatility:.8f}",
                    "long_total_return": f"{row.long_total_return:.8f}",
                    "short_total_return": f"{row.short_total_return:.8f}",
                    "long_trade_count": int(row.long_trade_count),
                    "short_trade_count": int(row.short_trade_count),
                    "avg_stability_score": f"{row.avg_stability_score:.8f}",
                    "avg_leverage_cap_saturation": f"{row.avg_leverage_cap_saturation:.8f}",
                    "avg_long_tail_loss_p95": f"{row.avg_long_tail_loss_p95:.8f}",
                    "avg_short_tail_loss_p95": f"{row.avg_short_tail_loss_p95:.8f}",
                    "score": f"{row.score:.8f}",
                    "overfit_flag": int(row.overfit_flag),
                    "overfit_reasons": ";".join(row.overfit_reasons),
                }
            )


def _write_risk_heatmap_csv(path: Path, rows: list[RiskOptimizationResult]) -> None:
    bucket: dict[tuple[str, float], list[RiskOptimizationResult]] = {}
    for row in rows:
        for param_name, param_value in row.parameter_set.items():
            key = (str(param_name), float(param_value))
            bucket.setdefault(key, []).append(row)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "parameter",
                "value",
                "sample_count",
                "overfit_count",
                "avg_score",
                "avg_non_overfit_score",
            ]
        )
        for key in sorted(bucket.keys()):
            sample = bucket[key]
            non_overfit = [row.score for row in sample if not row.overfit_flag]
            writer.writerow(
                [
                    key[0],
                    f"{key[1]:.8f}",
                    len(sample),
                    sum(1 for row in sample if row.overfit_flag),
                    f"{_mean([row.score for row in sample]):.8f}",
                    f"{_mean(non_overfit):.8f}" if non_overfit else "",
                ]
            )


def _write_risk_summary_md(
    path: Path,
    rows: list[RiskOptimizationResult],
    *,
    request: OptimizationRequest,
    split_count: int,
    engine: str,
) -> None:
    overfit_count = sum(1 for row in rows if row.overfit_flag)
    best = next((row for row in rows if not row.overfit_flag), None)
    lines = [
        "# Risk Optimization Summary",
        "",
        f"- Engine: `{engine}` (alpha params fixed)",
        f"- Assets: `{','.join(request.assets)}`",
        f"- Date Range: `{request.optimize_start.isoformat()}` -> `{request.optimize_end.isoformat()}`",
        f"- Walk Window Days: `{int(request.walk_window_days)}`",
        f"- Walk Step Days: `{int(request.walk_step_days)}`",
        f"- Splits: `{int(split_count)}`",
        f"- Parameter Sets Evaluated: `{len(rows)}`",
        f"- Overfit-Rejected Sets: `{int(overfit_count)}`",
        "",
        "## Best Candidate (Non-Overfit)",
        "",
    ]
    if best is None:
        lines.append("- No non-overfit candidate found.")
    else:
        lines.append(f"- rank={best.rank} score={best.score:.6f} params={json.dumps(best.parameter_set, sort_keys=True)}")
        lines.append(
            "- sharpe={sharpe:.4f} return={ret:.4f} long={long_ret:.4f} short={short_ret:.4f} dd={dd:.4f} win_rate={wr:.4f} vol={vol:.4f} stability={stability:.4f} cap_sat={cap_sat:.4f} tail_l={tail_l:.4f} tail_s={tail_s:.4f}".format(
                sharpe=best.avg_test_sharpe,
                ret=best.avg_test_return,
                long_ret=best.long_total_return,
                short_ret=best.short_total_return,
                dd=best.max_drawdown,
                wr=best.avg_win_rate,
                vol=best.avg_volatility,
                stability=best.avg_stability_score,
                cap_sat=best.avg_leverage_cap_saturation,
                tail_l=best.avg_long_tail_loss_p95,
                tail_s=best.avg_short_tail_loss_p95,
            )
        )

    lines.extend(["", "## Top Candidates (Non-Overfit)", ""])
    winners = [row for row in rows if not row.overfit_flag][:10]
    if not winners:
        lines.append("- None")
    else:
        for row in winners:
            lines.append(
                "- rank={rank} score={score:.6f} sharpe={sharpe:.4f} return={ret:.4f} long={long_ret:.4f} short={short_ret:.4f} dd={dd:.4f} win_rate={wr:.4f} vol={vol:.4f} stability={stability:.4f} cap_sat={cap_sat:.4f} params={params}".format(
                    rank=row.rank,
                    score=row.score,
                    sharpe=row.avg_test_sharpe,
                    ret=row.avg_test_return,
                    long_ret=row.long_total_return,
                    short_ret=row.short_total_return,
                    dd=row.max_drawdown,
                    wr=row.avg_win_rate,
                    vol=row.avg_volatility,
                    stability=row.avg_stability_score,
                    cap_sat=row.avg_leverage_cap_saturation,
                    params=json.dumps(row.parameter_set, sort_keys=True),
                )
            )

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `reports/RISK_OPTIMIZATION_RESULTS.csv`",
            "- `reports/RISK_OPTIMIZATION_HEATMAP.csv`",
            "- `reports/RISK_OPTIMIZATION_SUMMARY.md`",
            "- `reports/RISK_CONFIG_BEST.json`",
            "",
            "## Interpretation",
            "",
            "- Optimize risk parameters only; signal logic remains fixed during the search.",
            "- Treat overfit rows as rejected even when raw return appears strong.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _zero_metrics() -> WindowMetrics:
    return WindowMetrics(
        total_return=0.0,
        sharpe=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        stability=0.0,
        trade_count=0,
        long_total_return=0.0,
        short_total_return=0.0,
        long_win_rate=0.0,
        short_win_rate=0.0,
        long_max_drawdown=0.0,
        short_max_drawdown=0.0,
        long_trade_count=0,
        short_trade_count=0,
        long_avg_rr=0.0,
        short_avg_rr=0.0,
        long_max_adverse_excursion=0.0,
        short_max_adverse_excursion=0.0,
    )


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _pstdev(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(statistics.pstdev(values))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
