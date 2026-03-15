"""Per-symbol / per-engine / per-regime breakdown from WAR backtest SQLite DBs.

Usage:
    python Scripts/experiment_breakdown.py <run_dir> [--label LABEL]

Example:
    python Scripts/experiment_breakdown.py runs/war_backtest_lab/experiment_baseline/bull_2024__orion_on --label baseline
"""

import argparse
import os
import sqlite3
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def load_trades(run_dir: Path) -> list[dict]:
    """Load all closed trades from monthly SQLite DBs."""
    trades = []
    db_paths = sorted(run_dir.glob("*/war_backtest_lab_v25.db"))
    if not db_paths:
        print(f"  No DBs found in {run_dir}")
        return trades

    for db_path in db_paths:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT symbol, side, engine, net_pnl_pct, regime_at_entry, leverage "
                "FROM trades WHERE exit_time IS NOT NULL"
            ).fetchall()
            trades.extend([dict(r) for r in rows])
        except Exception as e:
            print(f"  Error reading {db_path}: {e}")
        finally:
            conn.close()
    return trades


def compute_stats(trades: list[dict]) -> dict:
    """Compute summary stats from a list of trade dicts."""
    if not trades:
        return {"trades": 0, "wr": 0, "pf": 0, "e_bps": 0, "total_ret": 0}

    n = len(trades)
    wins = [t for t in trades if t["net_pnl_pct"] > 0]
    losses = [t for t in trades if t["net_pnl_pct"] <= 0]
    wr = len(wins) / n if n > 0 else 0
    gross_profit = sum(t["net_pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["net_pnl_pct"] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    total_ret = sum(t["net_pnl_pct"] for t in trades)
    e_bps = (total_ret / n) * 10000 if n > 0 else 0

    return {
        "trades": n,
        "wr": wr,
        "pf": round(pf, 2),
        "e_bps": round(e_bps, 1),
        "total_ret": round(total_ret * 100, 2),
    }


def print_section(title: str, trades: list[dict], group_key: str):
    """Print breakdown by group_key."""
    groups: dict[str, list[dict]] = {}
    for t in trades:
        key = t.get(group_key, "UNKNOWN")
        groups.setdefault(key, []).append(t)

    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")
    print(f"  {'Group':<15} {'Trades':>7} {'WR%':>7} {'PF':>7} {'E(bps)':>8} {'TotRet%':>9}")
    print(f"  {'-' * 53}")

    for key in sorted(groups.keys()):
        s = compute_stats(groups[key])
        print(
            f"  {key:<15} {s['trades']:>7} {s['wr']*100:>6.1f}% {s['pf']:>7.2f} {s['e_bps']:>8.1f} {s['total_ret']:>8.2f}%"
        )


def print_crosstab(trades: list[dict], row_key: str, col_key: str):
    """Print crosstab of row_key x col_key."""
    # Collect unique values
    row_vals = sorted(set(t.get(row_key, "?") for t in trades))
    col_vals = sorted(set(t.get(col_key, "?") for t in trades))

    print(f"\n{'-' * 60}")
    print(f"  Crosstab: {row_key} x {col_key}")
    print(f"{'-' * 60}")

    header = f"  {'':>15}"
    for cv in col_vals:
        header += f" {cv:>18}"
    print(header)
    print(f"  {'-' * (15 + 19 * len(col_vals))}")

    for rv in row_vals:
        line = f"  {rv:>15}"
        for cv in col_vals:
            subset = [t for t in trades if t.get(row_key) == rv and t.get(col_key) == cv]
            s = compute_stats(subset)
            if s["trades"] > 0:
                cell = f"{s['trades']}t {s['wr']*100:.0f}% {s['e_bps']:.0f}b"
            else:
                cell = "-"
            line += f" {cell:>18}"
        print(line)


def main():
    parser = argparse.ArgumentParser(description="Experiment breakdown analyzer")
    parser.add_argument("run_dir", type=str, help="Path to run directory (e.g. runs/.../bull_2024__orion_on)")
    parser.add_argument("--label", type=str, default="experiment", help="Label for this run")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    print(f"\n{'=' * 60}")
    print(f"  EXPERIMENT BREAKDOWN: {args.label}")
    print(f"  Source: {run_dir}")
    print(f"{'=' * 60}")

    trades = load_trades(run_dir)
    if not trades:
        print("  No trades found!")
        return

    # Overall
    overall = compute_stats(trades)
    print(f"\n  OVERALL: {overall['trades']} trades, WR={overall['wr']*100:.1f}%, "
          f"PF={overall['pf']}, E={overall['e_bps']}bps, TotRet={overall['total_ret']}%")

    # Per-symbol
    print_section("BY SYMBOL", trades, "symbol")

    # Per-side
    print_section("BY SIDE", trades, "side")

    # Per-engine
    print_section("BY ENGINE", trades, "engine")

    # Per-regime
    print_section("BY REGIME", trades, "regime_at_entry")

    # Crosstab: symbol x side
    print_crosstab(trades, "symbol", "side")

    # Crosstab: symbol x engine
    print_crosstab(trades, "symbol", "engine")

    # Crosstab: engine x regime
    print_crosstab(trades, "engine", "regime_at_entry")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
