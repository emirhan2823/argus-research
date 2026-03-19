"""Backtest Validation Framework — filter calibration and overfit detection.

Tracks win rate per engine per regime, enforces minimum sample sizes,
and checks for out-of-sample degradation. Used after backtest runs to
validate that the filtering pipeline produces robust results.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class TradeRecord:
    """Minimal trade record for validation analysis."""

    pnl: float
    engine: str
    regime: str
    confidence: float
    is_in_sample: bool = True  # True = training window, False = test window


@dataclass(frozen=True)
class EngineRegimeStats:
    """Performance stats for a specific engine-regime combination."""

    engine: str
    regime: str
    total_trades: int
    wins: int
    win_rate: float
    avg_return: float
    sufficient_sample: bool  # total_trades >= min_sample_size


@dataclass(frozen=True)
class ValidationReport:
    """Complete validation report with overfit risk assessment."""

    overall_win_rate: float
    overall_trade_count: int
    engine_regime_stats: list[EngineRegimeStats]
    in_sample_win_rate: float
    out_of_sample_win_rate: float
    degradation_pct: float          # (IS_WR - OOS_WR) / IS_WR
    overfitting_risk: str           # "LOW" | "MEDIUM" | "HIGH"
    recommendations: list[str]


def profit_factor(pnls: Sequence[float]) -> float:
    """Compute profit factor: gross profit / gross loss."""
    gains = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))
    if losses < 1e-9:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def win_rate_by_group(
    trades: Sequence[TradeRecord],
    group_key: str,  # "engine" | "regime" | "engine_regime"
) -> dict[str, float]:
    """Compute win rate grouped by engine, regime, or engine+regime."""
    groups: dict[str, list[float]] = defaultdict(list)

    for t in trades:
        if group_key == "engine":
            key = t.engine
        elif group_key == "regime":
            key = t.regime
        else:
            key = f"{t.engine}_{t.regime}"
        groups[key].append(t.pnl)

    result = {}
    for key, pnls in groups.items():
        wins = sum(1 for p in pnls if p > 0)
        result[key] = wins / len(pnls) if pnls else 0.0
    return result


def validate_filter_performance(
    trades: Sequence[TradeRecord],
    *,
    min_sample_size: int = 30,
    max_degradation_pct: float = 0.15,
) -> ValidationReport:
    """Validate filter performance across engine-regime combinations.

    Checks:
    1. Win rate per engine per regime (with sample size requirements)
    2. In-sample vs out-of-sample degradation
    3. Overfitting risk assessment
    """
    if not trades:
        return ValidationReport(
            overall_win_rate=0.0,
            overall_trade_count=0,
            engine_regime_stats=[],
            in_sample_win_rate=0.0,
            out_of_sample_win_rate=0.0,
            degradation_pct=0.0,
            overfitting_risk="LOW",
            recommendations=["No trades to validate"],
        )

    # Overall metrics
    total = len(trades)
    total_wins = sum(1 for t in trades if t.pnl > 0)
    overall_wr = total_wins / total

    # Engine × Regime breakdown
    buckets: dict[tuple[str, str], list[TradeRecord]] = defaultdict(list)
    for t in trades:
        buckets[(t.engine, t.regime)].append(t)

    er_stats = []
    for (eng, reg), bucket_trades in sorted(buckets.items()):
        n = len(bucket_trades)
        wins = sum(1 for t in bucket_trades if t.pnl > 0)
        avg_ret = sum(t.pnl for t in bucket_trades) / n if n > 0 else 0.0
        er_stats.append(EngineRegimeStats(
            engine=eng,
            regime=reg,
            total_trades=n,
            wins=wins,
            win_rate=round(wins / n, 4) if n > 0 else 0.0,
            avg_return=round(avg_ret, 6),
            sufficient_sample=n >= min_sample_size,
        ))

    # In-sample vs out-of-sample
    is_trades = [t for t in trades if t.is_in_sample]
    oos_trades = [t for t in trades if not t.is_in_sample]

    is_wr = (sum(1 for t in is_trades if t.pnl > 0) / len(is_trades)) if is_trades else 0.0
    oos_wr = (sum(1 for t in oos_trades if t.pnl > 0) / len(oos_trades)) if oos_trades else 0.0

    if is_wr > 0:
        degradation = (is_wr - oos_wr) / is_wr
    else:
        degradation = 0.0

    # Overfitting risk assessment
    if degradation > 0.25:
        overfit_risk = "HIGH"
    elif degradation > max_degradation_pct:
        overfit_risk = "MEDIUM"
    else:
        overfit_risk = "LOW"

    # Recommendations
    recommendations = []

    if overall_wr < 0.60:
        recommendations.append(
            f"Overall win rate {overall_wr:.1%} below 60% target. "
            "Consider tightening confluence min_factors_required to 5."
        )

    for stat in er_stats:
        if not stat.sufficient_sample:
            recommendations.append(
                f"{stat.engine}×{stat.regime}: only {stat.total_trades} trades "
                f"(need {min_sample_size}). Statistics unreliable."
            )
        elif stat.win_rate < 0.50:
            recommendations.append(
                f"{stat.engine}×{stat.regime}: win rate {stat.win_rate:.1%} is below 50%. "
                "Consider disabling this engine-regime combination."
            )

    if overfit_risk == "HIGH":
        recommendations.append(
            f"OOS degradation {degradation:.1%} is severe. "
            "Likely overfitting — reduce filter complexity or widen walk-forward windows."
        )
    elif overfit_risk == "MEDIUM":
        recommendations.append(
            f"OOS degradation {degradation:.1%} is moderate. "
            "Monitor closely and consider loosening thresholds slightly."
        )

    if not oos_trades:
        recommendations.append(
            "No out-of-sample trades found. "
            "Run walk-forward validation to assess overfitting risk."
        )

    return ValidationReport(
        overall_win_rate=round(overall_wr, 4),
        overall_trade_count=total,
        engine_regime_stats=er_stats,
        in_sample_win_rate=round(is_wr, 4),
        out_of_sample_win_rate=round(oos_wr, 4),
        degradation_pct=round(degradation, 4),
        overfitting_risk=overfit_risk,
        recommendations=recommendations,
    )
