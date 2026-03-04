"""TITAN v2 Validation — Quantitative analysis of trend following engine.

Runs BTC-only and multi-asset (BTC+ETH+SOL) backtest scenarios via
war_backtest_lab, then produces a structured validation report comparing
TITAN v2 metrics: PF, expectancy, trade count, WR, avg R multiple, MaxDD,
asset allocation distribution, TrendScore histogram, and partial TP hit rate.

Usage:
    python Scripts/validate_titan_v2.py [--scenario bull_2024|luna_crash_2022|bear_2022]
    python Scripts/validate_titan_v2.py --all

Output: reports/trend_v2_validation/
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.war_forward_report import (
    _as_float,
    _load_closed_trades,
    _load_decisions,
)

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────

REPORTS_DIR = PROJECT_ROOT / "reports" / "trend_v2_validation"

SCENARIO_CONFIGS: dict[str, dict[str, Any]] = {
    "bull_2024": {
        "start": "2024-01-01",
        "end": "2024-12-31",
        "assets_btc": ["BTCUSDT"],
        "assets_multi": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    },
    "luna_crash_2022": {
        "start": "2022-05-01",
        "end": "2022-07-31",
        "assets_btc": ["BTCUSDT"],
        "assets_multi": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    },
    "bear_2022": {
        "start": "2022-01-01",
        "end": "2022-12-31",
        "assets_btc": ["BTCUSDT"],
        "assets_multi": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    },
}


# ─────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────

@dataclass
class TradeMetrics:
    """Aggregated metrics for a set of trades."""
    scenario: str = ""
    variant: str = ""  # "btc_only" or "multi_asset"
    trade_count: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    avg_return: float = 0.0
    profit_factor: float = 0.0
    avg_r_multiple: float = 0.0
    max_drawdown: float = 0.0
    expectancy: float = 0.0
    titan_trades: int = 0
    titan_win_rate: float = 0.0
    titan_avg_return: float = 0.0
    titan_pf: float = 0.0
    partial_tp_hits: int = 0
    partial_tp_rate: float = 0.0
    long_count: int = 0
    short_count: int = 0
    avg_hold_minutes: float = 0.0
    regime_distribution: dict[str, int] = field(default_factory=dict)
    asset_distribution: dict[str, int] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────
# Metric computation
# ─────────────────────────────────────────────────────────────────────

def compute_metrics(
    trades: list[dict[str, Any]],
    scenario: str,
    variant: str,
) -> TradeMetrics:
    """Compute comprehensive metrics from a list of trade rows."""
    m = TradeMetrics(scenario=scenario, variant=variant)
    if not trades:
        return m

    m.trade_count = len(trades)
    returns = [_as_float(t.get("net_pnl_pct", t.get("pnl_pct"))) for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    m.win_rate = len(wins) / len(returns) if returns else 0.0
    m.total_return = _compound_return(returns)
    m.avg_return = statistics.mean(returns) if returns else 0.0
    m.max_drawdown = _max_drawdown(returns)

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    # Expectancy = (WR × avg_win) - ((1-WR) × avg_loss)
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = abs(statistics.mean(losses)) if losses else 0.0
    m.expectancy = (m.win_rate * avg_win) - ((1 - m.win_rate) * avg_loss)

    # R multiples (pnl / stop_distance)
    r_multiples = []
    for t in trades:
        stop = _as_float(t.get("stop_distance"))
        if stop > 0:
            r_multiples.append(_as_float(t.get("net_pnl_pct", t.get("pnl_pct"))) / stop)
    m.avg_r_multiple = statistics.mean(r_multiples) if r_multiples else 0.0

    # TITAN-specific metrics
    titan_trades = [t for t in trades if t.get("engine") == "TITAN"]
    m.titan_trades = len(titan_trades)
    titan_returns = [_as_float(t.get("net_pnl_pct", t.get("pnl_pct"))) for t in titan_trades]
    titan_wins = [r for r in titan_returns if r > 0]
    titan_losses = [r for r in titan_returns if r <= 0]
    m.titan_win_rate = len(titan_wins) / len(titan_returns) if titan_returns else 0.0
    m.titan_avg_return = statistics.mean(titan_returns) if titan_returns else 0.0
    titan_gp = sum(titan_wins) if titan_wins else 0.0
    titan_gl = abs(sum(titan_losses)) if titan_losses else 0.0
    m.titan_pf = titan_gp / titan_gl if titan_gl > 0 else float("inf") if titan_gp > 0 else 0.0

    # Partial TP (trade_ids ending in -a are partial TP positions)
    partial_trades = [t for t in trades if str(t.get("trade_id", "")).endswith("-a")]
    partial_winners = [t for t in partial_trades if _as_float(t.get("net_pnl_pct")) > 0]
    m.partial_tp_hits = len(partial_winners)
    m.partial_tp_rate = len(partial_winners) / len(partial_trades) if partial_trades else 0.0

    # Long/short breakdown
    m.long_count = sum(1 for t in trades if t.get("side", "").lower() == "long")
    m.short_count = sum(1 for t in trades if t.get("side", "").lower() == "short")

    # Average hold
    hold_vals = [_as_float(t.get("hold_minutes")) for t in trades if t.get("hold_minutes")]
    m.avg_hold_minutes = statistics.mean(hold_vals) if hold_vals else 0.0

    # Regime distribution
    for t in trades:
        regime = str(t.get("regime_at_entry", "UNKNOWN"))
        m.regime_distribution[regime] = m.regime_distribution.get(regime, 0) + 1

    # Asset distribution
    for t in trades:
        symbol = str(t.get("symbol", "UNKNOWN"))
        m.asset_distribution[symbol] = m.asset_distribution.get(symbol, 0) + 1

    return m


def _compound_return(returns: list[float]) -> float:
    equity = 1.0
    for r in returns:
        equity *= (1 + r)
    return equity - 1.0


def _max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= (1 + r)
        peak = max(peak, equity)
        dd = (equity - peak) / peak
        max_dd = min(max_dd, dd)
    return max_dd


# ─────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────

def write_summary_report(
    all_metrics: list[TradeMetrics],
    output_dir: Path,
) -> None:
    """Write markdown + CSV summary report."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Markdown report ──
    md_path = output_dir / "TITAN_V2_VALIDATION.md"
    lines: list[str] = []
    lines.append("# TITAN v2 Validation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    for m in all_metrics:
        lines.append(f"## {m.scenario} — {m.variant}")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total trades | {m.trade_count} |")
        lines.append(f"| Win rate | {m.win_rate:.1%} |")
        lines.append(f"| Total return | {m.total_return:.4%} |")
        lines.append(f"| Avg return | {m.avg_return:.4%} |")
        lines.append(f"| Profit factor | {m.profit_factor:.3f} |")
        lines.append(f"| Expectancy (bps) | {m.expectancy * 10000:.2f} |")
        lines.append(f"| Avg R multiple | {m.avg_r_multiple:.3f} |")
        lines.append(f"| Max drawdown | {m.max_drawdown:.4%} |")
        lines.append(f"| Long / Short | {m.long_count} / {m.short_count} |")
        lines.append(f"| Avg hold (min) | {m.avg_hold_minutes:.0f} |")
        lines.append("")
        lines.append(f"### TITAN Engine")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| TITAN trades | {m.titan_trades} |")
        lines.append(f"| TITAN win rate | {m.titan_win_rate:.1%} |")
        lines.append(f"| TITAN avg return | {m.titan_avg_return:.4%} |")
        lines.append(f"| TITAN PF | {m.titan_pf:.3f} |")
        lines.append(f"| Partial TP hits | {m.partial_tp_hits} |")
        lines.append(f"| Partial TP rate | {m.partial_tp_rate:.1%} |")
        lines.append("")

        if m.regime_distribution:
            lines.append(f"### Regime Distribution")
            lines.append(f"| Regime | Count | Pct |")
            lines.append(f"|--------|-------|-----|")
            total = sum(m.regime_distribution.values())
            for regime, count in sorted(m.regime_distribution.items(), key=lambda x: -x[1]):
                lines.append(f"| {regime} | {count} | {count/total:.1%} |")
            lines.append("")

        if m.asset_distribution:
            lines.append(f"### Asset Distribution")
            lines.append(f"| Asset | Count | Pct |")
            lines.append(f"|-------|-------|-----|")
            total = sum(m.asset_distribution.values())
            for asset, count in sorted(m.asset_distribution.items(), key=lambda x: -x[1]):
                lines.append(f"| {asset} | {count} | {count/total:.1%} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[validate_titan_v2] report={md_path}")

    # ── CSV summary ──
    csv_path = output_dir / "TITAN_V2_VALIDATION.csv"
    fieldnames = [
        "scenario", "variant", "trade_count", "win_rate", "total_return",
        "avg_return", "profit_factor", "expectancy_bps", "avg_r_multiple",
        "max_drawdown", "titan_trades", "titan_win_rate", "titan_avg_return",
        "titan_pf", "partial_tp_hits", "partial_tp_rate",
        "long_count", "short_count", "avg_hold_minutes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in all_metrics:
            writer.writerow({
                "scenario": m.scenario,
                "variant": m.variant,
                "trade_count": m.trade_count,
                "win_rate": f"{m.win_rate:.4f}",
                "total_return": f"{m.total_return:.6f}",
                "avg_return": f"{m.avg_return:.6f}",
                "profit_factor": f"{m.profit_factor:.4f}",
                "expectancy_bps": f"{m.expectancy * 10000:.2f}",
                "avg_r_multiple": f"{m.avg_r_multiple:.4f}",
                "max_drawdown": f"{m.max_drawdown:.6f}",
                "titan_trades": m.titan_trades,
                "titan_win_rate": f"{m.titan_win_rate:.4f}",
                "titan_avg_return": f"{m.titan_avg_return:.6f}",
                "titan_pf": f"{m.titan_pf:.4f}",
                "partial_tp_hits": m.partial_tp_hits,
                "partial_tp_rate": f"{m.partial_tp_rate:.4f}",
                "long_count": m.long_count,
                "short_count": m.short_count,
                "avg_hold_minutes": f"{m.avg_hold_minutes:.0f}",
            })
    print(f"[validate_titan_v2] csv={csv_path}")


# ─────────────────────────────────────────────────────────────────────
# DB scanning — find existing backtest run DBs
# ─────────────────────────────────────────────────────────────────────

def scan_run_dbs(
    runs_root: Path,
    scenario_name: str,
) -> list[Path]:
    """Find all month-level backtest.db files for a given scenario."""
    dbs: list[Path] = []
    # Pattern: runs_root/<scenario>/<timestamp>/<scenario__orion_X>/<YYYY-MM>/backtest.db
    for scenario_dir in sorted(runs_root.glob(f"{scenario_name}*")):
        if not scenario_dir.is_dir():
            continue
        for timestamp_dir in sorted(scenario_dir.iterdir()):
            if not timestamp_dir.is_dir():
                continue
            for orion_dir in sorted(timestamp_dir.iterdir()):
                if not orion_dir.is_dir():
                    continue
                for month_dir in sorted(orion_dir.iterdir()):
                    db = month_dir / "backtest.db"
                    if db.exists():
                        dbs.append(db)
    return dbs


def load_all_trades(db_paths: list[Path]) -> list[dict[str, Any]]:
    """Load closed trades from multiple backtest DBs."""
    all_trades: list[dict[str, Any]] = []
    for db_path in db_paths:
        trades = _load_closed_trades(db_path)
        all_trades.extend(trades)
    return all_trades


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TITAN v2 Validation")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIO_CONFIGS.keys()),
        help="Run validation for specific scenario",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run validation for all scenarios",
    )
    parser.add_argument(
        "--runs-dir",
        type=str,
        default=str(PROJECT_ROOT / "runs" / "war_backtest_lab"),
        help="Root directory of backtest runs",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=str(REPORTS_DIR),
        help="Output directory for reports",
    )
    args = parser.parse_args(argv)

    runs_root = Path(args.runs_dir)
    reports_dir = Path(args.reports_dir)

    if args.all:
        scenarios = list(SCENARIO_CONFIGS.keys())
    elif args.scenario:
        scenarios = [args.scenario]
    else:
        print("Specify --scenario <name> or --all")
        return 1

    all_metrics: list[TradeMetrics] = []

    for scenario_name in scenarios:
        config = SCENARIO_CONFIGS[scenario_name]
        print(f"\n{'='*60}")
        print(f"Validating: {scenario_name}")
        print(f"{'='*60}")

        # Find existing run DBs
        db_paths = scan_run_dbs(runs_root, scenario_name)
        if not db_paths:
            print(f"  No backtest DBs found for {scenario_name} in {runs_root}")
            print(f"  Run war_backtest_lab first: python Scripts/war_backtest_lab.py --scenario {scenario_name}")
            continue

        print(f"  Found {len(db_paths)} month DBs")

        # Load all trades
        trades = load_all_trades(db_paths)
        print(f"  Total closed trades: {len(trades)}")

        if not trades:
            print(f"  No trades found — skipping")
            continue

        # BTC-only variant
        btc_trades = [t for t in trades if t.get("symbol") in config["assets_btc"]]
        if btc_trades:
            m_btc = compute_metrics(btc_trades, scenario_name, "btc_only")
            all_metrics.append(m_btc)
            print(f"  BTC-only: {m_btc.trade_count} trades, WR={m_btc.win_rate:.1%}, "
                  f"PF={m_btc.profit_factor:.3f}, Return={m_btc.total_return:.4%}")

        # Multi-asset variant
        multi_trades = [t for t in trades if t.get("symbol") in config["assets_multi"]]
        if multi_trades:
            m_multi = compute_metrics(multi_trades, scenario_name, "multi_asset")
            all_metrics.append(m_multi)
            print(f"  Multi-asset: {m_multi.trade_count} trades, WR={m_multi.win_rate:.1%}, "
                  f"PF={m_multi.profit_factor:.3f}, Return={m_multi.total_return:.4%}")

        # Engine breakdown
        engines = Counter(t.get("engine") for t in trades)
        print(f"  Engine breakdown: {dict(engines)}")

    if all_metrics:
        write_summary_report(all_metrics, reports_dir)
        print(f"\nValidation complete. Reports in: {reports_dir}")
    else:
        print("\nNo data found for validation. Run backtest scenarios first.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
