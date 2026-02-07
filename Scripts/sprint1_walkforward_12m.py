#!/usr/bin/env python3
import argparse
import calendar
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple


def add_months(d: date, months: int) -> date:
    month_idx = (d.month - 1) + months
    year = d.year + (month_idx // 12)
    month = (month_idx % 12) + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_run_dir(stdout: str) -> Optional[str]:
    for pattern in [r"Log Dir:\s*(\S+)", r"Logging run to:\s*(\S+)"]:
        m = re.search(pattern, stdout)
        if m:
            return m.group(1).strip()
    return None


def make_empty_row(start_dt: date, end_dt: date, reason: str, final_equity: float) -> Dict[str, object]:
    return {
        "window_start": start_dt.strftime("%Y-%m-%d"),
        "window_end": end_dt.strftime("%Y-%m-%d"),
        "run_id": f"NO_DATA_{start_dt.strftime('%Y%m')}",
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "final_equity": float(final_equity),
        "run_dir": "",
        "status": reason,
    }


def run_window(args: argparse.Namespace, start_dt: date, end_dt: date, extra_cli_args: List[str]) -> Dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "argus_py.runner.cli",
        "--mode",
        "backtest",
        "--symbol",
        args.symbol,
        "--asset_class",
        args.asset_class,
        "--market_adapter",
        args.market_adapter,
        "--start_balance",
        str(args.start_balance),
        "--data_dir",
        args.data_dir,
        "--start_date",
        start_dt.strftime("%Y-%m-%d"),
        "--end_date",
        end_dt.strftime("%Y-%m-%d"),
        "--quiet",
        "--no_report",
    ] + extra_cli_args

    if args.max_bars is not None:
        cmd += ["--max_bars", str(args.max_bars)]

    env = os.environ.copy()
    mpl_cache = os.path.join("runs", ".mplcache")
    os.makedirs(mpl_cache, exist_ok=True)
    env["MPLCONFIGDIR"] = mpl_cache

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=args.window_timeout_sec,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"Window timeout for {start_dt} -> {end_dt} after {args.window_timeout_sec}s. "
            f"Command: {' '.join(cmd)}"
        ) from e
    if proc.returncode != 0:
        raise RuntimeError(
            f"Backtest failed for {start_dt} -> {end_dt}\n"
            f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )

    run_dir = parse_run_dir(proc.stdout)
    if not run_dir:
        if "No bars left after filter!" in proc.stdout:
            return make_empty_row(start_dt, end_dt, "NO_DATA", args.start_balance)
        raise RuntimeError(
            f"Could not parse run_dir from CLI output for {start_dt} -> {end_dt}\n"
            f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )

    summary_path = os.path.join(run_dir, "summary.json")
    if not os.path.exists(summary_path):
        if "No bars left after filter!" in proc.stdout:
            return make_empty_row(start_dt, end_dt, "NO_DATA", args.start_balance)
        files = sorted(os.listdir(run_dir)) if os.path.isdir(run_dir) else []
        raise FileNotFoundError(
            f"summary.json not found: {summary_path}\n"
            f"run_dir_files={files}\n"
            f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )

    with open(summary_path, "r") as f:
        summary = json.load(f)

    return {
        "window_start": start_dt.strftime("%Y-%m-%d"),
        "window_end": end_dt.strftime("%Y-%m-%d"),
        "run_id": os.path.basename(run_dir),
        "total_return_pct": float(summary.get("total_return_pct", 0.0)),
        "max_drawdown_pct": float(summary.get("max_drawdown_pct", 0.0)),
        "total_trades": int(summary.get("total_trades", 0)),
        "win_rate": float(summary.get("win_rate", 0.0)),
        "profit_factor": float(summary.get("profit_factor", 0.0)),
        "final_equity": float(summary.get("final_equity", 0.0)),
        "run_dir": run_dir,
        "status": "OK",
    }


def aggregate(rows: List[Dict[str, object]]) -> Dict[str, float]:
    if not rows:
        return {
            "windows": 0,
            "positive_windows": 0,
            "avg_return_pct": 0.0,
            "compounded_return_pct": 0.0,
            "avg_max_drawdown_pct": 0.0,
        }

    returns = [float(r["total_return_pct"]) / 100.0 for r in rows]
    drawdowns = [float(r["max_drawdown_pct"]) for r in rows]
    compounded = 1.0
    for r in returns:
        compounded *= (1.0 + r)

    return {
        "windows": len(rows),
        "positive_windows": sum(1 for r in returns if r > 0.0),
        "avg_return_pct": (sum(returns) / len(returns)) * 100.0,
        "compounded_return_pct": (compounded - 1.0) * 100.0,
        "avg_max_drawdown_pct": sum(drawdowns) / len(drawdowns),
    }


def write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = [
        "window_start",
        "window_end",
        "run_id",
        "total_return_pct",
        "max_drawdown_pct",
        "total_trades",
        "win_rate",
        "profit_factor",
        "final_equity",
        "run_dir",
        "status",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_md(path: str, args: argparse.Namespace, rows: List[Dict[str, object]], stats: Dict[str, float], extra_cli_args: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    lines.append("# Sprint-1 Walk-Forward 12M Report")
    lines.append("")
    lines.append(f"- Generated: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append(f"- Symbol: `{args.symbol}`")
    lines.append(f"- Asset: `{args.asset_class}`")
    lines.append(f"- Adapter: `{args.market_adapter}`")
    lines.append(f"- Start Balance: `{args.start_balance}`")
    lines.append(f"- Start Date: `{args.start_date}`")
    lines.append(f"- Months: `{args.months}`")
    lines.append(f"- Max Bars: `{args.max_bars}`")
    lines.append(f"- Extra CLI Args: `{' '.join(extra_cli_args) if extra_cli_args else '(none)'}`")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- windows: `{stats['windows']}`")
    lines.append(f"- positive_windows: `{stats['positive_windows']}`")
    lines.append(f"- avg_return_pct: `{stats['avg_return_pct']:.4f}`")
    lines.append(f"- compounded_return_pct: `{stats['compounded_return_pct']:.4f}`")
    lines.append(f"- avg_max_drawdown_pct: `{stats['avg_max_drawdown_pct']:.4f}`")
    lines.append("")
    lines.append("## Windows")
    lines.append("")
    lines.append("| window_start | window_end | run_id | status | return_pct | max_dd_pct | trades | pf |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['window_start']} | {r['window_end']} | {r['run_id']} | {r['status']} | "
            f"{float(r['total_return_pct']):.4f} | {float(r['max_drawdown_pct']):.4f} | "
            f"{int(r['total_trades'])} | {float(r['profit_factor']):.4f} |"
        )

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def parse_args(argv: List[str]) -> Tuple[argparse.Namespace, List[str]]:
    parser = argparse.ArgumentParser(
        description="Run monthly rolling walk-forward windows and collect summary metrics."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--asset_class", default="crypto", choices=["crypto", "us_equity", "bist"])
    parser.add_argument("--market_adapter", default="auto", choices=["auto", "crypto_csv", "us_equity_stub", "bist_stub"])
    parser.add_argument("--data_dir", default="argus_py/data/cache")
    parser.add_argument("--start_balance", type=float, default=30.0)
    parser.add_argument("--start_date", default="2024-02-01", help="Rolling start date (expected month boundary YYYY-MM-DD)")
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--max_bars", type=int, default=None, help="Optional bar cap per window for fast smoke runs")
    parser.add_argument("--window_timeout_sec", type=int, default=1800, help="Timeout per monthly window (seconds)")
    parser.add_argument("--output_csv", default="")
    parser.add_argument("--output_md", default="")
    args, extra = parser.parse_known_args(argv)
    return args, extra


def main(argv: List[str]) -> int:
    args, extra_cli_args = parse_args(argv)
    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    if args.months <= 0:
        raise ValueError("--months must be > 0")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = args.output_csv or os.path.join("runs", "sweeps", f"walkforward_12m_{ts}.csv")
    md_path = args.output_md or os.path.join("runs", "sweeps", f"walkforward_12m_{ts}.md")

    rows: List[Dict[str, object]] = []
    for i in range(args.months):
        win_start = add_months(start_dt, i)
        win_end = add_months(start_dt, i + 1)
        t0 = time.time()
        print(
            f"WINDOW_START idx={i+1}/{args.months} start={win_start} end={win_end}",
            flush=True,
        )
        row = run_window(args, win_start, win_end, extra_cli_args)
        rows.append(row)
        print(
            f"{row['window_start']},{row['window_end']},{row['run_id']},"
            f"{row['total_return_pct']:.4f},{row['max_drawdown_pct']:.4f},"
            f"{row['total_trades']},{row['win_rate']:.4f},{row['profit_factor']:.4f},"
            f"{row['final_equity']:.4f},status={row['status']},elapsed_sec={time.time()-t0:.1f}",
            flush=True,
        )

    stats = aggregate(rows)
    write_csv(csv_path, rows)
    write_md(md_path, args, rows, stats, extra_cli_args)

    print(
        "WF12M_SUMMARY "
        f"windows={int(stats['windows'])} "
        f"positive_windows={int(stats['positive_windows'])} "
        f"avg_return_pct={stats['avg_return_pct']:.4f} "
        f"compounded_return_pct={stats['compounded_return_pct']:.4f} "
        f"avg_max_drawdown_pct={stats['avg_max_drawdown_pct']:.4f}"
    )
    print(f"RESULT_CSV={csv_path}")
    print(f"RESULT_MD={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
