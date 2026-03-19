"""Combined validation runner — AEGEAN vs TITAN vs AEGEAN+TITAN (fixed-size).

Runs 12 backtests total (3 configs × 4 scenarios) with --no-compound for fair comparison.
Produces a combined comparison table.

Usage:
    python Scripts/run_combined_validation.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIGS = [
    {"label": "AEGEAN_only", "args": ["--engine", "AEGEAN", "--no-compound"]},
    {"label": "TITAN_only", "args": ["--engine", "TITAN", "--no-compound"]},
    {"label": "AEGEAN_TITAN", "args": ["--engines", "AEGEAN,TITAN", "--no-compound"]},
]

SCENARIOS = ["luna_crash_2022", "bear_2022", "bull_2024", "covid_crash_2020"]


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = PROJECT_ROOT / "runs" / "combined_validation" / timestamp

    all_results: list[dict] = []

    for config in CONFIGS:
        label = config["label"]
        for scenario in SCENARIOS:
            print(f"\n{'=' * 80}")
            print(f"CONFIG: {label} | SCENARIO: {scenario}")
            print(f"{'=' * 80}")

            output_dir = str(output_base / label)

            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "Scripts" / "isolated_engine_backtest.py"),
                *config["args"],
                "--scenario", scenario,
                "--output-dir", output_dir,
                "--timeout", "1800",
            ]

            print(f"Running: {' '.join(cmd[-8:])}")

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    text=True,
                    capture_output=True,
                    timeout=7200,
                )
                print(proc.stdout[-500:] if proc.stdout else "(no stdout)")
                if proc.returncode != 0:
                    print(f"STDERR: {proc.stderr[-300:] if proc.stderr else '(none)'}")
            except subprocess.TimeoutExpired:
                print("TIMEOUT (>2h)")
                continue

            # Try to read result JSON
            # Find latest result.json in output dir
            output_path = Path(output_dir)
            result_files = list(output_path.rglob("result.json"))
            for rf in result_files:
                try:
                    data = json.loads(rf.read_text(encoding="utf-8"))
                    data["config"] = label
                    all_results.append(data)
                except Exception:
                    pass

    # Print combined table
    print(f"\n\n{'=' * 140}")
    print("COMBINED VALIDATION RESULTS (FIXED-SIZE / NO COMPOUNDING)")
    print(f"{'=' * 140}")
    print(f"  {'Config':<20} {'Scenario':<22} {'Trades':>7} {'WR%':>7} {'PnL%':>10} "
          f"{'MaxDD%':>8} {'PF':>7} {'Expect%':>9} {'Long':>6} {'Short':>6}")
    print(f"  {'-' * 118}")

    for r in sorted(all_results, key=lambda x: (x.get("config", ""), x.get("scenario", ""))):
        config = r.get("config", "?")
        scenario = r.get("scenario", "?")
        trades = r.get("total_trades", 0)
        wr = f"{r.get('win_rate', 0) * 100:.1f}" if trades > 0 else "N/A"
        pnl = r.get("total_pnl_pct", 0)
        maxdd = r.get("max_drawdown_pct", 0)
        pf = r.get("profit_factor", 0)
        pf_str = f"{pf:.2f}" if pf != float("inf") else "INF"
        exp = r.get("expectancy_pct", 0)
        longs = r.get("long_trades", 0)
        shorts = r.get("short_trades", 0)
        print(f"  {config:<20} {scenario:<22} {trades:>7} {wr:>7} {pnl:>10.2f} "
              f"{maxdd:>8.2f} {pf_str:>7} {exp:>9.4f} {longs:>6} {shorts:>6}")

    # Save combined JSON
    combined_json = output_base / "COMBINED_RESULTS.json"
    combined_json.parent.mkdir(parents=True, exist_ok=True)
    combined_json.write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nResults saved to: {combined_json}")


if __name__ == "__main__":
    main()
