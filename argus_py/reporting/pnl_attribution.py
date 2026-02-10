from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
import csv
import json


@dataclass(frozen=True)
class AttributionBucket:
    key: str
    trades: int
    wins: int
    losses: int
    realized_pnl: float
    avg_pnl: float
    win_rate: float


@dataclass(frozen=True)
class PnLAttributionReport:
    generated_at_utc: str
    run_dir: str
    total_realized_pnl: float
    total_closed_trades: int
    by_strategy: List[AttributionBucket]
    by_asset_class: List[AttributionBucket]
    by_venue: List[AttributionBucket]

    def to_json(self) -> Dict[str, object]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "run_dir": self.run_dir,
            "total_realized_pnl": self.total_realized_pnl,
            "total_closed_trades": self.total_closed_trades,
            "by_strategy": [asdict(x) for x in self.by_strategy],
            "by_asset_class": [asdict(x) for x in self.by_asset_class],
            "by_venue": [asdict(x) for x in self.by_venue],
        }


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _closed_trade_rows(trades_csv: Path) -> Iterable[Dict[str, str]]:
    if not trades_csv.exists():
        return []
    with trades_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    out: List[Dict[str, str]] = []
    for row in rows:
        event = str(row.get("event", "")).upper()
        if event in {"REJECTED", "OPEN", "ENTRY", "SIGNAL"}:
            continue
        pnl = _safe_float(row.get("pnl"), 0.0)
        if abs(pnl) <= 1e-12:
            continue
        out.append(row)
    return out


def _aggregate(rows: Iterable[Dict[str, str]], key_name: str, default_key: str) -> List[AttributionBucket]:
    agg: Dict[str, Dict[str, float]] = {}
    for row in rows:
        key = str(row.get(key_name) or default_key).strip() or default_key
        pnl = _safe_float(row.get("pnl"), 0.0)
        if key not in agg:
            agg[key] = {"trades": 0.0, "wins": 0.0, "losses": 0.0, "realized_pnl": 0.0}
        bucket = agg[key]
        bucket["trades"] += 1.0
        bucket["realized_pnl"] += pnl
        if pnl > 0:
            bucket["wins"] += 1.0
        elif pnl < 0:
            bucket["losses"] += 1.0

    result: List[AttributionBucket] = []
    for key, bucket in agg.items():
        trades = int(bucket["trades"])
        wins = int(bucket["wins"])
        losses = int(bucket["losses"])
        realized = float(bucket["realized_pnl"])
        avg = realized / trades if trades else 0.0
        win_rate = (wins / trades) if trades else 0.0
        result.append(
            AttributionBucket(
                key=key,
                trades=trades,
                wins=wins,
                losses=losses,
                realized_pnl=realized,
                avg_pnl=avg,
                win_rate=win_rate,
            )
        )
    result.sort(key=lambda x: x.realized_pnl, reverse=True)
    return result


def compute_pnl_attribution(run_dir: Path) -> PnLAttributionReport:
    run_dir = Path(run_dir)
    trades_path = run_dir / "trades.csv"
    rows = list(_closed_trade_rows(trades_path))
    total_pnl = sum(_safe_float(r.get("pnl"), 0.0) for r in rows)
    total_trades = len(rows)
    by_strategy = _aggregate(rows, "strategy_id", "UNKNOWN_STRATEGY")
    by_asset_class = _aggregate(rows, "asset_class", "unknown")
    by_venue = _aggregate(rows, "venue_id", "unknown")
    return PnLAttributionReport(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        run_dir=str(run_dir),
        total_realized_pnl=float(total_pnl),
        total_closed_trades=int(total_trades),
        by_strategy=by_strategy,
        by_asset_class=by_asset_class,
        by_venue=by_venue,
    )


def write_pnl_attribution_report(
    report: PnLAttributionReport,
    *,
    out_md: Path,
    out_json: Path,
) -> Tuple[Path, Path]:
    out_md = Path(out_md)
    out_json = Path(out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    def _rows(title: str, buckets: List[AttributionBucket]) -> List[str]:
        lines = [f"## {title}", "", "| Key | Trades | Win% | Realized PnL | Avg PnL |", "|---|---:|---:|---:|---:|"]
        if not buckets:
            lines.append("| - | 0 | 0.00% | 0.000000 | 0.000000 |")
        for item in buckets:
            lines.append(
                f"| `{item.key}` | {item.trades} | {item.win_rate:.2%} | {item.realized_pnl:.6f} | {item.avg_pnl:.6f} |"
            )
        lines.append("")
        return lines

    lines = [
        "# PnL Attribution",
        "",
        f"Generated: {report.generated_at_utc}",
        f"Run Dir: `{report.run_dir}`",
        "",
        "## Summary",
        "",
        f"- Total closed trades: `{report.total_closed_trades}`",
        f"- Total realized PnL: `{report.total_realized_pnl:.6f}`",
        "",
    ]
    lines.extend(_rows("By Strategy", report.by_strategy))
    lines.extend(_rows("By Asset Class", report.by_asset_class))
    lines.extend(_rows("By Venue", report.by_venue))

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_json.write_text(json.dumps(report.to_json(), ensure_ascii=True, indent=2), encoding="utf-8")
    return out_md, out_json


__all__ = [
    "AttributionBucket",
    "PnLAttributionReport",
    "compute_pnl_attribution",
    "write_pnl_attribution_report",
]
