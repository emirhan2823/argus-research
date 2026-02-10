#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.walk_forward import WalkForwardEngine


def _parse_date(raw: str) -> date:
    return date.fromisoformat(str(raw))


def monte_carlo_drawdown_probability(pnls: List[float], threshold_pct: float, runs: int = 500) -> float:
    if not pnls:
        return 0.0
    rng = random.Random(42)
    breaches = 0
    start_equity = 1000.0
    for _ in range(max(1, int(runs))):
        sample = [pnls[rng.randrange(0, len(pnls))] for _ in range(len(pnls))]
        eq = start_equity
        peak = eq
        max_dd = 0.0
        for pnl in sample:
            eq += float(pnl)
            peak = max(peak, eq)
            dd = ((peak - eq) / peak) * 100.0 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        if max_dd > float(threshold_pct):
            breaches += 1
    return breaches / float(max(1, runs))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run walk-forward + Monte Carlo stress summary")
    parser.add_argument("--data-path", "--data_path", dest="data_path", type=Path, required=True)
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--start-date", "--start_date", dest="start_date", type=str, default="2025-01-01")
    parser.add_argument("--end-date", "--end_date", dest="end_date", type=str, default="2026-01-01")
    parser.add_argument("--train-months", "--train_months", dest="train_months", type=int, default=6)
    parser.add_argument("--test-months", "--test_months", dest="test_months", type=int, default=1)
    parser.add_argument("--step-months", "--step_months", dest="step_months", type=int, default=1)
    parser.add_argument("--mc-runs", "--mc_runs", dest="mc_runs", type=int, default=500)
    parser.add_argument("--dd-threshold-pct", "--dd_threshold_pct", dest="dd_threshold_pct", type=float, default=8.0)
    parser.add_argument("--out-dir", "--out_dir", dest="out_dir", type=Path, default=Path("reports/year2/lab"))
    args = parser.parse_args()

    engine = WalkForwardEngine(data_path=args.data_path, output_dir=args.out_dir)
    report = engine.run_full(
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        symbols=[args.symbol],
        skip_invalid=True,
    )
    wf_json = engine.save_report(report, "walkforward_lab")

    pnl_series = [float(w.test_pnl) for w in report.windows]
    mc_prob = monte_carlo_drawdown_probability(pnl_series, threshold_pct=args.dd_threshold_pct, runs=args.mc_runs)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": args.symbol,
        "walkforward": {
            "windows": len(report.windows),
            "aggregate_sharpe": report.aggregate_sharpe,
            "aggregate_pnl": report.aggregate_pnl,
            "aggregate_dd": report.aggregate_dd,
            "no_data_windows": report.no_data_windows,
            "json_path": str(wf_json),
        },
        "monte_carlo": {
            "runs": int(args.mc_runs),
            "dd_threshold_pct": float(args.dd_threshold_pct),
            "p_dd_breach": mc_prob,
        },
    }
    out_json = args.out_dir / "walkforward_montecarlo.json"
    out_md = args.out_dir / "walkforward_montecarlo.md"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# Walk-Forward + Monte Carlo Lab",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Symbol: `{args.symbol}`",
        "",
        "## Walk-Forward Summary",
        "",
        f"- Windows: {len(report.windows)}",
        f"- Aggregate Sharpe: {report.aggregate_sharpe:.4f}",
        f"- Aggregate PnL: {report.aggregate_pnl:.4f}",
        f"- Aggregate MaxDD%: {report.aggregate_dd:.4f}",
        f"- No-data windows: {len(report.no_data_windows)}",
        f"- Report JSON: `{wf_json}`",
        "",
        "## Monte Carlo",
        "",
        f"- Runs: {int(args.mc_runs)}",
        f"- DD Threshold%: {float(args.dd_threshold_pct):.2f}",
        f"- P(maxDD > threshold): **{mc_prob:.4%}**",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[walkforward_mc] wrote {out_md}")
    print(f"[walkforward_mc] wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
