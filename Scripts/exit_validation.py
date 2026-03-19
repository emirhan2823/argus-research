"""Exit Policy Validation — Quantitative analysis of trailing stop + dynamic exit layer.

Reads executed decisions from war_backtest_lab DBs, loads OHLC candle data,
re-evaluates exits with different exit_policy configs, and produces
comprehensive reports.

Usage:
    python Scripts/exit_validation.py

Output: reports/exit_validation/
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.exit_policy import (
    EngineExitConfig,
    ExitResult,
    evaluate_exit_bar_by_bar,
    get_engine_exit_config,
    REASON_STOP_LOSS,
    REASON_BREAKEVEN_STOP,
    REASON_TRAILING_STOP,
    REASON_TIME_STOP,
    REASON_TIME_EXIT,
)

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────

SCENARIO_DB_BASE = Path("runs/war_backtest_lab/luna_crash_2022/20260225_081038/luna_crash_2022__orion_off")
MONTHS = ["2022-05", "2022-06", "2022-07"]
PARQUET_ROOT = Path("data/binance")
HOLD_MINUTES = 360  # 6h outer bound (matches scenario avg_hold_hours=5.2)
CANDLE_INTERVAL_MINUTES = 60  # 1h candles
OUTPUT_DIR = Path("reports/exit_validation")
FEES_PCT = 0.001  # 0.1% per side
SLIPPAGE_PCT = 0.0005  # 0.05%

# Phase 2 sweep grid
TRAIL_PCT_GRID = [0.006, 0.01, 0.015]
BE_TRIGGER_GRID = [1.0, 1.5, 2.0]


# ─────────────────────────────────────────────────────────────────────
# Data Loading
# ─────────────────────────────────────────────────────────────────────


@dataclass
class TradeDecision:
    """One executed advisory decision from the DB."""

    decision_id: int
    timestamp: datetime
    symbol: str
    side: str  # "long" | "short"
    stop_loss_pct: float
    confidence: float
    engine: str
    regime: str
    atr_pct: float
    leverage: float
    position_size_pct: float
    adx_14: float = 0.0
    volume_ratio: float = 0.0


@dataclass
class TradeResult:
    """Result of exit evaluation for one trade."""

    decision: TradeDecision
    entry_price: float
    exit_price: float
    exit_time: datetime
    exit_reason: str
    hold_minutes: float
    gross_pnl_pct: float
    net_pnl_pct: float
    be_locked: bool = False


def _load_decisions() -> list[TradeDecision]:
    """Load all executed decisions from Luna crash DBs."""
    decisions: list[TradeDecision] = []
    for month in MONTHS:
        db_path = SCENARIO_DB_BASE / month / "war_backtest_lab_v25.db"
        if not db_path.exists():
            print(f"  [WARN] DB not found: {db_path}")
            continue
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            """SELECT decision_id, timestamp, symbol, action,
                      stop_loss_pct, confidence, engine, regime,
                      gate_results_json, leverage, position_size_pct
               FROM decisions WHERE status='executed'
               ORDER BY timestamp"""
        ).fetchall()
        for row in rows:
            gr = json.loads(row[8]) if row[8] else {}
            fs = gr.get("features_snapshot", {})
            atr = float(fs.get("atr_14_pct", 0.0) or 0.0)
            adx = float(fs.get("adx_14", 0.0) or 0.0)
            vol_ratio = float(fs.get("volume_ratio", 0.0) or 0.0)
            ts = datetime.fromisoformat(row[1])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            decisions.append(TradeDecision(
                decision_id=row[0],
                timestamp=ts,
                symbol=row[2],
                side=row[3].lower(),
                stop_loss_pct=float(row[4] or 0.01),
                confidence=float(row[5] or 0.0),
                engine=row[6] or "UNKNOWN",
                regime=row[7] or "UNKNOWN",
                atr_pct=atr,
                leverage=float(row[9] or 1.0),
                position_size_pct=float(row[10] or 0.01),
                adx_14=adx,
                volume_ratio=vol_ratio,
            ))
        conn.close()
    return decisions


def _load_candles(symbol: str) -> pd.DataFrame:
    """Load 1h OHLC candles for 2022 from parquet."""
    path = PARQUET_ROOT / symbol / "1h" / "2022.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


# ─────────────────────────────────────────────────────────────────────
# Exit Evaluation
# ─────────────────────────────────────────────────────────────────────


def _evaluate_trade(
    decision: TradeDecision,
    candle_df: pd.DataFrame,
    config_override: EngineExitConfig | None = None,
) -> TradeResult | None:
    """Evaluate a single trade using exit_policy."""
    entry_time = decision.timestamp
    exit_time_limit = entry_time + timedelta(minutes=HOLD_MINUTES)

    # Get entry price from candle at decision time
    mask_entry = candle_df["timestamp"] == pd.Timestamp(entry_time)
    if mask_entry.sum() == 0:
        # Try nearest candle
        mask_entry = candle_df["timestamp"] <= pd.Timestamp(entry_time)
        if mask_entry.sum() == 0:
            return None
        entry_idx = candle_df.loc[mask_entry].index[-1]
    else:
        entry_idx = candle_df.loc[mask_entry].index[0]

    entry_price = float(candle_df.loc[entry_idx, "close"])

    # Get candles between entry and exit window
    mask = (candle_df["timestamp"] > pd.Timestamp(entry_time)) & \
           (candle_df["timestamp"] <= pd.Timestamp(exit_time_limit))
    window = candle_df.loc[mask]
    if window.empty:
        return None

    # Build candle list
    candle_list: list[dict] = []
    for _, row in window.iterrows():
        ts = row["timestamp"].to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        candle_list.append({
            "timestamp": ts,
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    # Compute stop price
    stop_price = (
        entry_price * (1.0 - decision.stop_loss_pct)
        if decision.side == "long"
        else entry_price * (1.0 + decision.stop_loss_pct)
    )

    # Use override config or default engine config
    config = config_override if config_override is not None else get_engine_exit_config(decision.engine)

    result = evaluate_exit_bar_by_bar(
        candles=candle_list,
        side=decision.side,
        entry_price=entry_price,
        initial_stop_price=stop_price,
        atr_pct=decision.atr_pct,
        config=config,
    )

    if result is None:
        return None

    # Compute PnL
    if decision.side == "long":
        gross_pnl = (result.exit_price - entry_price) / entry_price * decision.leverage
    else:
        gross_pnl = (entry_price - result.exit_price) / entry_price * decision.leverage

    net_pnl = gross_pnl - (2 * FEES_PCT + SLIPPAGE_PCT) * decision.leverage

    hold_mins = (result.exit_time - entry_time).total_seconds() / 60.0

    return TradeResult(
        decision=decision,
        entry_price=entry_price,
        exit_price=result.exit_price,
        exit_time=result.exit_time,
        exit_reason=result.exit_reason,
        hold_minutes=hold_mins,
        gross_pnl_pct=gross_pnl,
        net_pnl_pct=net_pnl,
        be_locked=result.be_locked,
    )


def _evaluate_all(
    decisions: list[TradeDecision],
    candles_by_symbol: dict[str, pd.DataFrame],
    config_override: EngineExitConfig | None = None,
) -> list[TradeResult]:
    """Evaluate all decisions with given config."""
    results: list[TradeResult] = []
    for d in decisions:
        df = candles_by_symbol.get(d.symbol)
        if df is None or df.empty:
            continue
        tr = _evaluate_trade(d, df, config_override)
        if tr is not None:
            results.append(tr)
    return results


# ─────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Metrics:
    """Comprehensive trade metrics."""

    total_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    median_win: float = 0.0
    avg_loss: float = 0.0
    median_loss: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    total_return_pct: float = 0.0
    avg_hold_minutes: float = 0.0
    exit_reasons: dict[str, int] = field(default_factory=dict)


def _compute_metrics(results: list[TradeResult]) -> Metrics:
    """Compute comprehensive metrics from trade results."""
    if not results:
        return Metrics()

    wins = [r for r in results if r.net_pnl_pct > 0]
    losses = [r for r in results if r.net_pnl_pct <= 0]

    wr = len(wins) / len(results) if results else 0.0

    win_pnls = [r.net_pnl_pct for r in wins]
    loss_pnls = [r.net_pnl_pct for r in losses]

    avg_w = statistics.mean(win_pnls) if win_pnls else 0.0
    med_w = statistics.median(win_pnls) if win_pnls else 0.0
    avg_l = statistics.mean(loss_pnls) if loss_pnls else 0.0
    med_l = statistics.median(loss_pnls) if loss_pnls else 0.0

    exp = wr * avg_w - (1.0 - wr) * abs(avg_l)

    gross_profit = sum(r.net_pnl_pct for r in wins)
    gross_loss = abs(sum(r.net_pnl_pct for r in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown (cumulative equity curve)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in sorted(results, key=lambda x: x.decision.timestamp):
        equity *= (1.0 + r.net_pnl_pct)
        peak = max(peak, equity)
        dd = (equity / peak) - 1.0
        max_dd = min(max_dd, dd)

    total_ret = (equity - 1.0) * 100.0

    # Exit reason counts
    reasons: dict[str, int] = {}
    for r in results:
        reasons[r.exit_reason] = reasons.get(r.exit_reason, 0) + 1

    avg_hold = statistics.mean(r.hold_minutes for r in results) if results else 0.0

    return Metrics(
        total_trades=len(results),
        win_rate=wr,
        avg_win=avg_w,
        median_win=med_w,
        avg_loss=avg_l,
        median_loss=med_l,
        expectancy=exp,
        profit_factor=pf,
        max_drawdown_pct=max_dd * 100.0,
        total_return_pct=total_ret,
        avg_hold_minutes=avg_hold,
        exit_reasons=reasons,
    )


# ─────────────────────────────────────────────────────────────────────
# Phase 1: Baseline vs New Exit Policy
# ─────────────────────────────────────────────────────────────────────


def _run_baseline(
    decisions: list[TradeDecision],
    candles: dict[str, pd.DataFrame],
) -> list[TradeResult]:
    """Run with all exit features disabled (old SL-only behavior)."""
    baseline_config = EngineExitConfig(
        trailing_enabled=False,
        be_lock_enabled=False,
        max_hold_candles=9999,  # no engine time-stop, rely on hold_minutes
    )
    return _evaluate_all(decisions, candles, config_override=baseline_config)


def _run_new_policy(
    decisions: list[TradeDecision],
    candles: dict[str, pd.DataFrame],
) -> list[TradeResult]:
    """Run with engine-specific exit configs (new exit policy)."""
    return _evaluate_all(decisions, candles, config_override=None)


# ─────────────────────────────────────────────────────────────────────
# Phase 2: Trail Sweep
# ─────────────────────────────────────────────────────────────────────


def _run_sweep(
    decisions: list[TradeDecision],
    candles: dict[str, pd.DataFrame],
) -> list[dict]:
    """Run parameter sweep for POSEIDON trailing config."""
    results_table: list[dict] = []

    for trail_pct in TRAIL_PCT_GRID:
        for be_mult in BE_TRIGGER_GRID:
            # Build custom config: POSEIDON gets sweep params, others keep defaults
            def _make_config(engine: str) -> EngineExitConfig:
                if engine == "POSEIDON":
                    return EngineExitConfig(
                        trailing_enabled=True,
                        trail_pct=trail_pct,
                        be_lock_enabled=True,
                        be_trigger_atr_mult=be_mult,
                        be_buffer_pct=0.001,
                        max_hold_candles=24,
                    )
                return get_engine_exit_config(engine)

            # Evaluate each trade with its engine-specific config
            trade_results: list[TradeResult] = []
            for d in decisions:
                df = candles.get(d.symbol)
                if df is None or df.empty:
                    continue
                config = _make_config(d.engine)
                tr = _evaluate_trade(d, df, config_override=config)
                if tr is not None:
                    trade_results.append(tr)

            m = _compute_metrics(trade_results)

            # Count specific exit reasons
            trail_count = m.exit_reasons.get(REASON_TRAILING_STOP, 0)
            be_count = m.exit_reasons.get(REASON_BREAKEVEN_STOP, 0)

            results_table.append({
                "trail_pct": trail_pct,
                "be_trigger_atr_mult": be_mult,
                "total_trades": m.total_trades,
                "total_return_pct": round(m.total_return_pct, 4),
                "expectancy": round(m.expectancy * 100, 4),  # in bps
                "profit_factor": round(m.profit_factor, 4),
                "max_drawdown_pct": round(m.max_drawdown_pct, 4),
                "win_rate": round(m.win_rate * 100, 2),
                "avg_win_pct": round(m.avg_win * 100, 4),
                "avg_loss_pct": round(m.avg_loss * 100, 4),
                "trailing_stop_hit": trail_count,
                "breakeven_stop_hit": be_count,
            })

    # Sort by expectancy desc, then PF desc, then DD asc (least negative)
    results_table.sort(
        key=lambda x: (-x["expectancy"], -x["profit_factor"], x["max_drawdown_pct"]),
    )
    return results_table


# ─────────────────────────────────────────────────────────────────────
# Phase 3: Long vs Short Diagnosis
# ─────────────────────────────────────────────────────────────────────


def _long_short_diagnosis(results: list[TradeResult]) -> dict:
    """Split metrics by side."""
    longs = [r for r in results if r.decision.side == "long"]
    shorts = [r for r in results if r.decision.side == "short"]

    ml = _compute_metrics(longs)
    ms = _compute_metrics(shorts)

    diagnosis: dict = {
        "long": {
            "trades": ml.total_trades,
            "win_rate": round(ml.win_rate * 100, 2),
            "avg_win": round(ml.avg_win * 100, 4),
            "avg_loss": round(ml.avg_loss * 100, 4),
            "expectancy_bps": round(ml.expectancy * 100, 4),
            "exit_reasons": ml.exit_reasons,
            "total_return_pct": round(ml.total_return_pct, 4),
            "avg_hold_minutes": round(ml.avg_hold_minutes, 1),
        },
        "short": {
            "trades": ms.total_trades,
            "win_rate": round(ms.win_rate * 100, 2),
            "avg_win": round(ms.avg_win * 100, 4),
            "avg_loss": round(ms.avg_loss * 100, 4),
            "expectancy_bps": round(ms.expectancy * 100, 4),
            "exit_reasons": ms.exit_reasons,
            "total_return_pct": round(ms.total_return_pct, 4),
            "avg_hold_minutes": round(ms.avg_hold_minutes, 1),
        },
    }

    # Identify dominant loss exit reason for weaker side
    if ms.expectancy < ml.expectancy:
        loss_shorts = [r for r in shorts if r.net_pnl_pct <= 0]
        loss_reasons: dict[str, int] = {}
        for r in loss_shorts:
            loss_reasons[r.exit_reason] = loss_reasons.get(r.exit_reason, 0) + 1
        diagnosis["short_loss_dominant_exit"] = loss_reasons
    elif ml.expectancy < ms.expectancy:
        loss_longs = [r for r in longs if r.net_pnl_pct <= 0]
        loss_reasons = {}
        for r in loss_longs:
            loss_reasons[r.exit_reason] = loss_reasons.get(r.exit_reason, 0) + 1
        diagnosis["long_loss_dominant_exit"] = loss_reasons

    return diagnosis


# ─────────────────────────────────────────────────────────────────────
# Phase 4: Regime Sensitivity
# ─────────────────────────────────────────────────────────────────────


def _regime_diagnosis(results: list[TradeResult]) -> list[dict]:
    """Group metrics by regime."""
    by_regime: dict[str, list[TradeResult]] = {}
    for r in results:
        regime = r.decision.regime
        by_regime.setdefault(regime, []).append(r)

    rows: list[dict] = []
    for regime, trades in sorted(by_regime.items()):
        m = _compute_metrics(trades)
        rows.append({
            "regime": regime,
            "trades": m.total_trades,
            "win_rate": round(m.win_rate * 100, 2),
            "expectancy_bps": round(m.expectancy * 100, 4),
            "profit_factor": round(m.profit_factor, 4),
            "total_return_pct": round(m.total_return_pct, 4),
            "dominant_exit": max(m.exit_reasons, key=m.exit_reasons.get) if m.exit_reasons else "N/A",
            "exit_distribution": str(m.exit_reasons),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────
# Win/Loss Structure
# ─────────────────────────────────────────────────────────────────────


def _win_loss_structure(results: list[TradeResult]) -> dict:
    """Compute win/loss structural analysis."""
    wins = [r for r in results if r.net_pnl_pct > 0]
    losses = [r for r in results if r.net_pnl_pct <= 0]

    win_holds = [r.hold_minutes for r in wins]
    loss_holds = [r.hold_minutes for r in losses]

    win_reasons: dict[str, int] = {}
    for r in wins:
        win_reasons[r.exit_reason] = win_reasons.get(r.exit_reason, 0) + 1

    loss_reasons: dict[str, int] = {}
    for r in losses:
        loss_reasons[r.exit_reason] = loss_reasons.get(r.exit_reason, 0) + 1

    return {
        "winners_avg_hold_min": round(statistics.mean(win_holds), 1) if win_holds else 0.0,
        "winners_med_hold_min": round(statistics.median(win_holds), 1) if win_holds else 0.0,
        "losers_avg_hold_min": round(statistics.mean(loss_holds), 1) if loss_holds else 0.0,
        "losers_med_hold_min": round(statistics.median(loss_holds), 1) if loss_holds else 0.0,
        "winners_exit_reasons": win_reasons,
        "losers_exit_reasons": loss_reasons,
    }


# ─────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> {path}")


def _fmt_pct(v: float) -> str:
    return f"{v:+.4f}%"


def _fmt_bps(v: float) -> str:
    return f"{v:+.2f} bps"


def _generate_summary(
    baseline_m: Metrics,
    new_m: Metrics,
    baseline_wl: dict,
    new_wl: dict,
    ls_diag: dict,
    regime_rows: list[dict],
    sweep_results: list[dict],
) -> str:
    """Generate EXIT_VALIDATION_SUMMARY.md content."""
    lines: list[str] = []
    lines.append("# Exit Policy Validation Summary")
    lines.append(f"\nScenario: Luna Crash 2022 (May-Jul 2022)")
    lines.append(f"Candle interval: 1h | Hold window: {HOLD_MINUTES}m")
    lines.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Before vs After
    lines.append("\n## Phase 1: Before vs After\n")
    lines.append("| Metric | Baseline (SL-only) | New (Exit Policy) | Delta |")
    lines.append("|--------|-------------------|-------------------|-------|")

    def _row(name: str, b: float, n: float, fmt: str = ".4f") -> str:
        delta = n - b
        return f"| {name} | {b:{fmt}} | {n:{fmt}} | {delta:+{fmt}} |"

    lines.append(_row("Total Trades", baseline_m.total_trades, new_m.total_trades, "d"))
    lines.append(_row("Win Rate %", baseline_m.win_rate * 100, new_m.win_rate * 100))
    lines.append(_row("Avg Win %", baseline_m.avg_win * 100, new_m.avg_win * 100))
    lines.append(_row("Median Win %", baseline_m.median_win * 100, new_m.median_win * 100))
    lines.append(_row("Avg Loss %", baseline_m.avg_loss * 100, new_m.avg_loss * 100))
    lines.append(_row("Median Loss %", baseline_m.median_loss * 100, new_m.median_loss * 100))
    lines.append(_row("Expectancy bps", baseline_m.expectancy * 100, new_m.expectancy * 100))
    lines.append(_row("Profit Factor", baseline_m.profit_factor, new_m.profit_factor))
    lines.append(_row("Max DD %", baseline_m.max_drawdown_pct, new_m.max_drawdown_pct))
    lines.append(_row("Total Return %", baseline_m.total_return_pct, new_m.total_return_pct))
    lines.append(_row("Avg Hold min", baseline_m.avg_hold_minutes, new_m.avg_hold_minutes, ".1f"))

    # Exit distribution
    lines.append("\n### Exit Reason Distribution\n")
    lines.append("| Exit Reason | Baseline | New |")
    lines.append("|-------------|----------|-----|")
    all_reasons = sorted(set(list(baseline_m.exit_reasons.keys()) + list(new_m.exit_reasons.keys())))
    for reason in all_reasons:
        b_count = baseline_m.exit_reasons.get(reason, 0)
        n_count = new_m.exit_reasons.get(reason, 0)
        lines.append(f"| {reason} | {b_count} | {n_count} |")

    # Win/Loss structure
    lines.append("\n### Win/Loss Structure\n")
    lines.append("| Metric | Baseline | New |")
    lines.append("|--------|----------|-----|")
    lines.append(f"| Winners avg hold (min) | {baseline_wl['winners_avg_hold_min']} | {new_wl['winners_avg_hold_min']} |")
    lines.append(f"| Losers avg hold (min) | {baseline_wl['losers_avg_hold_min']} | {new_wl['losers_avg_hold_min']} |")
    lines.append(f"| Winners exit reasons | {baseline_wl['winners_exit_reasons']} | {new_wl['winners_exit_reasons']} |")
    lines.append(f"| Losers exit reasons | {baseline_wl['losers_exit_reasons']} | {new_wl['losers_exit_reasons']} |")

    # Phase 2: Sweep
    lines.append("\n## Phase 2: Trail Parameter Sweep (POSEIDON)\n")
    if sweep_results:
        lines.append("| trail_pct | be_mult | trades | return% | expect(bps) | PF | maxDD% | WR% | trail_hits | be_hits |")
        lines.append("|-----------|---------|--------|---------|-------------|-----|--------|-----|------------|---------|")
        for row in sweep_results:
            lines.append(
                f"| {row['trail_pct']} | {row['be_trigger_atr_mult']} "
                f"| {row['total_trades']} | {row['total_return_pct']:.2f} "
                f"| {row['expectancy']:.2f} | {row['profit_factor']:.3f} "
                f"| {row['max_drawdown_pct']:.2f} | {row['win_rate']:.1f} "
                f"| {row['trailing_stop_hit']} | {row['breakeven_stop_hit']} |"
            )
        best = sweep_results[0]
        lines.append(f"\n**Best config**: trail_pct={best['trail_pct']}, be_mult={best['be_trigger_atr_mult']} "
                     f"(expectancy={best['expectancy']:.2f} bps, PF={best['profit_factor']:.3f})")

    # Phase 3: Long/Short
    lines.append("\n## Phase 3: Long vs Short Diagnosis\n")
    for side_name in ["long", "short"]:
        s = ls_diag[side_name]
        lines.append(f"### {side_name.upper()}")
        lines.append(f"- Trades: {s['trades']}")
        lines.append(f"- Win Rate: {s['win_rate']}%")
        lines.append(f"- Avg Win: {s['avg_win']}%")
        lines.append(f"- Avg Loss: {s['avg_loss']}%")
        lines.append(f"- Expectancy: {s['expectancy_bps']} bps")
        lines.append(f"- Total Return: {s['total_return_pct']}%")
        lines.append(f"- Exit Reasons: {s['exit_reasons']}")
        lines.append("")

    if "short_loss_dominant_exit" in ls_diag:
        lines.append(f"**Short losses dominated by**: {ls_diag['short_loss_dominant_exit']}")
    if "long_loss_dominant_exit" in ls_diag:
        lines.append(f"**Long losses dominated by**: {ls_diag['long_loss_dominant_exit']}")

    # Phase 4: Regime
    lines.append("\n## Phase 4: Regime Sensitivity\n")
    if regime_rows:
        lines.append("| Regime | Trades | WR% | Expect(bps) | PF | Return% | Dominant Exit |")
        lines.append("|--------|--------|-----|-------------|-----|---------|---------------|")
        for row in regime_rows:
            lines.append(
                f"| {row['regime']} | {row['trades']} | {row['win_rate']} "
                f"| {row['expectancy_bps']:.2f} | {row['profit_factor']:.3f} "
                f"| {row['total_return_pct']:.2f} | {row['dominant_exit']} |"
            )

    # Verdict
    lines.append("\n## Verdict\n")
    exp_delta = (new_m.expectancy - baseline_m.expectancy) * 100
    pf_delta = new_m.profit_factor - baseline_m.profit_factor
    dd_delta = new_m.max_drawdown_pct - baseline_m.max_drawdown_pct

    if exp_delta > 0.5 and pf_delta > 0:
        verdict = "YES"
        explanation = (
            f"Trailing layer improves expectancy by {exp_delta:+.2f} bps and "
            f"profit factor by {pf_delta:+.3f}. "
        )
    elif exp_delta > 0:
        verdict = "MARGINAL"
        explanation = (
            f"Small expectancy improvement ({exp_delta:+.2f} bps) but "
            f"profit factor delta is {pf_delta:+.3f}. "
        )
    else:
        verdict = "NO"
        explanation = (
            f"Expectancy delta is {exp_delta:+.2f} bps (negative or flat). "
        )

    if dd_delta < 0:
        explanation += f"Drawdown improved by {abs(dd_delta):.2f}pp."
    else:
        explanation += f"Drawdown worsened by {dd_delta:.2f}pp."

    lines.append(f"**Is trailing layer materially improving structural edge? {verdict}**")
    lines.append(f"\n{explanation}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("ARGUS Exit Policy Validation")
    print("=" * 60)

    # Load data
    print("\n[1/6] Loading decisions...")
    decisions = _load_decisions()
    print(f"  Total executed decisions: {len(decisions)}")
    if not decisions:
        print("  ERROR: No executed decisions found. Exiting.")
        sys.exit(1)

    symbols = sorted(set(d.symbol for d in decisions))
    engines = sorted(set(d.engine for d in decisions))
    print(f"  Symbols: {symbols}")
    print(f"  Engines: {engines}")

    print("\n[2/6] Loading candle data...")
    candles: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = _load_candles(sym)
        candles[sym] = df
        print(f"  {sym}: {len(df)} candles")

    # Phase 1: Baseline vs New
    print("\n[3/6] Phase 1: Baseline (SL-only) vs New Exit Policy...")
    baseline_results = _run_baseline(decisions, candles)
    new_results = _run_new_policy(decisions, candles)
    baseline_m = _compute_metrics(baseline_results)
    new_m = _compute_metrics(new_results)

    print(f"\n  BASELINE: {baseline_m.total_trades} trades, WR={baseline_m.win_rate*100:.1f}%, "
          f"E={baseline_m.expectancy*100:.2f}bps, PF={baseline_m.profit_factor:.3f}, "
          f"Ret={baseline_m.total_return_pct:.2f}%")
    print(f"  NEW:      {new_m.total_trades} trades, WR={new_m.win_rate*100:.1f}%, "
          f"E={new_m.expectancy*100:.2f}bps, PF={new_m.profit_factor:.3f}, "
          f"Ret={new_m.total_return_pct:.2f}%")
    print(f"  DELTA:    E={((new_m.expectancy - baseline_m.expectancy)*100):+.2f}bps, "
          f"PF={new_m.profit_factor - baseline_m.profit_factor:+.3f}, "
          f"DD={new_m.max_drawdown_pct - baseline_m.max_drawdown_pct:+.2f}pp")

    baseline_wl = _win_loss_structure(baseline_results)
    new_wl = _win_loss_structure(new_results)

    # Phase 2: Sweep
    print("\n[4/6] Phase 2: Trail parameter sweep...")
    sweep_results = _run_sweep(decisions, candles)
    if sweep_results:
        print(f"  Best: trail={sweep_results[0]['trail_pct']}, "
              f"be_mult={sweep_results[0]['be_trigger_atr_mult']}, "
              f"E={sweep_results[0]['expectancy']:.2f}bps")

    # Phase 3: Long/Short
    print("\n[5/6] Phase 3: Long vs Short diagnosis...")
    ls_diag = _long_short_diagnosis(new_results)
    print(f"  LONG:  {ls_diag['long']['trades']} trades, WR={ls_diag['long']['win_rate']}%, "
          f"E={ls_diag['long']['expectancy_bps']} bps")
    print(f"  SHORT: {ls_diag['short']['trades']} trades, WR={ls_diag['short']['win_rate']}%, "
          f"E={ls_diag['short']['expectancy_bps']} bps")

    # Phase 4: Regime
    print("\n[6/6] Phase 4: Regime sensitivity...")
    regime_rows = _regime_diagnosis(new_results)
    for row in regime_rows:
        print(f"  {row['regime']}: {row['trades']} trades, WR={row['win_rate']}%, "
              f"E={row['expectancy_bps']} bps")

    # Write outputs
    print("\n" + "=" * 60)
    print("Writing reports...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # trail_sweep_results.csv
    _write_csv(OUTPUT_DIR / "trail_sweep_results.csv", sweep_results)

    # exit_reason_breakdown.csv
    exit_breakdown: list[dict] = []
    for reason in sorted(set(list(baseline_m.exit_reasons.keys()) + list(new_m.exit_reasons.keys()))):
        # Global
        exit_breakdown.append({
            "scope": "global",
            "side": "all",
            "exit_reason": reason,
            "baseline_count": baseline_m.exit_reasons.get(reason, 0),
            "new_count": new_m.exit_reasons.get(reason, 0),
        })
    # By side for new policy
    for side in ["long", "short"]:
        side_results = [r for r in new_results if r.decision.side == side]
        for r in side_results:
            found = False
            for eb in exit_breakdown:
                if eb["scope"] == "by_side" and eb["side"] == side and eb["exit_reason"] == r.exit_reason:
                    eb["new_count"] += 1
                    found = True
                    break
            if not found:
                exit_breakdown.append({
                    "scope": "by_side",
                    "side": side,
                    "exit_reason": r.exit_reason,
                    "baseline_count": 0,
                    "new_count": 1,
                })
    _write_csv(OUTPUT_DIR / "exit_reason_breakdown.csv", exit_breakdown)

    # long_short_diagnosis.csv
    ls_rows = []
    for side_name in ["long", "short"]:
        s = ls_diag[side_name]
        ls_rows.append({
            "side": side_name,
            "trades": s["trades"],
            "win_rate": s["win_rate"],
            "avg_win_pct": s["avg_win"],
            "avg_loss_pct": s["avg_loss"],
            "expectancy_bps": s["expectancy_bps"],
            "total_return_pct": s["total_return_pct"],
            "avg_hold_minutes": s["avg_hold_minutes"],
            "exit_reasons": str(s["exit_reasons"]),
        })
    _write_csv(OUTPUT_DIR / "long_short_diagnosis.csv", ls_rows)

    # regime_diagnosis.csv
    _write_csv(OUTPUT_DIR / "regime_diagnosis.csv", regime_rows)

    # EXIT_VALIDATION_SUMMARY.md
    summary = _generate_summary(
        baseline_m, new_m, baseline_wl, new_wl,
        ls_diag, regime_rows, sweep_results,
    )
    summary_path = OUTPUT_DIR / "EXIT_VALIDATION_SUMMARY.md"
    summary_path.write_text(summary, encoding="utf-8")
    print(f"  -> {summary_path}")

    print("\n" + "=" * 60)
    print("Validation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
