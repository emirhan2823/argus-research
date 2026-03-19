"""Isolated Engine Backtest — Evidence-based engine ranking.

Forces a single engine through the full pipeline across multiple scenarios.
Collects metrics: net profit, max drawdown, profit factor, expectancy, trade count.

Usage:
    python Scripts/isolated_engine_backtest.py --engine POSEIDON
    python Scripts/isolated_engine_backtest.py --engine AEGEAN
    python Scripts/isolated_engine_backtest.py --engine POSEIDON --scenario luna_crash_2022
    python Scripts/isolated_engine_backtest.py --all-engines
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# -- Scenarios ----------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "luna_crash_2022": {
        "start": date(2022, 5, 1),
        "end": date(2022, 7, 31),
        "label": "Luna Crash (May-Jul 2022)",
        "symbols": ("BTCUSDT", "ETHUSDT"),
    },
    "bear_2022": {
        "start": date(2022, 1, 1),
        "end": date(2022, 12, 31),
        "label": "Bear Market 2022",
        "symbols": ("BTCUSDT", "ETHUSDT"),
    },
    "bull_2024": {
        "start": date(2024, 1, 1),
        "end": date(2024, 12, 31),
        "label": "Bull Market 2024",
        "symbols": ("BTCUSDT", "ETHUSDT"),
    },
    "covid_crash_2020": {
        "start": date(2020, 2, 15),
        "end": date(2020, 5, 31),
        "label": "COVID Crash (Feb-May 2020)",
        "symbols": ("BTCUSDT", "ETHUSDT"),
    },
}

# Engines worth testing (excludes PHOENIX=quarantined, HERMES=overlay, GEMINI=pairs)
TESTABLE_ENGINES = ("POSEIDON", "AEGEAN", "NAUTILUS", "HYDRA", "TITAN")


@dataclass
class ScenarioResult:
    engine: str
    scenario: str
    label: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy_pct: float = 0.0
    avg_duration_candles: float = 0.0
    exit_reasons: dict[str, int] = field(default_factory=dict)
    long_trades: int = 0
    short_trades: int = 0
    long_pnl_pct: float = 0.0
    short_pnl_pct: float = 0.0
    status: str = "pending"
    error: str = ""


def _to_iso_z(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()


def _month_slices(start: date, end: date) -> list[tuple[date, date]]:
    """Split date range into monthly slices."""
    slices = []
    current = start.replace(day=1)
    while current <= end:
        month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        slice_start = max(current, start)
        slice_end = min(month_end, end)
        if slice_start <= slice_end:
            slices.append((slice_start, slice_end))
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    return slices


def _run_single_month(
    engine: str,
    symbols: tuple[str, ...],
    replay_start: date,
    replay_end: date,
    run_dir: Path,
    db_path: Path,
    timeout_seconds: int = 1800,
    no_compound: bool = False,
    multi_engines: list[str] | None = None,
) -> tuple[str, str]:
    """Run one month of backtest via src.main subprocess with engine isolation."""

    # Calculate cycles: number of 1h candles in the period
    delta_hours = int((datetime.combine(replay_end, datetime.min.time())
                       - datetime.combine(replay_start, datetime.min.time())).total_seconds() / 3600)
    cycles = max(1, delta_hours)

    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "--mode", "backtest",
        "--assets", "crypto",
        "--v25",
        "--v25-db", str(db_path),
        "--run-dir", str(run_dir),
        "--max-cycles", str(cycles),
        "--cycle-step-minutes", "60",
        "--hold-minutes", "60",
        "--symbols", ",".join(symbols),
        "--risk-profile", "normal",
        "--replay-now", _to_iso_z(replay_start),
        "--forward-sim",
        "--timeframe", "1h",
    ]

    # Engine selection: multi-engine or single-engine
    if multi_engines and len(multi_engines) > 1:
        cmd.extend(["--force-engines", ",".join(multi_engines)])
    else:
        cmd.extend(["--force-engine", engine])

    if no_compound:
        cmd.append("--no-compound")

    # Save command for debugging
    (run_dir / "runner_command.txt").write_text(" ".join(cmd), encoding="utf-8")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        (run_dir / "runner_stdout.log").write_text("", encoding="utf-8")
        (run_dir / "runner_stderr.log").write_text("timeout\n", encoding="utf-8")
        return "FAILED", "timeout"

    (run_dir / "runner_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "runner_stderr.log").write_text(proc.stderr or "", encoding="utf-8")

    if proc.returncode != 0:
        return "FAILED", f"exit_{proc.returncode}"
    return "COMPLETED", "ok"


def _extract_metrics_from_db(db_path: Path, engine: str) -> dict[str, Any]:
    """Extract trade metrics from backtest SQLite database."""
    if not db_path.exists():
        return {"trades": 0, "error": "db_not_found"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check which tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    trades = []
    # Try multiple known table names
    for table in ("backtest_execution_sim", "closed_trades", "trades"):
        if table in tables:
            try:
                cursor.execute(f"SELECT * FROM {table}")
                trades = [dict(row) for row in cursor.fetchall()]
                break
            except Exception:
                continue

    conn.close()

    if not trades:
        # Fallback: try parsing decisions table for executed signals
        return {"trades": 0, "note": "no_trade_table_found", "tables": list(tables)}

    # Filter to target engine (some backtests may have multiple engines)
    if engine.upper() == "ALL":
        engine_trades = trades  # Multi-engine combined mode: use all trades
    else:
        engine_trades = [t for t in trades if t.get("engine", "").upper() == engine.upper()]
        if not engine_trades:
            # If no engine column, use all trades (single-engine backtest)
            engine_trades = trades

    total = len(engine_trades)
    if total == 0:
        return {"trades": 0}

    wins = sum(1 for t in engine_trades if float(t.get("pnl_pct", t.get("pnl_usd", 0))) > 0)
    losses = total - wins

    pnl_pcts = [float(t.get("pnl_pct", 0)) for t in engine_trades]
    pnl_usds = [float(t.get("pnl_usd", 0)) for t in engine_trades]

    gross_profit = sum(p for p in pnl_usds if p > 0)
    gross_loss = abs(sum(p for p in pnl_usds if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    total_pnl_pct = sum(pnl_pcts)
    expectancy_pct = total_pnl_pct / total if total > 0 else 0

    # Max drawdown from cumulative PnL
    cumulative = []
    running = 0
    for p in pnl_pcts:
        running += p
        cumulative.append(running)
    peak = 0.0
    max_dd = 0.0
    for c in cumulative:
        if c > peak:
            peak = c
        dd = peak - c
        if dd > max_dd:
            max_dd = dd

    # Exit reasons
    exit_reasons: dict[str, int] = defaultdict(int)
    for t in engine_trades:
        reason = t.get("exit_reason", "unknown")
        exit_reasons[reason] += 1

    # Duration
    durations = [float(t.get("duration_candles", 0)) for t in engine_trades if t.get("duration_candles")]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Long/short breakdown
    long_trades = [t for t in engine_trades if t.get("side", "").lower() == "long"]
    short_trades = [t for t in engine_trades if t.get("side", "").lower() == "short"]

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / total if total > 0 else 0,
        "total_pnl_pct": round(total_pnl_pct, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "profit_factor": round(profit_factor, 4),
        "expectancy_pct": round(expectancy_pct, 4),
        "avg_duration_candles": round(avg_duration, 1),
        "exit_reasons": dict(exit_reasons),
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "long_pnl_pct": round(sum(float(t.get("pnl_pct", 0)) for t in long_trades), 4),
        "short_pnl_pct": round(sum(float(t.get("pnl_pct", 0)) for t in short_trades), 4),
    }


def run_scenario(
    engine: str,
    scenario_name: str,
    output_root: Path,
    timeout_per_month: int = 1800,
    no_compound: bool = False,
    multi_engines: list[str] | None = None,
) -> ScenarioResult:
    """Run one engine through one scenario (monthly sliced)."""
    scenario = SCENARIOS[scenario_name]
    result = ScenarioResult(
        engine=engine,
        scenario=scenario_name,
        label=scenario["label"],
    )

    start = scenario["start"]
    end = scenario["end"]
    symbols = scenario["symbols"]
    slices = _month_slices(start, end)

    scenario_dir = output_root / f"{engine}" / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    all_metrics: list[dict[str, Any]] = []
    failed_months = 0

    for slice_start, slice_end in slices:
        month_label = slice_start.strftime("%Y-%m")
        month_dir = scenario_dir / month_label
        db_path = month_dir / "backtest.db"

        print(f"  [{engine}] {scenario_name} / {month_label} ...", end=" ", flush=True)

        status, detail = _run_single_month(
            engine=engine,
            symbols=symbols,
            replay_start=slice_start,
            replay_end=slice_end,
            run_dir=month_dir,
            db_path=db_path,
            timeout_seconds=timeout_per_month,
            no_compound=no_compound,
            multi_engines=multi_engines,
        )

        if status != "COMPLETED":
            print(f"FAILED ({detail})")
            failed_months += 1
            continue

        # In multi-engine mode, pass "ALL" to skip engine filtering
        _extract_engine = "ALL" if multi_engines else engine
        metrics = _extract_metrics_from_db(db_path, _extract_engine)
        all_metrics.append(metrics)
        trades = metrics.get("trades", 0)
        print(f"OK ({trades} trades)")

    # Aggregate metrics
    total_trades = sum(m.get("trades", 0) for m in all_metrics)
    total_wins = sum(m.get("wins", 0) for m in all_metrics)
    total_losses = sum(m.get("losses", 0) for m in all_metrics)
    total_pnl_pct = sum(m.get("total_pnl_pct", 0) for m in all_metrics)

    # Aggregate PnL for drawdown across months
    # (This is approximate — true drawdown requires continuous equity curve)
    monthly_pnls = [m.get("total_pnl_pct", 0) for m in all_metrics]
    peak = 0.0
    max_dd = 0.0
    running = 0.0
    for p in monthly_pnls:
        running += p
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    # Aggregate exit reasons
    agg_exit_reasons: dict[str, int] = defaultdict(int)
    for m in all_metrics:
        for reason, count in m.get("exit_reasons", {}).items():
            agg_exit_reasons[reason] += count

    # Aggregate durations
    all_durations = [m.get("avg_duration_candles", 0) * m.get("trades", 0) for m in all_metrics]
    avg_duration = sum(all_durations) / total_trades if total_trades > 0 else 0

    # Long/short
    long_trades = sum(m.get("long_trades", 0) for m in all_metrics)
    short_trades = sum(m.get("short_trades", 0) for m in all_metrics)
    long_pnl = sum(m.get("long_pnl_pct", 0) for m in all_metrics)
    short_pnl = sum(m.get("short_pnl_pct", 0) for m in all_metrics)

    # Profit factor from aggregated wins/losses
    gross_profit_pct = sum(max(0, m.get("total_pnl_pct", 0)) for m in all_metrics)
    gross_loss_pct = abs(sum(min(0, m.get("total_pnl_pct", 0)) for m in all_metrics))
    pf = gross_profit_pct / gross_loss_pct if gross_loss_pct > 0 else (
        float("inf") if gross_profit_pct > 0 else 0
    )

    result.total_trades = total_trades
    result.wins = total_wins
    result.losses = total_losses
    result.win_rate = total_wins / total_trades if total_trades > 0 else 0
    result.total_pnl_pct = round(total_pnl_pct, 4)
    result.max_drawdown_pct = round(max_dd, 4)
    result.profit_factor = round(pf, 4)
    result.expectancy_pct = round(total_pnl_pct / total_trades, 4) if total_trades > 0 else 0
    result.avg_duration_candles = round(avg_duration, 1)
    result.exit_reasons = dict(agg_exit_reasons)
    result.long_trades = long_trades
    result.short_trades = short_trades
    result.long_pnl_pct = round(long_pnl, 4)
    result.short_pnl_pct = round(short_pnl, 4)
    result.status = "completed" if failed_months == 0 else f"partial ({failed_months} months failed)"

    # Save per-scenario JSON
    (scenario_dir / "result.json").write_text(
        json.dumps(result.__dict__, indent=2, default=str), encoding="utf-8"
    )

    return result


def _print_results_table(results: list[ScenarioResult]) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 120)
    print("ISOLATED ENGINE BACKTEST RESULTS")
    print("=" * 120)

    # Group by scenario
    scenarios_seen: dict[str, list[ScenarioResult]] = defaultdict(list)
    for r in results:
        scenarios_seen[r.scenario].append(r)

    for scenario, scenario_results in scenarios_seen.items():
        label = scenario_results[0].label if scenario_results else scenario
        print(f"\n{'-' * 120}")
        print(f"  {label}")
        print(f"{'-' * 120}")
        print(f"  {'Engine':<12} {'Trades':>7} {'WR%':>7} {'PnL%':>10} {'MaxDD%':>8} {'PF':>7} "
              f"{'Expect%':>9} {'Long':>6} {'Short':>6} {'L_PnL%':>8} {'S_PnL%':>8} {'Status'}")
        print(f"  {'-' * 108}")

        for r in sorted(scenario_results, key=lambda x: x.total_pnl_pct, reverse=True):
            wr = f"{r.win_rate * 100:.1f}" if r.total_trades > 0 else "N/A"
            pf = f"{r.profit_factor:.2f}" if r.profit_factor != float("inf") else "INF"
            print(f"  {r.engine:<12} {r.total_trades:>7} {wr:>7} {r.total_pnl_pct:>10.2f} "
                  f"{r.max_drawdown_pct:>8.2f} {pf:>7} {r.expectancy_pct:>9.4f} "
                  f"{r.long_trades:>6} {r.short_trades:>6} {r.long_pnl_pct:>8.2f} "
                  f"{r.short_pnl_pct:>8.2f} {r.status}")


def _write_summary_csv(results: list[ScenarioResult], output_path: Path) -> None:
    """Write all results to CSV."""
    if not results:
        return
    fieldnames = [
        "engine", "scenario", "label", "total_trades", "wins", "losses",
        "win_rate", "total_pnl_pct", "max_drawdown_pct", "profit_factor",
        "expectancy_pct", "avg_duration_candles", "long_trades", "short_trades",
        "long_pnl_pct", "short_pnl_pct", "status",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {k: getattr(r, k) for k in fieldnames}
            row["win_rate"] = round(r.win_rate * 100, 1)
            writer.writerow(row)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Isolated Engine Backtest for Evidence-Based Ranking")
    parser.add_argument("--engine", type=str, help="Engine to test (e.g., POSEIDON)")
    parser.add_argument("--all-engines", action="store_true", help="Test all engines")
    parser.add_argument("--scenario", type=str, help="Single scenario (e.g., luna_crash_2022)")
    parser.add_argument("--output-dir", type=str, default="runs/isolated_engine_backtest",
                        help="Output root directory")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout per month (seconds)")
    parser.add_argument("--no-compound", action="store_true", default=False,
                        help="Use fixed position sizing (no equity compounding)")
    parser.add_argument("--engines", type=str, default=None,
                        help="Combined multi-engine test (comma-separated, e.g. AEGEAN,TITAN)")
    args = parser.parse_args(argv)

    if not args.engine and not args.all_engines and not args.engines:
        parser.error("Specify --engine ENGINE, --all-engines, or --engines ENGINE1,ENGINE2")

    # Multi-engine combined mode
    multi_engines: list[str] | None = None
    if args.engines:
        multi_engines = [e.strip().upper() for e in args.engines.split(",") if e.strip()]
        engines = ["_".join(multi_engines)]  # label for output dir
    elif args.all_engines:
        engines = list(TESTABLE_ENGINES)
    else:
        engines = [args.engine.upper()]
    scenarios = [args.scenario] if args.scenario else list(SCENARIOS.keys())

    # Validate (skip for combined multi-engine labels like AEGEAN_TITAN)
    if not multi_engines:
        for e in engines:
            if e not in TESTABLE_ENGINES:
                parser.error(f"Unknown engine: {e}. Available: {TESTABLE_ENGINES}")
    for s in scenarios:
        if s not in SCENARIOS:
            parser.error(f"Unknown scenario: {s}. Available: {list(SCENARIOS.keys())}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = Path(args.output_dir) / timestamp

    print(f"Isolated Engine Backtest")
    print(f"Engines: {engines}")
    print(f"Scenarios: {scenarios}")
    print(f"Output: {output_root}")
    print()

    all_results: list[ScenarioResult] = []

    for engine in engines:
        for scenario in scenarios:
            print(f"\n{'=' * 80}")
            print(f"ENGINE: {engine} | SCENARIO: {SCENARIOS[scenario]['label']}")
            print(f"{'=' * 80}")

            result = run_scenario(
                engine=engine,
                scenario_name=scenario,
                output_root=output_root,
                timeout_per_month=args.timeout,
                no_compound=bool(args.no_compound),
                multi_engines=multi_engines,
            )
            all_results.append(result)

    # Print results
    _print_results_table(all_results)

    # Save CSV
    csv_path = output_root / "ENGINE_RANKING.csv"
    _write_summary_csv(all_results, csv_path)
    print(f"\nResults saved to: {csv_path}")

    # Save JSON
    json_path = output_root / "ENGINE_RANKING.json"
    json_path.write_text(
        json.dumps([r.__dict__ for r in all_results], indent=2, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
