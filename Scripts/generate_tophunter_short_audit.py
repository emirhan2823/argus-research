#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

STRATEGY_TAG = "strategy_id=TOPHUNTER_SHORT_V1"


def _read_rows(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def generate(run_dir: Path, output: Path) -> Path:
    decisions = _read_rows(run_dir / "decisions.csv")
    rejects = _read_rows(run_dir / "rejects.csv")
    trades = _read_rows(run_dir / "trades.csv")

    tagged_decisions = [r for r in decisions if STRATEGY_TAG in (r.get("reasons") or "")]
    tagged_rejects = [r for r in rejects if STRATEGY_TAG in (r.get("detail") or "")]

    go_count = sum(1 for r in tagged_decisions if (r.get("decision") or "").upper() == "GO")
    no_go_count = len(tagged_decisions) - go_count

    reject_codes = Counter((r.get("code") or "UNKNOWN") for r in tagged_rejects)
    total_rejects = sum(reject_codes.values())

    realized_pnl = 0.0
    close_trades = 0
    for row in trades:
        event = (row.get("event") or "").upper()
        if event in {"SL", "TP", "TIME", "EOS"}:
            close_trades += 1
            try:
                realized_pnl += float(row.get("pnl", "0") or 0.0)
            except ValueError:
                pass

    lines = [
        "# TopHunter Short Audit (Minimal)",
        "",
        f"- Run Dir: `{run_dir}`",
        f"- Strategy Tag Filter: `{STRATEGY_TAG}`",
        "",
        "## Decision Summary",
        "",
        f"- Tagged decisions: **{len(tagged_decisions)}**",
        f"- GO decisions: **{go_count}**",
        f"- NO_GO/BLOCK decisions: **{no_go_count}**",
        "",
        "## Reject Summary",
        "",
        f"- Tagged rejects: **{total_rejects}**",
    ]

    if reject_codes:
        lines.append("")
        lines.append("| Reject Code | Count |")
        lines.append("|---|---:|")
        for code, count in sorted(reject_codes.items()):
            lines.append(f"| `{code}` | {count} |")
    else:
        lines.append("- No tagged rejects found.")

    lines.extend(
        [
            "",
            "## Trade Snapshot (Run-level)",
            "",
            f"- Closed trades (all strategies): **{close_trades}**",
            f"- Realized PnL (all strategies): **{realized_pnl:.2f}**",
            "",
            "> Note: trades.csv currently does not include per-trade strategy tag; trade section is run-level.",
            "",
        ]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate minimal TopHunter short markdown audit report.")
    parser.add_argument("run_dir", type=Path, help="Run directory containing decisions.csv/rejects.csv/trades.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/year2/tophunter_short_audit.md"),
        help="Markdown output path",
    )
    args = parser.parse_args()
    out = generate(args.run_dir, args.output)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

