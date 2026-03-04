#!/usr/bin/env python3
"""Run multi-scenario backtests and produce a unified analysis report.

Scenarios:
  1. COVID crash (2020-02 to 2020-05) — extreme bear panic
  2. Luna/3AC crash (2022-05 to 2022-07) — cascading liquidation
  3. Bear market (2022-01 to 2022-12) — prolonged downtrend
  4. Bull market (2024-01 to 2024-12) — strong uptrend
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import numpy as np

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.data.replay_loader import ReplayLoader


# ── Scenario Definitions ────────────────────────────────────────────
@dataclass
class Scenario:
    name: str
    start: str
    end: str
    symbols: list[str]
    risk_profile: str
    description: str
    hold_hours: int = 4


SCENARIOS = [
    Scenario(
        name="covid_crash_2020",
        start="2020-02-15",
        end="2020-05-31",
        symbols=["BTCUSDT", "ETHUSDT"],
        risk_profile="strict",
        description="COVID-19 market crash — BTC dropped from $10K to $3.8K",
        hold_hours=4,
    ),
    Scenario(
        name="luna_crash_2022",
        start="2022-05-01",
        end="2022-07-31",
        symbols=["BTCUSDT", "ETHUSDT"],
        risk_profile="strict",
        description="Luna/3AC collapse — BTC from $40K to $17K",
        hold_hours=4,
    ),
    Scenario(
        name="bear_2022",
        start="2022-01-01",
        end="2022-12-31",
        symbols=["BTCUSDT", "ETHUSDT"],
        risk_profile="normal",
        description="Full 2022 bear market — extended downtrend",
        hold_hours=6,
    ),
    Scenario(
        name="bull_2024",
        start="2024-01-01",
        end="2024-12-31",
        symbols=["BTCUSDT", "ETHUSDT"],
        risk_profile="relaxed",
        description="2024 bull market — BTC from $42K to $100K+",
        hold_hours=6,
    ),
]


def _load_price_map(symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """Load 1h OHLCV for all symbols as DataFrames indexed by timestamp."""
    loader = ReplayLoader(root="data/binance")
    price_map = {}
    for sym in symbols:
        try:
            df = loader.load_ohlcv(sym, "1h", start, end, verify=False)
            df = df.set_index("timestamp").sort_index()
            price_map[sym] = df
        except FileNotFoundError:
            print(f"  [warn] No data for {sym}, skipping")
    return price_map


def run_scenario(scenario: Scenario, output_root: Path) -> dict:
    """Run a single backtest scenario via ArgusPipeline with trade simulation."""
    from src.main import ArgusPipeline
    from src.v25.bootstrap import run_v25_migrations

    run_dir = output_root / scenario.name
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "argus_v25.db"

    conn = run_v25_migrations(str(db_path))

    start_dt = datetime.strptime(scenario.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(scenario.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    total_hours = int((end_dt - start_dt).total_seconds() / 3600)
    max_cycles = min(total_hours, 8760)

    print(f"\n{'='*60}")
    print(f"  Scenario: {scenario.name}")
    print(f"  {scenario.description}")
    print(f"  Period: {scenario.start} -> {scenario.end} ({total_hours}h, {max_cycles} cycles)")
    print(f"  Symbols: {', '.join(scenario.symbols)}")
    print(f"  Risk: {scenario.risk_profile} | Hold: {scenario.hold_hours}h")
    print(f"{'='*60}")

    # Preload price data for trade simulation
    price_map = _load_price_map(scenario.symbols, scenario.start, scenario.end)

    replay_now = pd.Timestamp(start_dt)
    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        v25_conn=conn,
        ohlcv_limit=260,
        replay_now=replay_now,
        risk_profile=scenario.risk_profile,
        allow_crisis=True,
    )
    pipeline._primary_tf = "1h"
    pipeline.ctx.symbols = {"crypto": scenario.symbols}

    all_outputs = []
    regime_counts: dict[str, int] = {}
    for cycle in range(1, max_cycles + 1):
        cycle_now = start_dt + timedelta(hours=cycle - 1)
        pipeline.replay_now = pd.Timestamp(cycle_now)

        try:
            outputs = pipeline.run_once(now=cycle_now)
            for o in outputs:
                o["_cycle_time"] = cycle_now
                # Track regime distribution from features snapshot
                _fs = o.get("gate_results", {}).get("features_snapshot", {})
                _reg = _fs.get("regime", "UNKNOWN")
                regime_counts[_reg] = regime_counts.get(_reg, 0) + 1
            all_outputs.extend(outputs)
        except Exception as exc:
            if cycle <= 3:
                print(f"  [cycle {cycle}] error: {exc}")
            continue

        if cycle % 500 == 0 or cycle == max_cycles:
            executed = sum(1 for o in all_outputs if o.get("status") == "executed")
            rejected = sum(1 for o in all_outputs if o.get("status") == "rejected")
            print(f"  [cycle {cycle}/{max_cycles}] executed={executed} rejected={rejected}")

    # Print regime distribution
    total_regime = sum(regime_counts.values()) or 1
    regime_str = " | ".join(f"{k}: {v} ({100*v/total_regime:.0f}%)" for k, v in sorted(regime_counts.items()))
    print(f"  Regime distribution: {regime_str}")

    conn.close()

    # Simulate trades from executed signals
    trades = _simulate_trades(all_outputs, price_map, scenario.hold_hours)
    result = _analyze(scenario, all_outputs, trades)

    result_path = run_dir / "analysis.json"
    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    # Save trade detail CSV
    if trades:
        trades_df = pd.DataFrame(trades)
        trades_df.to_csv(run_dir / "trades.csv", index=False)

    print(f"  Trades: {len(trades)} | Results saved to {result_path}")
    return result


def _simulate_trades(
    outputs: list[dict], price_map: dict[str, pd.DataFrame], hold_hours: int
) -> list[dict]:
    """Simulate trades with ATR-based stop-loss and trailing take-profit.

    For each executed signal:
    1. Entry at signal candle close
    2. Walk forward candle by candle up to max hold_hours
    3. Exit if stop-loss hit (2x ATR from entry) or take-profit trail triggered
    4. Otherwise exit at hold expiry
    """
    fee_pct = 0.075  # 0.075% per side (taker)
    trades = []

    for o in outputs:
        if o.get("status") != "executed":
            continue

        symbol = o.get("symbol", "UNKNOWN")
        if symbol not in price_map:
            continue

        entry_time = o["_cycle_time"]
        entry_ts = pd.Timestamp(entry_time).tz_localize("UTC") if pd.Timestamp(entry_time).tzinfo is None else pd.Timestamp(entry_time).tz_convert("UTC")

        df = price_map[symbol]
        entry_idx = df.index.searchsorted(entry_ts)
        if entry_idx >= len(df):
            continue

        entry_price = float(df.iloc[entry_idx]["close"])
        action = str(o.get("action", "long")).lower()
        bias = action if action in ("long", "short") else "long"

        engine = str(o.get("engine", "UNKNOWN"))
        gate_results = o.get("gate_results", {})
        features = gate_results.get("features_snapshot", {})
        regime = features.get("regime", "UNKNOWN")

        # Dynamic hold: trending regime gets longer holds, ranging shorter
        if regime == "TRENDING":
            effective_hold = min(hold_hours * 2, 12)
        elif regime in ("VOLATILE", "CRISIS"):
            effective_hold = max(hold_hours // 2, 2)
        else:
            effective_hold = hold_hours

        # Compute ATR for stop-loss (use last 14 candles before entry)
        atr_start = max(0, entry_idx - 14)
        atr_slice = df.iloc[atr_start:entry_idx]
        if len(atr_slice) >= 2:
            highs = atr_slice["high"].values
            lows = atr_slice["low"].values
            closes = atr_slice["close"].values
            tr_vals = []
            for i in range(1, len(highs)):
                tr = max(
                    float(highs[i]) - float(lows[i]),
                    abs(float(highs[i]) - float(closes[i-1])),
                    abs(float(lows[i]) - float(closes[i-1])),
                )
                tr_vals.append(tr)
            atr = np.mean(tr_vals) if tr_vals else entry_price * 0.02
        else:
            atr = entry_price * 0.02  # fallback: 2%

        # Regime-aware ATR multipliers for stop and trailing activation
        _regime_sl_mult = {
            "TRENDING": 2.2,   # wider: trend needs room to develop
            "RANGING": 1.4,    # tighter: mean-reversion expects quick return
            "VOLATILE": 1.8,   # moderate
            "CRISIS": 1.2,     # tight: preserve capital
        }.get(regime, 1.8)
        _regime_tp_mult = {
            "TRENDING": 3.0,   # trend: let it run
            "RANGING": 1.5,    # ranging: closer target
            "VOLATILE": 2.0,
        }.get(regime, 2.0)
        _regime_trail_mult = {
            "TRENDING": 1.5,   # wider trail in trending
            "RANGING": 0.8,    # tighter in ranging
            "VOLATILE": 1.2,
        }.get(regime, 1.2)
        stop_distance = atr * _regime_sl_mult
        tp_distance = atr * _regime_tp_mult

        if bias == "long":
            stop_price = entry_price - stop_distance
            tp_price = entry_price + tp_distance
        else:
            stop_price = entry_price + stop_distance
            tp_price = entry_price - tp_distance

        # Walk forward candle-by-candle
        exit_price = entry_price
        exit_reason = "hold_expiry"
        exit_idx = entry_idx
        best_price = entry_price  # For trailing stop after TP1
        _half_hold = effective_hold // 2  # Time-based stop tightening point
        _partial_pnl = 0.0  # Accumulated partial TP PnL
        _partial_taken = False  # Whether 30% partial TP at 1R has been taken

        max_exit_idx = min(entry_idx + effective_hold, len(df) - 1)
        for ci in range(entry_idx + 1, max_exit_idx + 1):
            candle_high = float(df.iloc[ci]["high"])
            candle_low = float(df.iloc[ci]["low"])
            candle_close = float(df.iloc[ci]["close"])
            elapsed = ci - entry_idx

            # Time-based stop tightening: after 50% of hold, tighten stop
            # to 1.5 ATR from entry (if not already tighter)
            if elapsed >= _half_hold:
                if bias == "long":
                    time_tight_stop = entry_price - atr * 1.5
                    stop_price = max(stop_price, time_tight_stop)
                else:
                    time_tight_stop = entry_price + atr * 1.5
                    stop_price = min(stop_price, time_tight_stop)

            if bias == "long":
                # Check stop-loss
                if candle_low <= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                    exit_idx = ci
                    break
                # Partial TP at 1R: take 30% profit, move stop to breakeven
                if not _partial_taken and candle_high >= entry_price + atr:
                    _partial_taken = True
                    _partial_pnl = (atr / entry_price) * 100.0 * 0.30  # 30% of 1R
                    stop_price = max(stop_price, entry_price)  # breakeven on remainder
                # Track best price for trailing
                if candle_high > best_price:
                    best_price = candle_high
                    # Move stop to breakeven + cushion once 1R profit reached
                    if best_price >= entry_price + atr:
                        stop_price = max(stop_price, entry_price + atr * 0.3)
                    # Trailing stop at regime-aware ATR distance from best
                    if best_price >= tp_price:
                        trail_stop = best_price - atr * _regime_trail_mult
                        stop_price = max(stop_price, trail_stop)
                        exit_reason = "trailing_stop"
                # Check if trailing stop hit on close
                if candle_close <= stop_price and exit_reason == "trailing_stop":
                    exit_price = candle_close
                    exit_idx = ci
                    break
            else:  # short
                # Check stop-loss
                if candle_high >= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                    exit_idx = ci
                    break
                # Partial TP at 1R: take 30% profit, move stop to breakeven
                if not _partial_taken and candle_low <= entry_price - atr:
                    _partial_taken = True
                    _partial_pnl = (atr / entry_price) * 100.0 * 0.30  # 30% of 1R
                    stop_price = min(stop_price, entry_price)  # breakeven on remainder
                # Track best (lowest) price
                if candle_low < best_price:
                    best_price = candle_low
                    if best_price <= entry_price - atr:
                        stop_price = min(stop_price, entry_price - atr * 0.3)
                    if best_price <= tp_price:
                        trail_stop = best_price + atr * _regime_trail_mult
                        stop_price = min(stop_price, trail_stop)
                        exit_reason = "trailing_stop"
                if candle_close >= stop_price and exit_reason == "trailing_stop":
                    exit_price = candle_close
                    exit_idx = ci
                    break

            exit_price = candle_close
            exit_idx = ci

        # Compute PnL (with partial TP adjustment)
        if bias == "long":
            remainder_pnl = (exit_price / entry_price - 1) * 100
        else:
            remainder_pnl = (1 - exit_price / entry_price) * 100

        if _partial_taken:
            # 30% exited at 1R (captured in _partial_pnl), 70% at final exit
            gross_pnl_pct = _partial_pnl + remainder_pnl * 0.70
        else:
            gross_pnl_pct = remainder_pnl

        net_pnl_pct = gross_pnl_pct - (fee_pct * 2)  # round-trip fees

        actual_hold = int(exit_idx - entry_idx)
        exit_time = entry_time + timedelta(hours=actual_hold)

        trades.append({
            "symbol": symbol,
            "side": bias,
            "engine": engine,
            "regime_at_entry": regime,
            "confidence": float(o.get("confidence", 0)),
            "entry_time": str(entry_time),
            "exit_time": str(exit_time),
            "entry_price": entry_price,
            "exit_price": round(exit_price, 8),
            "gross_pnl_pct": round(gross_pnl_pct, 4),
            "net_pnl_pct": round(net_pnl_pct, 4),
            "hold_hours": actual_hold,
            "max_hold_hours": effective_hold,
            "exit_reason": exit_reason,
            "atr_at_entry": round(atr, 4),
        })

    return trades


def _analyze(scenario: Scenario, outputs: list, trades: list) -> dict:
    """Analyze trade results."""
    total_decisions = len(outputs)
    executed = sum(1 for o in outputs if o.get("status") == "executed")
    rejected = sum(1 for o in outputs if o.get("status") == "rejected")

    if not trades:
        # Rejection analysis
        rejection_reasons = {}
        for o in outputs:
            if o.get("status") == "rejected":
                reason = str(o.get("reason", "unknown"))
                key = reason.split("(")[0].strip().rstrip("_")
                rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
        top_rejections = dict(sorted(rejection_reasons.items(), key=lambda x: -x[1])[:10])

        return {
            "scenario": scenario.name,
            "description": scenario.description,
            "period": f"{scenario.start} to {scenario.end}",
            "total_decisions": total_decisions,
            "executed": executed,
            "rejected": rejected,
            "closed_trades": 0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "top_rejection_reasons": top_rejections,
            "message": "No closed trades — all signals rejected or no price data",
        }

    tdf = pd.DataFrame(trades)
    total_trades = len(tdf)
    wins = (tdf["net_pnl_pct"] > 0).sum()
    losses = (tdf["net_pnl_pct"] <= 0).sum()
    win_rate = wins / total_trades

    total_return = tdf["net_pnl_pct"].sum()
    avg_return = tdf["net_pnl_pct"].mean()
    median_return = tdf["net_pnl_pct"].median()

    # Equity curve & drawdown
    equity = (1 + tdf["net_pnl_pct"] / 100).cumprod()
    rolling_max = equity.cummax()
    drawdown = (equity / rolling_max - 1) * 100
    max_drawdown = drawdown.min()

    # Profit factor
    gross_profit = tdf[tdf["net_pnl_pct"] > 0]["net_pnl_pct"].sum()
    gross_loss = abs(tdf[tdf["net_pnl_pct"] < 0]["net_pnl_pct"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0.001 else float("inf")

    # Long vs Short
    def _side_stats(df):
        if df.empty:
            return {"count": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0}
        return {
            "count": len(df),
            "win_rate": round(float((df["net_pnl_pct"] > 0).mean()), 4),
            "avg_pnl": round(float(df["net_pnl_pct"].mean()), 4),
            "total_pnl": round(float(df["net_pnl_pct"].sum()), 4),
            "max_win": round(float(df["net_pnl_pct"].max()), 4),
            "max_loss": round(float(df["net_pnl_pct"].min()), 4),
        }

    long_df = tdf[tdf["side"] == "long"]
    short_df = tdf[tdf["side"] == "short"]

    # Engine breakdown
    engine_stats = {}
    for eng in tdf["engine"].unique():
        eng_df = tdf[tdf["engine"] == eng]
        engine_stats[eng] = _side_stats(eng_df)

    # Regime breakdown
    regime_stats = {}
    for reg in tdf["regime_at_entry"].unique():
        reg_df = tdf[tdf["regime_at_entry"] == reg]
        regime_stats[str(reg)] = _side_stats(reg_df)

    # Symbol breakdown
    symbol_stats = {}
    for sym in tdf["symbol"].unique():
        sym_df = tdf[tdf["symbol"] == sym]
        symbol_stats[sym] = _side_stats(sym_df)

    # Rejection analysis
    rejection_reasons = {}
    for o in outputs:
        if o.get("status") == "rejected":
            reason = str(o.get("reason", "unknown"))
            key = reason.split("(")[0].strip().rstrip("_")
            rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
    top_rejections = dict(sorted(rejection_reasons.items(), key=lambda x: -x[1])[:10])

    # Exit reason breakdown
    exit_reason_stats = {}
    if "exit_reason" in tdf.columns:
        for reason in tdf["exit_reason"].unique():
            r_df = tdf[tdf["exit_reason"] == reason]
            exit_reason_stats[str(reason)] = {
                "count": len(r_df),
                "win_rate": round(float((r_df["net_pnl_pct"] > 0).mean()), 4),
                "avg_pnl": round(float(r_df["net_pnl_pct"].mean()), 4),
                "total_pnl": round(float(r_df["net_pnl_pct"].sum()), 4),
            }

    # Average hold hours
    avg_hold = round(float(tdf["hold_hours"].mean()), 1) if "hold_hours" in tdf.columns else hold_hours

    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "period": f"{scenario.start} to {scenario.end}",
        "total_decisions": total_decisions,
        "executed": executed,
        "rejected": rejected,
        "closed_trades": total_trades,
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": round(float(win_rate), 4),
        "total_return_pct": round(float(total_return), 4),
        "avg_return_pct": round(float(avg_return), 4),
        "median_return_pct": round(float(median_return), 4),
        "max_win_pct": round(float(tdf["net_pnl_pct"].max()), 4),
        "max_loss_pct": round(float(tdf["net_pnl_pct"].min()), 4),
        "max_drawdown_pct": round(float(max_drawdown), 4),
        "profit_factor": round(float(profit_factor), 4),
        "avg_hold_hours": avg_hold,
        "long_stats": _side_stats(long_df),
        "short_stats": _side_stats(short_df),
        "engine_breakdown": engine_stats,
        "regime_breakdown": regime_stats,
        "symbol_breakdown": symbol_stats,
        "exit_reason_breakdown": exit_reason_stats,
        "top_rejection_reasons": top_rejections,
    }


def print_report(results: list[dict]) -> None:
    """Print a unified comparison report."""
    print(f"\n\n{'='*80}")
    print("  ARGUS MULTI-SCENARIO BACKTEST ANALYSIS")
    print(f"{'='*80}\n")

    for r in results:
        print(f"\n--- {r['scenario']} ({r['period']}) ---")
        print(f"  {r.get('description', '')}")
        print(f"  Decisions: {r.get('total_decisions',0)} | Executed: {r.get('executed',0)} | Rejected: {r.get('rejected',0)}")

        if r.get("closed_trades", 0) == 0:
            if r.get("top_rejection_reasons"):
                print(f"  ** No trades executed. Top rejections: **")
                for reason, count in list(r["top_rejection_reasons"].items())[:5]:
                    print(f"    {reason}: {count}")
            continue

        print(f"  Trades: {r['closed_trades']} | Win Rate: {r['win_rate']:.1%} | PF: {r['profit_factor']:.2f}")
        print(f"  Total Return: {r['total_return_pct']:+.2f}% | Avg: {r['avg_return_pct']:+.3f}% | Median: {r['median_return_pct']:+.3f}%")
        print(f"  Max DD: {r['max_drawdown_pct']:.2f}% | Max Win: {r['max_win_pct']:+.2f}% | Max Loss: {r['max_loss_pct']:+.2f}%")

        ls = r.get("long_stats", {})
        ss = r.get("short_stats", {})
        print(f"\n  LONG:  {ls.get('count',0):>4} trades | WR {ls.get('win_rate',0):.1%} | Avg {ls.get('avg_pnl',0):+.3f}% | Total {ls.get('total_pnl',0):+.2f}%")
        print(f"  SHORT: {ss.get('count',0):>4} trades | WR {ss.get('win_rate',0):.1%} | Avg {ss.get('avg_pnl',0):+.3f}% | Total {ss.get('total_pnl',0):+.2f}%")

        if r.get("engine_breakdown"):
            print(f"\n  Engine Performance:")
            for eng, s in sorted(r["engine_breakdown"].items(), key=lambda x: -x[1].get("total_pnl", 0)):
                print(f"    {eng:<12} {s['count']:>4} trades | WR {s['win_rate']:.1%} | Total {s['total_pnl']:+.2f}%")

        if r.get("regime_breakdown"):
            print(f"\n  Regime Performance:")
            for reg, s in sorted(r["regime_breakdown"].items(), key=lambda x: -x[1].get("total_pnl", 0)):
                print(f"    {reg:<16} {s['count']:>4} trades | WR {s['win_rate']:.1%} | Total {s['total_pnl']:+.2f}%")

        if r.get("exit_reason_breakdown"):
            print(f"\n  Exit Reasons:")
            for reason, s in sorted(r["exit_reason_breakdown"].items(), key=lambda x: -x[1].get("count", 0)):
                print(f"    {reason:<16} {s['count']:>4} trades | WR {s['win_rate']:.1%} | Avg {s['avg_pnl']:+.3f}% | Total {s['total_pnl']:+.2f}%")

        if r.get("avg_hold_hours"):
            print(f"\n  Avg Hold: {r['avg_hold_hours']:.1f}h")

        if r.get("top_rejection_reasons"):
            print(f"\n  Top Rejection Reasons:")
            for reason, count in list(r["top_rejection_reasons"].items())[:5]:
                pct = count / max(r.get("total_decisions", 1), 1) * 100
                print(f"    {reason}: {count} ({pct:.1f}%)")

    # Cross-scenario comparison
    print(f"\n\n{'='*80}")
    print("  CROSS-SCENARIO COMPARISON")
    print(f"{'='*80}")
    print(f"  {'Scenario':<22} {'Trades':>6} {'WR':>6} {'Return':>9} {'MaxDD':>8} {'PF':>6} {'Long$':>9} {'Short$':>9} {'Exec%':>7}")
    print(f"  {'-'*22} {'-'*6} {'-'*6} {'-'*9} {'-'*8} {'-'*6} {'-'*9} {'-'*9} {'-'*7}")
    for r in results:
        ls = r.get("long_stats", {})
        ss = r.get("short_stats", {})
        tc = r.get("closed_trades", 0)
        exec_rate = r.get("executed", 0) / max(r.get("total_decisions", 1), 1) * 100
        print(
            f"  {r['scenario']:<22} {tc:>6} "
            f"{r.get('win_rate',0):>5.1%} {r.get('total_return_pct',0):>+8.2f}% "
            f"{r.get('max_drawdown_pct',0):>+7.2f}% {r.get('profit_factor',0):>5.2f} "
            f"{ls.get('total_pnl',0):>+8.2f}% {ss.get('total_pnl',0):>+8.2f}% "
            f"{exec_rate:>6.1f}%"
        )


def main():
    output_root = _ROOT / "runs" / "scenario_analysis"
    output_root.mkdir(parents=True, exist_ok=True)

    results = []
    for scenario in SCENARIOS:
        try:
            result = run_scenario(scenario, output_root)
            results.append(result)
        except Exception as exc:
            print(f"\n  ERROR in {scenario.name}: {exc}")
            import traceback
            traceback.print_exc()
            results.append({
                "scenario": scenario.name,
                "description": scenario.description,
                "period": f"{scenario.start} to {scenario.end}",
                "closed_trades": 0,
                "message": f"Error: {exc}",
            })

    print_report(results)

    combined_path = output_root / "combined_analysis.json"
    combined_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nFull analysis saved to: {combined_path}")


if __name__ == "__main__":
    main()
