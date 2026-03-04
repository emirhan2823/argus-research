"""Bull 2024 Exit Validation — TITAN trailing stop analysis for trend-following.

Generates synthetic TITAN trend signals from 2024 1h candle data using
simple trend detection (EMA crossover + ADX proxy), then evaluates:
  Phase 1: Baseline (SL-only) vs TITAN trailing (1% trail)
  Phase 2: Trail parameter sweep (0.8%, 1.0%, 1.5%, 2.0%)

Usage:
    python Scripts/exit_validation_bull2024.py

Output: reports/exit_validation/BULL_2024_EXIT_VALIDATION.md
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.exit_policy import (
    EngineExitConfig,
    evaluate_exit_bar_by_bar,
    REASON_STOP_LOSS,
    REASON_TRAILING_STOP,
    REASON_TIME_STOP,
    REASON_TIME_EXIT,
)

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────

PARQUET_ROOT = Path("data/binance")
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
HOLD_CANDLES = 16  # TITAN default max_hold
STOP_LOSS_PCT = 0.02  # 2% SL (ATR×2 proxy)
FEES_PCT = 0.001
SLIPPAGE_PCT = 0.0005
LEVERAGE = 3.0  # conservative trend leverage

OUTPUT_DIR = Path("reports/exit_validation")

# Trail sweep grid
TRAIL_PCT_GRID = [0.008, 0.01, 0.015, 0.02]

# TITAN baseline: SL-only + time-stop (no trailing, no BE)
TITAN_BASELINE = EngineExitConfig(
    trailing_enabled=False, be_lock_enabled=False, max_hold_candles=HOLD_CANDLES,
)


# ─────────────────────────────────────────────────────────────────────
# Data & Signal Generation
# ─────────────────────────────────────────────────────────────────────


def _load_candles(symbol: str) -> pd.DataFrame:
    path = PARQUET_ROOT / symbol / "1h" / "2024.parquet"
    if not path.exists():
        print(f"  [WARN] Parquet not found: {path}")
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Simple ADX computation for trend strength detection."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx


def _generate_trend_signals(df: pd.DataFrame, symbol: str) -> list[dict]:
    """Generate TITAN-style trend signals using EMA crossover + ADX filter.

    Entry conditions (simplified):
    - EMA21 > EMA55 -> long; EMA21 < EMA55 -> short
    - ADX > 25 (trend strength filter)
    - Min 24h between signals (avoid overtrading)
    """
    if len(df) < 60:
        return []

    df = df.copy()
    df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_55"] = df["close"].ewm(span=55, adjust=False).mean()
    df["adx"] = _compute_adx(df)
    df["atr_14"] = (df["high"] - df["low"]).ewm(span=14, adjust=False).mean()
    df["atr_pct"] = df["atr_14"] / df["close"]

    signals: list[dict] = []
    last_signal_idx = -25  # allow first signal early

    for i in range(56, len(df) - HOLD_CANDLES - 1):
        if i - last_signal_idx < 24:
            continue

        adx = df.iloc[i]["adx"]
        if adx < 25:
            continue

        ema_21 = df.iloc[i]["ema_21"]
        ema_55 = df.iloc[i]["ema_55"]
        ema_diff_pct = (ema_21 - ema_55) / ema_55

        # Need clear trend direction
        if abs(ema_diff_pct) < 0.005:
            continue

        side = "long" if ema_diff_pct > 0 else "short"

        signals.append({
            "idx": i,
            "timestamp": df.iloc[i]["timestamp"].to_pydatetime(),
            "symbol": symbol,
            "side": side,
            "entry_price": float(df.iloc[i]["close"]),
            "atr_pct": float(df.iloc[i]["atr_pct"]),
            "adx": float(adx),
        })
        last_signal_idx = i

    return signals


# ─────────────────────────────────────────────────────────────────────
# Exit Evaluation
# ─────────────────────────────────────────────────────────────────────


@dataclass
class TradeResult:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    exit_reason: str
    exit_candle_idx: int
    hold_candles: int
    gross_pnl_pct: float
    net_pnl_pct: float
    be_locked: bool = False


def _evaluate_signal(
    signal: dict,
    df: pd.DataFrame,
    config: EngineExitConfig,
) -> TradeResult | None:
    idx = signal["idx"]
    entry_price = signal["entry_price"]
    side = signal["side"]

    sl_price = (
        entry_price * (1.0 - STOP_LOSS_PCT) if side == "long"
        else entry_price * (1.0 + STOP_LOSS_PCT)
    )

    # Get candles after entry
    window = df.iloc[idx + 1: idx + 1 + HOLD_CANDLES + 2]
    if window.empty:
        return None

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

    result = evaluate_exit_bar_by_bar(
        candles=candle_list,
        side=side,
        entry_price=entry_price,
        initial_stop_price=sl_price,
        atr_pct=signal["atr_pct"],
        config=config,
    )
    if result is None:
        return None

    if side == "long":
        gross = (result.exit_price - entry_price) / entry_price * LEVERAGE
    else:
        gross = (entry_price - result.exit_price) / entry_price * LEVERAGE

    net = gross - (2 * FEES_PCT + SLIPPAGE_PCT) * LEVERAGE

    return TradeResult(
        symbol=signal["symbol"],
        side=side,
        entry_price=entry_price,
        exit_price=result.exit_price,
        exit_reason=result.exit_reason,
        exit_candle_idx=result.exit_candle_index,
        hold_candles=result.candles_evaluated,
        gross_pnl_pct=gross,
        net_pnl_pct=net,
        be_locked=result.be_locked,
    )


# ─────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────


@dataclass
class Metrics:
    total_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy_bps: float = 0.0
    profit_factor: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_hold_candles: float = 0.0
    exit_reasons: dict[str, int] = field(default_factory=dict)
    long_count: int = 0
    short_count: int = 0


def _compute_metrics(results: list[TradeResult]) -> Metrics:
    if not results:
        return Metrics()

    wins = [r for r in results if r.net_pnl_pct > 0]
    losses = [r for r in results if r.net_pnl_pct <= 0]

    wr = len(wins) / len(results)
    win_pnls = [r.net_pnl_pct for r in wins]
    loss_pnls = [r.net_pnl_pct for r in losses]

    avg_w = statistics.mean(win_pnls) if win_pnls else 0.0
    avg_l = statistics.mean(loss_pnls) if loss_pnls else 0.0

    expectancy = wr * avg_w + (1 - wr) * avg_l

    gross_wins = sum(win_pnls)
    gross_losses = abs(sum(loss_pnls))
    pf = gross_wins / gross_losses if gross_losses > 0 else float("inf")

    # Cumulative equity
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in results:
        equity *= (1 + r.net_pnl_pct)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    total_ret = (equity - 1.0) * 100.0

    exit_dist: dict[str, int] = {}
    for r in results:
        exit_dist[r.exit_reason] = exit_dist.get(r.exit_reason, 0) + 1

    return Metrics(
        total_trades=len(results),
        win_rate=wr * 100.0,
        avg_win=avg_w * 100.0,
        avg_loss=avg_l * 100.0,
        expectancy_bps=expectancy * 10000.0,
        profit_factor=pf,
        total_return_pct=total_ret,
        max_drawdown_pct=max_dd * 100.0,
        avg_hold_candles=statistics.mean([r.hold_candles for r in results]),
        exit_reasons=exit_dist,
        long_count=sum(1 for r in results if r.side == "long"),
        short_count=sum(1 for r in results if r.side == "short"),
    )


# ─────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────


def _fmt_metrics_table(label: str, m: Metrics) -> str:
    lines = [
        f"| {label} | {m.total_trades} | {m.win_rate:.1f} | {m.avg_win:+.4f} | {m.avg_loss:+.4f} "
        f"| {m.expectancy_bps:+.3f} | {m.profit_factor:.3f} | {m.total_return_pct:+.2f} "
        f"| {m.max_drawdown_pct:.2f} |"
    ]
    return "\n".join(lines)


def _generate_report(
    baseline_results: list[TradeResult],
    trailing_results: dict[float, list[TradeResult]],
    all_signals_count: int,
) -> str:
    bl = _compute_metrics(baseline_results)

    lines: list[str] = []
    lines.append("# Bull 2024 Exit Validation — TITAN Trailing Stop")
    lines.append("")
    lines.append(f"Scenario: Bull Market 2024 (Jan-Dec)")
    lines.append(f"Assets: {', '.join(SYMBOLS)}")
    lines.append(f"Candle interval: 1h | Hold window: {HOLD_CANDLES} candles")
    lines.append(f"Signal generation: EMA(21/55) crossover + ADX>25")
    lines.append(f"Total signals generated: {all_signals_count}")
    lines.append(f"Stop-loss: {STOP_LOSS_PCT*100:.1f}% | Leverage: {LEVERAGE:.0f}x")
    lines.append(f"Date: 2026-03-02")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Phase 1: Baseline vs Best Trail
    lines.append("## Phase 1: Baseline (SL-only) vs Trailing Configs")
    lines.append("")
    lines.append("| Config | Trades | WR% | Avg Win% | Avg Loss% | E(bps) | PF | Return% | Max DD% |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    lines.append(_fmt_metrics_table("**Baseline (SL+time)**", bl))

    for trail_pct in sorted(trailing_results.keys()):
        tl = _compute_metrics(trailing_results[trail_pct])
        label = f"Trail {trail_pct*100:.1f}%"
        lines.append(_fmt_metrics_table(label, tl))

    lines.append("")

    # Exit reason distribution
    lines.append("### Exit Reason Distribution")
    lines.append("")
    lines.append("| Exit Reason | Baseline | " + " | ".join(
        f"Trail {t*100:.1f}%" for t in sorted(trailing_results.keys())
    ) + " |")
    lines.append("| --- | --- |" + " --- |" * len(trailing_results))

    all_reasons = set(bl.exit_reasons.keys())
    for tr in trailing_results.values():
        tm = _compute_metrics(tr)
        all_reasons |= set(tm.exit_reasons.keys())

    for reason in sorted(all_reasons):
        row = f"| {reason} | {bl.exit_reasons.get(reason, 0)}"
        for trail_pct in sorted(trailing_results.keys()):
            tm = _compute_metrics(trailing_results[trail_pct])
            row += f" | {tm.exit_reasons.get(reason, 0)}"
        row += " |"
        lines.append(row)

    lines.append("")

    # Long vs Short breakdown
    lines.append("### Long vs Short Breakdown")
    lines.append("")
    lines.append(f"**Baseline**: {bl.long_count} long, {bl.short_count} short")

    for trail_pct in sorted(trailing_results.keys()):
        tl = _compute_metrics(trailing_results[trail_pct])
        lines.append(f"**Trail {trail_pct*100:.1f}%**: {tl.long_count} long, {tl.short_count} short")

    lines.append("")

    # Side-specific metrics for baseline and best trail
    lines.append("### Side-Specific Metrics (Baseline)")
    lines.append("")
    bl_long = _compute_metrics([r for r in baseline_results if r.side == "long"])
    bl_short = _compute_metrics([r for r in baseline_results if r.side == "short"])
    lines.append("| Side | Trades | WR% | E(bps) | Return% |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append(f"| LONG | {bl_long.total_trades} | {bl_long.win_rate:.1f} | {bl_long.expectancy_bps:+.3f} | {bl_long.total_return_pct:+.2f} |")
    lines.append(f"| SHORT | {bl_short.total_trades} | {bl_short.win_rate:.1f} | {bl_short.expectancy_bps:+.3f} | {bl_short.total_return_pct:+.2f} |")
    lines.append("")

    # Trailing wins analysis
    lines.append("## Phase 2: Trailing Stop Winner/Loser Analysis")
    lines.append("")
    for trail_pct in sorted(trailing_results.keys()):
        tr_list = trailing_results[trail_pct]
        trailing_hits = [r for r in tr_list if r.exit_reason == REASON_TRAILING_STOP]
        if trailing_hits:
            t_wins = sum(1 for r in trailing_hits if r.net_pnl_pct > 0)
            t_losses = len(trailing_hits) - t_wins
            t_wr = t_wins / len(trailing_hits) * 100 if trailing_hits else 0
            lines.append(f"**Trail {trail_pct*100:.1f}%**: {len(trailing_hits)} trailing exits — "
                         f"{t_wins} winners ({t_wr:.1f}%), {t_losses} losers ({100-t_wr:.1f}%)")
        else:
            lines.append(f"**Trail {trail_pct*100:.1f}%**: 0 trailing exits")

    lines.append("")

    # Verdict
    lines.append("---")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")

    # Compare best trailing to baseline
    best_trail = None
    best_e = bl.expectancy_bps
    for trail_pct, tr_list in trailing_results.items():
        tm = _compute_metrics(tr_list)
        if tm.expectancy_bps > best_e:
            best_e = tm.expectancy_bps
            best_trail = trail_pct

    if best_trail is not None:
        tm = _compute_metrics(trailing_results[best_trail])
        delta_e = tm.expectancy_bps - bl.expectancy_bps
        lines.append(f"**Best trailing config**: Trail {best_trail*100:.1f}%")
        lines.append(f"- Expectancy delta: {delta_e:+.3f} bps vs baseline")
        lines.append(f"- Win rate delta: {tm.win_rate - bl.win_rate:+.1f}pp")
        lines.append(f"- Return delta: {tm.total_return_pct - bl.total_return_pct:+.2f}%")
        lines.append("")
        if delta_e > 0.5:
            lines.append("**RECOMMENDATION**: Enable trailing for TITAN trend-following trades.")
        elif delta_e > 0:
            lines.append("**RECOMMENDATION**: Marginal improvement. Consider enabling trailing for TITAN with monitoring.")
        else:
            lines.append("**RECOMMENDATION**: Trailing does not improve TITAN trend trades in bull 2024. Keep disabled.")
    else:
        lines.append("**No trailing configuration improves on baseline.**")
        lines.append("")
        lines.append("**RECOMMENDATION**: Keep `trailing_enabled=False` for TITAN. "
                     "Focus on entry quality and regime detection instead.")

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Bull 2024 Exit Validation — TITAN Trailing Stop")
    print("=" * 60)

    # Load candle data
    candles_by_symbol: dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        df = _load_candles(sym)
        if not df.empty:
            candles_by_symbol[sym] = df
            print(f"  Loaded {sym}: {len(df)} candles ({df['timestamp'].min()} -> {df['timestamp'].max()})")
        else:
            print(f"  [WARN] No data for {sym}")

    if not candles_by_symbol:
        print("[ERROR] No candle data loaded. Aborting.")
        return

    # Generate signals
    all_signals: list[dict] = []
    for sym, df in candles_by_symbol.items():
        signals = _generate_trend_signals(df, sym)
        all_signals.extend(signals)
        print(f"  {sym}: {len(signals)} trend signals generated")

    all_signals.sort(key=lambda s: s["timestamp"])
    print(f"\n  Total signals: {len(all_signals)}")

    if not all_signals:
        print("[ERROR] No signals generated. Aborting.")
        return

    # Phase 1: Baseline evaluation
    print("\n--- Phase 1: Baseline (SL-only) ---")
    baseline_results: list[TradeResult] = []
    for sig in all_signals:
        df = candles_by_symbol[sig["symbol"]]
        tr = _evaluate_signal(sig, df, TITAN_BASELINE)
        if tr is not None:
            baseline_results.append(tr)

    bl = _compute_metrics(baseline_results)
    print(f"  Trades: {bl.total_trades} | WR: {bl.win_rate:.1f}% | E: {bl.expectancy_bps:+.3f}bps | "
          f"PF: {bl.profit_factor:.3f} | Return: {bl.total_return_pct:+.2f}%")
    print(f"  Exits: {bl.exit_reasons}")

    # Phase 2: Trail sweep
    print("\n--- Phase 2: Trail Parameter Sweep ---")
    trailing_results: dict[float, list[TradeResult]] = {}

    for trail_pct in TRAIL_PCT_GRID:
        config = EngineExitConfig(
            trailing_enabled=True,
            trail_pct=trail_pct,
            be_lock_enabled=False,
            max_hold_candles=HOLD_CANDLES,
        )
        results: list[TradeResult] = []
        for sig in all_signals:
            df = candles_by_symbol[sig["symbol"]]
            tr = _evaluate_signal(sig, df, config)
            if tr is not None:
                results.append(tr)

        trailing_results[trail_pct] = results
        tm = _compute_metrics(results)
        print(f"  Trail {trail_pct*100:.1f}%: trades={tm.total_trades} WR={tm.win_rate:.1f}% "
              f"E={tm.expectancy_bps:+.3f}bps PF={tm.profit_factor:.3f} Ret={tm.total_return_pct:+.2f}%")

    # Also test with BE lock
    print("\n--- Phase 2b: Trail + BE Lock ---")
    for trail_pct in [0.01, 0.015]:
        config = EngineExitConfig(
            trailing_enabled=True,
            trail_pct=trail_pct,
            be_lock_enabled=True,
            be_trigger_atr_mult=1.5,
            be_buffer_pct=0.001,
            max_hold_candles=HOLD_CANDLES,
        )
        results = []
        for sig in all_signals:
            df = candles_by_symbol[sig["symbol"]]
            tr = _evaluate_signal(sig, df, config)
            if tr is not None:
                results.append(tr)

        key = trail_pct + 0.0001  # slight offset to distinguish in results
        trailing_results[key] = results
        tm = _compute_metrics(results)
        print(f"  Trail {trail_pct*100:.1f}%+BE: trades={tm.total_trades} WR={tm.win_rate:.1f}% "
              f"E={tm.expectancy_bps:+.3f}bps PF={tm.profit_factor:.3f}")

    # Generate report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = _generate_report(baseline_results, trailing_results, len(all_signals))
    report_path = OUTPUT_DIR / "BULL_2024_EXIT_VALIDATION.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n  Report written to: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
