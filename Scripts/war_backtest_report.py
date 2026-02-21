from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.war_forward_report import (  # noqa: E402
    _as_float,
    _build_decision_lookup,
    _build_trade_analytics,
    _load_closed_trades,
    _load_decisions,
    _scenario_metrics,
    _to_iso_z,
    _write_equity_curves,
)
from src.data.replay_loader import ReplayLoader  # noqa: E402


@dataclass(frozen=True)
class BacktestScenario:
    name: str
    start: str
    end: str
    risk_profile: str
    allow_crisis: bool
    orion: bool = False


@dataclass
class ScenarioResult:
    name: str
    status: str
    reason: str
    run_dir: Path
    start_used: str | None = None
    end_used: str | None = None
    cycles: int = 0
    trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    return_volatility: float = 0.0
    risk_adjusted_return: float = 0.0


def _parse_iso_utc(raw: str) -> datetime:
    text = str(raw).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _default_scenarios(smoke: bool) -> list[BacktestScenario]:
    if smoke:
        return [
            BacktestScenario(
                name="smoke_recent",
                start="2026-01-26T15:38:00Z",
                end="2026-01-26T18:30:00Z",
                risk_profile="relaxed",
                allow_crisis=True,
                orion=True,
            )
        ]

    return [
        BacktestScenario(
            name="2022_crash",
            start="2022-05-01T00:00:00Z",
            end="2022-12-31T23:59:00Z",
            risk_profile="strict",
            allow_crisis=True,
            orion=False,
        ),
        BacktestScenario(
            name="2024_bull",
            start="2024-01-01T00:00:00Z",
            end="2024-12-31T23:59:00Z",
            risk_profile="normal",
            allow_crisis=False,
            orion=True,
        ),
    ]


def _range_and_cycles(
    *,
    loader: ReplayLoader,
    symbol: str,
    start: str,
    end: str,
    max_cycles: int,
) -> tuple[datetime, datetime, int] | None:
    try:
        start_key = _parse_iso_utc(start).strftime("%Y-%m-%d %H:%M:%S")
        end_key = _parse_iso_utc(end).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

    try:
        df = loader.load_ohlcv(symbol=symbol, interval="1m", start=start_key, end=end_key, verify=False)
    except Exception:
        return None

    if df.empty:
        return None

    first_ts = pd.Timestamp(df["timestamp"].iloc[0])
    last_ts = pd.Timestamp(df["timestamp"].iloc[-1])
    if first_ts.tzinfo is None:
        first_ts = first_ts.tz_localize("UTC")
    else:
        first_ts = first_ts.tz_convert("UTC")
    if last_ts.tzinfo is None:
        last_ts = last_ts.tz_localize("UTC")
    else:
        last_ts = last_ts.tz_convert("UTC")

    minutes = int(max(1, ((last_ts - first_ts).total_seconds() // 60) + 1))
    cycles = int(max(1, min(int(max_cycles), minutes)))
    return first_ts.to_pydatetime(), last_ts.to_pydatetime(), cycles


def _run_backtest_scenario(
    *,
    scenario: BacktestScenario,
    run_dir: Path,
    db_path: Path,
    symbols: str,
    replay_anchor: str,
    cycles: int,
    hold_minutes: int,
    timeout_seconds: int,
) -> tuple[str, str]:
    cmd: list[str] = [
        sys.executable,
        "-m",
        "src.main",
        "--mode",
        "backtest",
        "--assets",
        "crypto",
        "--v25",
        "--v25-db",
        str(db_path),
        "--run-dir",
        str(run_dir),
        "--max-cycles",
        str(int(cycles)),
        "--cycle-step-minutes",
        "1",
        "--hold-minutes",
        str(int(hold_minutes)),
        "--symbols",
        symbols,
        "--risk-profile",
        scenario.risk_profile,
        "--replay-now",
        replay_anchor,
        "--forward-sim",
    ]
    if scenario.allow_crisis:
        cmd.append("--allow-crisis")
    if scenario.orion:
        cmd.append("--orion")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "runner_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=max(60, int(timeout_seconds)),
        )
    except subprocess.TimeoutExpired:
        (run_dir / "runner_stdout.log").write_text("", encoding="utf-8")
        (run_dir / "runner_stderr.log").write_text("timeout\n", encoding="utf-8")
        return "FAILED", "timeout"

    (run_dir / "runner_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "runner_stderr.log").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        return "FAILED", f"main_exit_{proc.returncode}"
    return "COMPLETED", "ok"


def _write_scenario_monthly_summary(run_dir: Path, trade_rows: list[dict[str, Any]]) -> None:
    monthly_csv = run_dir / "monthly_summary.csv"
    monthly_md = run_dir / "monthly_summary.md"

    by_month: dict[str, list[dict[str, Any]]] = {}
    for row in trade_rows:
        month = str(row.get("exit_time", ""))[:7] or "UNKNOWN"
        by_month.setdefault(month, []).append(row)

    with monthly_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "month",
                "trades",
                "win_rate",
                "avg_return",
                "total_return",
                "max_drawdown",
                "best_engine",
                "worst_engine",
                "regime_dominance",
            ]
        )
        for month in sorted(by_month):
            rows = by_month[month]
            returns = [_as_float(item.get("net_pnl_pct")) for item in rows]
            trades = len(returns)
            wins = sum(1 for val in returns if val > 0.0)
            avg_return = (sum(returns) / trades) if trades else 0.0

            equity = 1.0
            peak = 1.0
            max_dd = 0.0
            by_engine: dict[str, list[float]] = {}
            regime_counts: dict[str, int] = {}
            for item in rows:
                ret = _as_float(item.get("net_pnl_pct"))
                equity *= (1.0 + ret)
                peak = max(peak, equity)
                dd = (equity / peak) - 1.0 if peak > 0.0 else 0.0
                max_dd = min(max_dd, dd)

                engine = str(item.get("engine", "UNKNOWN"))
                by_engine.setdefault(engine, []).append(ret)
                regime = str(item.get("regime_at_entry", "UNKNOWN"))
                regime_counts[regime] = regime_counts.get(regime, 0) + 1

            engine_rank = sorted(
                ((eng, (sum(vals) / len(vals)) if vals else 0.0) for eng, vals in by_engine.items()),
                key=lambda pair: pair[1],
                reverse=True,
            )
            best_engine = engine_rank[0][0] if engine_rank else "N/A"
            worst_engine = engine_rank[-1][0] if engine_rank else "N/A"
            regime_dominance = max(regime_counts, key=regime_counts.get) if regime_counts else "N/A"

            writer.writerow(
                [
                    month,
                    trades,
                    f"{(wins / trades) if trades else 0.0:.6f}",
                    f"{avg_return:.6f}",
                    f"{(equity - 1.0) if trades else 0.0:.6f}",
                    f"{max_dd:.6f}",
                    best_engine,
                    worst_engine,
                    regime_dominance,
                ]
            )

    lines = [
        "# Scenario Monthly Summary",
        "",
        "| month | trades | win_rate | avg_return | total_return | max_drawdown | best_engine | worst_engine | regime_dominance |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    with monthly_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lines.append(
                "| {month} | {trades} | {win_rate} | {avg_return} | {total_return} | {max_drawdown} | {best_engine} | {worst_engine} | {regime_dominance} |".format(
                    **row
                )
            )
    monthly_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(reports_path: Path, results: list[ScenarioResult]) -> None:
    lines = [
        "# WAR Backtest Report",
        "",
        "| scenario | status | reason | start | end | cycles | trades | win_rate | total_return | max_drawdown |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {name} | {status} | {reason} | {start} | {end} | {cycles} | {trades} | {win:.4f} | {ret:.6f} | {dd:.6f} |".format(
                name=row.name,
                status=row.status,
                reason=row.reason,
                start=row.start_used or "n/a",
                end=row.end_used or "n/a",
                cycles=int(row.cycles),
                trades=int(row.trades),
                win=row.win_rate,
                ret=row.total_return,
                dd=row.max_drawdown,
            )
        )

    lines.append("")
    lines.append("## Scenario Artifacts")
    lines.append("")
    for row in results:
        lines.append(f"- `{row.name}` -> `{row.run_dir}`")
        lines.append(f"  - `equity_curve.csv`: {(row.run_dir / 'equity_curve.csv').exists()}")
        lines.append(f"  - `drawdown_curve.csv`: {(row.run_dir / 'drawdown_curve.csv').exists()}")
        lines.append(f"  - `trades/`: {(row.run_dir / 'trades').exists()}")
        lines.append(f"  - `monthly_summary.csv`: {(row.run_dir / 'monthly_summary.csv').exists()}")

    reports_path.parent.mkdir(parents=True, exist_ok=True)
    reports_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run long WAR backtest scenarios and generate aggregate report")
    parser.add_argument("--smoke", action="store_true", default=False, help="Quick scenario smoke mode")
    parser.add_argument("--symbols", default="BTCUSDT", help="Comma-separated symbols")
    parser.add_argument("--hold-minutes", type=int, default=30, help="Backtest hold minutes")
    parser.add_argument("--max-cycles-per-scenario", type=int, default=400, help="Cap cycles per scenario")
    parser.add_argument("--run-root", default="runs/war_backtest", help="Scenario output root")
    parser.add_argument("--reports-dir", default="reports", help="Reports output directory")
    parser.add_argument("--cache-root", default="data/binance", help="Replay parquet root")
    parser.add_argument("--scenario-timeout", type=int, default=1800, help="Per-scenario timeout seconds")
    args = parser.parse_args()

    run_root = PROJECT_ROOT / args.run_root
    run_root.mkdir(parents=True, exist_ok=True)
    reports_dir = PROJECT_ROOT / args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    scenarios = _default_scenarios(smoke=bool(args.smoke))
    loader = ReplayLoader(root=args.cache_root)
    symbols = str(args.symbols)
    primary_symbol = symbols.split(",")[0].strip().upper() if symbols.strip() else "BTCUSDT"

    results: list[ScenarioResult] = []

    for scenario in scenarios:
        run_dir = run_root / scenario.name
        db_path = run_dir / "war_backtest_v25.db"
        result = ScenarioResult(name=scenario.name, status="FAILED", reason="not_started", run_dir=run_dir)

        range_info = _range_and_cycles(
            loader=loader,
            symbol=primary_symbol,
            start=scenario.start,
            end=scenario.end,
            max_cycles=max(1, int(args.max_cycles_per_scenario)),
        )
        if range_info is None:
            result.reason = "no_cached_range_data"
            results.append(result)
            continue

        start_ts, end_ts, cycles = range_info
        result.start_used = _to_iso_z(start_ts)
        result.end_used = _to_iso_z(end_ts)
        result.cycles = int(cycles)

        status, reason = _run_backtest_scenario(
            scenario=scenario,
            run_dir=run_dir,
            db_path=db_path,
            symbols=symbols,
            replay_anchor=_to_iso_z(start_ts),
            cycles=cycles,
            hold_minutes=max(1, int(args.hold_minutes)),
            timeout_seconds=max(60, int(args.scenario_timeout)),
        )
        result.status = status
        result.reason = reason

        if status == "COMPLETED":
            decisions = _load_decisions(db_path)
            trades = _load_closed_trades(db_path)
            decisions_by_symbol = _build_decision_lookup(decisions)
            trade_rows = _build_trade_analytics(
                run_dir=run_dir,
                scenario_id=scenario.name,
                trades=trades,
                decisions_by_symbol=decisions_by_symbol,
                loader=loader,
            )
            _write_equity_curves(run_dir, trades)
            _write_scenario_monthly_summary(run_dir, trade_rows)

            metrics = _scenario_metrics(trade_rows)
            result.trades = int(metrics["trades"])
            result.win_rate = float(metrics["win_rate"])
            result.avg_return = float(metrics["avg_return"])
            result.total_return = float(metrics["total_return"])
            result.max_drawdown = float(metrics["max_drawdown"])
            result.return_volatility = float(metrics["return_volatility"])
            result.risk_adjusted_return = float(metrics["risk_adjusted_return"])

        status_payload = {
            "scenario": scenario.name,
            "status": result.status,
            "reason": result.reason,
            "start": scenario.start,
            "end": scenario.end,
            "start_used": result.start_used,
            "end_used": result.end_used,
            "cycles": int(result.cycles),
            "symbols": symbols,
            "orion": bool(scenario.orion),
        }
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scenario_status.json").write_text(
            json.dumps(status_payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

        results.append(result)

    report_path = reports_dir / "WAR_BACKTEST_REPORT.md"
    _write_report(report_path, results)
    print(f"[war_backtest] scenarios={len(results)}")
    print(f"[war_backtest] report={report_path}")


if __name__ == "__main__":
    main()
