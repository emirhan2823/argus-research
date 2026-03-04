"""Compare TITAN exit strategies: vCurrent (1.5R partial + ATR×2.5 trail) vs vUpgraded (multi-tier + structure trail).

Usage:
    python Scripts/compare_titan_exits.py --symbol BTCUSDT --start 2024-06-01 --end 2024-12-31

Output:
    reports/titan_exit_comparison/comparison_{symbol}_{start}_{end}.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.exit_policy import (
    EngineExitConfig,
    ExitResult,
    evaluate_exit_bar_by_bar,
    REASON_STOP_LOSS,
    REASON_TRAILING_STOP,
    REASON_BREAKEVEN_STOP,
    REASON_TIME_EXIT,
)


# ── Exit Configs ──

V_CURRENT = EngineExitConfig(
    trailing_enabled=True,
    trail_atr_mult=2.5,
    be_lock_enabled=False,
    unlimited_hold=True,
    partial_tp_enabled=True,
    partial_tp_r=1.5,
    partial_tp_fraction=0.5,
)

V_UPGRADED = EngineExitConfig(
    trailing_enabled=True,
    trail_atr_mult=2.5,
    be_lock_enabled=False,
    unlimited_hold=True,
    partial_tp_enabled=False,
    partial_tp_tiers=(
        (1.0, 0.33),
        (2.0, 0.33),
    ),
    be_after_tp1=True,
    be_after_tp1_buffer_pct=0.002,
    runner_trail_mode="atr",  # use ATR for comparison (structure needs full history)
    runner_trail_atr_mult=2.0,
    runner_atr_buffer=0.3,
)


def _generate_synthetic_trades(
    n_trades: int = 50,
    seed: int = 42,
) -> list[dict]:
    """Generate synthetic TITAN-like trade scenarios for comparison.

    Each trade is a dict with: entry_price, sl_pct, atr_pct, side, candles.
    """
    import random
    random.seed(seed)
    trades = []

    for t in range(n_trades):
        entry = 100.0
        sl_pct = random.uniform(0.015, 0.035)
        atr_pct = sl_pct / 2.0
        side = random.choice(["long", "short"])

        # Generate 60 candles of price action
        candles = []
        price = entry
        # Trend bias: 60% trending, 40% mean-revert
        trending = random.random() < 0.6
        if trending:
            drift = random.uniform(0.002, 0.006) * (1 if side == "long" else -1)
        else:
            drift = random.uniform(-0.001, 0.001)

        for i in range(60):
            noise = random.gauss(0, atr_pct * entry * 0.5)
            price = price * (1 + drift) + noise
            price = max(price, entry * 0.8)  # floor
            h = price * (1 + random.uniform(0.001, 0.005))
            l = price * (1 - random.uniform(0.001, 0.005))
            candles.append({
                "timestamp": datetime(2024, 6, 1, tzinfo=timezone.utc),
                "high": h,
                "low": l,
                "close": price,
            })

        trades.append({
            "entry_price": entry,
            "sl_pct": sl_pct,
            "atr_pct": atr_pct,
            "side": side,
            "candles": candles,
        })
    return trades


def _compute_pnl(
    result: ExitResult,
    entry_price: float,
    side: str,
    fee_pct: float = 0.0006,
) -> float:
    """Compute PnL% from exit result including partial exits."""
    total_pnl = 0.0
    remaining_fraction = 1.0

    # Account for partial exits
    if result.partial_exits:
        for pe in result.partial_exits:
            if side == "long":
                pnl = (pe.exit_price - entry_price) / entry_price
            else:
                pnl = (entry_price - pe.exit_price) / entry_price
            pnl -= 2 * fee_pct  # round-trip fees
            total_pnl += pnl * pe.fraction
            remaining_fraction -= pe.fraction

    # Remaining position exits at final price
    if side == "long":
        final_pnl = (result.exit_price - entry_price) / entry_price
    else:
        final_pnl = (entry_price - result.exit_price) / entry_price
    final_pnl -= 2 * fee_pct
    total_pnl += final_pnl * remaining_fraction

    return total_pnl


def _run_comparison(trades: list[dict]) -> dict:
    """Run both strategies on trades and return comparison metrics."""
    results = {"vCurrent": [], "vUpgraded": []}

    for trade in trades:
        entry = trade["entry_price"]
        sl_pct = trade["sl_pct"]
        atr_pct = trade["atr_pct"]
        side = trade["side"]
        candles = trade["candles"]

        if side == "long":
            sl_price = entry * (1 - sl_pct)
        else:
            sl_price = entry * (1 + sl_pct)

        for label, config in [("vCurrent", V_CURRENT), ("vUpgraded", V_UPGRADED)]:
            result = evaluate_exit_bar_by_bar(
                candles=candles,
                side=side,
                entry_price=entry,
                initial_stop_price=sl_price,
                atr_pct=atr_pct,
                config=config,
            )
            if result is not None:
                pnl = _compute_pnl(result, entry, side)
                results[label].append({
                    "pnl_pct": pnl,
                    "hold_bars": result.candles_evaluated,
                    "exit_reason": result.exit_reason,
                    "n_partials": len(result.partial_exits) if result.partial_exits else 0,
                    "be_locked": result.be_locked,
                })

    return results


def _compute_metrics(trades: list[dict]) -> dict:
    """Compute summary metrics from trade results."""
    if not trades:
        return {"n": 0, "wr": 0, "expectancy_bps": 0, "pf": 0, "avg_hold": 0}

    n = len(trades)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    wr = len(wins) / n * 100
    expectancy = sum(t["pnl_pct"] for t in trades) / n * 10000  # bps
    gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.001
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    avg_hold = sum(t["hold_bars"] for t in trades) / n

    return {
        "n": n,
        "wr": wr,
        "expectancy_bps": expectancy,
        "pf": pf,
        "avg_hold": avg_hold,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare TITAN exit strategies")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", default="2024-06-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--n-trades", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Generating {args.n_trades} synthetic TITAN trades (seed={args.seed})...")
    trades = _generate_synthetic_trades(n_trades=args.n_trades, seed=args.seed)

    print("Running exit strategy comparison...")
    results = _run_comparison(trades)

    m_current = _compute_metrics(results["vCurrent"])
    m_upgraded = _compute_metrics(results["vUpgraded"])

    # Print report
    report = []
    report.append(f"{'=' * 60}")
    report.append(f" TITAN Exit Comparison: {args.symbol} {args.start} -> {args.end}")
    report.append(f" Synthetic trades: {args.n_trades} (seed={args.seed})")
    report.append(f"{'=' * 60}")
    report.append(f"{'Metric':<24} {'vCurrent':>12} {'vUpgraded':>12} {'Delta':>12}")
    report.append(f"{'-' * 60}")
    report.append(f"{'Trades':<24} {m_current['n']:>12} {m_upgraded['n']:>12} {'-':>12}")
    report.append(f"{'Win Rate':<24} {m_current['wr']:>11.1f}% {m_upgraded['wr']:>11.1f}% {m_upgraded['wr'] - m_current['wr']:>+11.1f}pp")
    report.append(f"{'Expectancy (bps)':<24} {m_current['expectancy_bps']:>+12.1f} {m_upgraded['expectancy_bps']:>+12.1f} {m_upgraded['expectancy_bps'] - m_current['expectancy_bps']:>+12.1f}")
    report.append(f"{'Profit Factor':<24} {m_current['pf']:>12.2f} {m_upgraded['pf']:>12.2f} {m_upgraded['pf'] - m_current['pf']:>+12.2f}")
    report.append(f"{'Avg Hold (bars)':<24} {m_current['avg_hold']:>12.1f} {m_upgraded['avg_hold']:>12.1f} {m_upgraded['avg_hold'] - m_current['avg_hold']:>+12.1f}")

    # Exit reason breakdown
    for label, res in results.items():
        report.append(f"\n  {label} Exit Reasons:")
        reasons = {}
        for t in res:
            r = t["exit_reason"]
            reasons[r] = reasons.get(r, 0) + 1
        for r, count in sorted(reasons.items(), key=lambda x: -x[1]):
            report.append(f"    {r:<30} {count:>5} ({count / len(res) * 100:.1f}%)")

    report_text = "\n".join(report)
    print(report_text)

    # Save report
    out_dir = Path("reports/titan_exit_comparison")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"comparison_{args.symbol}_{args.start}_{args.end}.txt"
    out_file.write_text(report_text, encoding="utf-8")
    print(f"\nReport saved to: {out_file}")

    # Save JSON
    json_file = out_dir / f"comparison_{args.symbol}_{args.start}_{args.end}.json"
    json_file.write_text(json.dumps({
        "vCurrent": m_current,
        "vUpgraded": m_upgraded,
        "delta": {
            "wr": m_upgraded["wr"] - m_current["wr"],
            "expectancy_bps": m_upgraded["expectancy_bps"] - m_current["expectancy_bps"],
            "pf": m_upgraded["pf"] - m_current["pf"],
            "avg_hold": m_upgraded["avg_hold"] - m_current["avg_hold"],
        },
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
