#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def load_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_ts(row: Dict[str, str], candidates: Iterable[str]) -> float | None:
    for key in candidates:
        value = row.get(key)
        if not value:
            continue
        txt = str(value).strip()
        if not txt:
            continue
        if txt.replace(".", "", 1).isdigit():
            ts = float(txt)
            if ts > 1_000_000_000_000:
                ts /= 1000.0
            return ts
        try:
            dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            continue
    return None


def filter_window(rows: List[Dict[str, str]], now_ts: float, window_sec: int, ts_keys: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    start_ts = now_ts - window_sec
    for row in rows:
        ts = parse_ts(row, ts_keys)
        if ts is None:
            continue
        if ts >= start_ts:
            out.append(row)
    return out


def is_closed_trade(row: Dict[str, str]) -> bool:
    event = str(row.get("event", "")).strip().upper()
    if event in {"OPEN", "ENTRY", "REJECTED", ""}:
        return False
    pnl = safe_float(row.get("pnl"), 0.0)
    if event in {"CLOSE", "TP", "SL", "STOP", "TIME", "EXIT", "PROFIT", "LOSS"}:
        return True
    return abs(pnl) > 1e-12


def metrics_from_trades(rows: List[Dict[str, str]]) -> Dict[str, float]:
    closed = [r for r in rows if is_closed_trade(r)]
    if not closed:
        return {
            "trades": 0,
            "winrate": 0.0,
            "expectancy": 0.0,
            "avgR": 0.0,
            "maxDD": 0.0,
        }

    pnls = [safe_float(r.get("pnl"), 0.0) for r in closed]
    wins = sum(1 for p in pnls if p > 0.0)
    expectancy = sum(pnls) / len(pnls)

    losses = [abs(p) for p in pnls if p < 0.0]
    r_base = median(losses) if losses else 1.0
    avg_r = sum((p / r_base) for p in pnls) / len(pnls)

    equity = 1000.0
    peak = equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        if peak > 0.0:
            max_dd = max(max_dd, (peak - equity) / peak)

    return {
        "trades": float(len(pnls)),
        "winrate": wins / len(pnls),
        "expectancy": expectancy,
        "avgR": avg_r,
        "maxDD": max_dd * 100.0,
    }


def reject_distribution(rows: List[Dict[str, str]]) -> Dict[str, int]:
    cnt = Counter()
    for row in rows:
        code = str(row.get("code") or row.get("reason") or "UNKNOWN").strip() or "UNKNOWN"
        cnt[code] += 1
    return dict(sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])))


def regime_breakdown(decisions: List[Dict[str, str]]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for row in decisions:
        regime = str(row.get("regime", "UNKNOWN")).strip() or "UNKNOWN"
        decision = str(row.get("decision", "UNKNOWN")).strip().upper() or "UNKNOWN"
        if regime not in out:
            out[regime] = {"GO": 0, "BLOCK": 0, "NO_GO": 0, "OTHER": 0}
        if decision in out[regime]:
            out[regime][decision] += 1
        else:
            out[regime]["OTHER"] += 1
    return out


def compute_window_report(
    decisions: List[Dict[str, str]],
    rejects: List[Dict[str, str]],
    trades: List[Dict[str, str]],
) -> Dict[str, Any]:
    m = metrics_from_trades(trades)
    return {
        "trades": int(m["trades"]),
        "winrate": m["winrate"],
        "expectancy": m["expectancy"],
        "avgR": m["avgR"],
        "maxDD": m["maxDD"],
        "reject_distribution": reject_distribution(rejects),
        "regime_breakdown": regime_breakdown(decisions),
    }


def write_markdown(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pct(v: float) -> str:
    return f"{v * 100.0:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly evaluation report for paper run")
    parser.add_argument("--run-dir", type=Path, default=Path("runs/year2/paper_main"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/year2"))
    args = parser.parse_args()

    decisions = load_rows(args.run_dir / "decisions.csv")
    rejects = load_rows(args.run_dir / "rejects.csv")
    trades = load_rows(args.run_dir / "trades.csv")

    now_ts = datetime.now(timezone.utc).timestamp()

    d24 = filter_window(decisions, now_ts, 24 * 3600, ["ts_iso", "bar_ts_iso", "timestamp", "bar_ts"])
    r24 = filter_window(rejects, now_ts, 24 * 3600, ["ts_iso", "bar_ts_iso", "timestamp", "bar_ts"])
    t24 = filter_window(trades, now_ts, 24 * 3600, ["ts_iso", "timestamp"])

    d7 = filter_window(decisions, now_ts, 7 * 24 * 3600, ["ts_iso", "bar_ts_iso", "timestamp", "bar_ts"])
    r7 = filter_window(rejects, now_ts, 7 * 24 * 3600, ["ts_iso", "bar_ts_iso", "timestamp", "bar_ts"])
    t7 = filter_window(trades, now_ts, 7 * 24 * 3600, ["ts_iso", "timestamp"])

    report_24h = compute_window_report(d24, r24, t24)
    report_7d = compute_window_report(d7, r7, t7)

    compare = {
        "expectancy_delta": report_24h["expectancy"] - report_7d["expectancy"],
        "winrate_delta": report_24h["winrate"] - report_7d["winrate"],
        "avgR_delta": report_24h["avgR"] - report_7d["avgR"],
        "maxDD_delta": report_24h["maxDD"] - report_7d["maxDD"],
    }

    metrics_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(args.run_dir),
        "window_24h": report_24h,
        "window_7d": report_7d,
        "compare": compare,
    }

    metrics_out = args.reports_dir / "metrics.json"
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.write_text(json.dumps(metrics_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# Nightly Evaluation",
        "",
        f"Generated: {metrics_payload['generated_at_utc']}",
        f"Run Dir: `{args.run_dir}`",
        "",
        "## 24h vs 7d",
        "",
        "| Metric | 24h | 7d | Delta (24h-7d) |",
        "|---|---:|---:|---:|",
        f"| Trades | {report_24h['trades']} | {report_7d['trades']} | {report_24h['trades'] - report_7d['trades']} |",
        f"| Winrate | {pct(report_24h['winrate'])} | {pct(report_7d['winrate'])} | {pct(compare['winrate_delta'])} |",
        f"| Expectancy | {report_24h['expectancy']:.4f} | {report_7d['expectancy']:.4f} | {compare['expectancy_delta']:.4f} |",
        f"| AvgR | {report_24h['avgR']:.4f} | {report_7d['avgR']:.4f} | {compare['avgR_delta']:.4f} |",
        f"| MaxDD% | {report_24h['maxDD']:.2f} | {report_7d['maxDD']:.2f} | {compare['maxDD_delta']:.2f} |",
        "",
        "## Reject Distribution (24h)",
        "",
        "| Code | Count |",
        "|---|---:|",
    ]

    if report_24h["reject_distribution"]:
        for code, count in report_24h["reject_distribution"].items():
            lines.append(f"| `{code}` | {int(count)} |")
    else:
        lines.append("| `N/A` | 0 |")

    lines.extend(["", "## Regime Breakdown (24h)", "", "| Regime | GO | BLOCK | NO_GO | OTHER |", "|---|---:|---:|---:|---:|"])
    rb24 = report_24h["regime_breakdown"]
    if rb24:
        for regime, items in rb24.items():
            lines.append(
                f"| {regime} | {int(items.get('GO',0))} | {int(items.get('BLOCK',0))} | {int(items.get('NO_GO',0))} | {int(items.get('OTHER',0))} |"
            )
    else:
        lines.append("| UNKNOWN | 0 | 0 | 0 | 0 |")

    nightly_eval_out = args.reports_dir / "nightly_eval.md"
    write_markdown(nightly_eval_out, lines)
    print(f"[nightly_eval] wrote {nightly_eval_out}")
    print(f"[nightly_eval] wrote {metrics_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
