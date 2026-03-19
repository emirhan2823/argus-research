#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.year2_autopilot import (
    TuneParams,
    TuneResult,
    load_market_bars,
    rank_tuning,
    run_tophunter_backtest,
    slice_last_days,
)


def pct(v: float) -> str:
    return f"{v * 100.0:.2f}%"


def write_report(path: Path, ranked: List[TuneResult]) -> None:
    top = ranked[:5]
    lines = [
        "# TopHunter Parameter Sweep (Paper-Only)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "Risk caps unchanged: maxRiskPerTrade=0.5%, dailyLossCap=1.5%, maxConcurrent=1.",
        "",
        "| Rank | adx_max | pivot_window | cooldown_bars | exp_move_min_bps | tp2_ratio | trades | winrate | expectancy | sharpe | maxDD% | totalPnL |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for i, r in enumerate(top, start=1):
        p = r.params
        lines.append(
            f"| {i} | {p.max_adx:.1f} | {p.pivot_window} | {p.cooldown_bars} | {p.exp_move_min_bps:.1f} | {p.tp2_ratio:.2f} | {r.trades} | {pct(r.win_rate)} | {r.expectancy:.4f} | {r.sharpe:.3f} | {r.max_dd_pct:.2f} | {r.total_pnl:.2f} |"
        )

    lines.extend(["", "## Stability Notes", ""])
    if not top:
        lines.append("- No valid configuration produced trades in the selected window.")
    else:
        for r in top:
            tag = "STABLE" if (r.max_dd_pct <= 6.0 and r.trades >= 20) else "WATCH"
            p = r.params
            lines.append(
                f"- `{tag}` adx={p.max_adx:.1f}, pivot={p.pivot_window}, cooldown={p.cooldown_bars}, exp_move={p.exp_move_min_bps:.1f}, tp2={p.tp2_ratio:.2f} -> trades={r.trades}, maxDD={r.max_dd_pct:.2f}%, expectancy={r.expectancy:.4f}"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="TopHunter small-grid sweep (paper-only)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/BTCUSDT/1h"))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", type=Path, default=Path("reports/year2/tophunter_tuning.md"))
    args = parser.parse_args()

    bars = slice_last_days(load_market_bars(args.data_dir), args.days)

    results: List[TuneResult] = []
    for adx_max, pivot, cooldown, exp_move, tp2 in itertools.product(
        [16.0, 18.0, 20.0],
        [2, 3],
        [2, 3, 4],
        [8.0, 12.0, 16.0],
        [1.6, 2.0],
    ):
        params = TuneParams(
            max_adx=adx_max,
            pivot_window=pivot,
            cooldown_bars=cooldown,
            tp2_ratio=tp2,
            exp_move_min_bps=exp_move,
        )
        results.append(run_tophunter_backtest(bars, params))

    ranked = rank_tuning(results)
    write_report(args.out, ranked)
    print(f"[tophunter_sweep] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
