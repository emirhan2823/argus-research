from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _is_closed_trade(row: Dict[str, str]) -> bool:
    event = str(row.get("event", "")).strip().upper()
    if event in {"OPEN", "ENTRY", "REJECTED", ""}:
        return False
    pnl = _safe_float(row.get("pnl"), 0.0)
    if event in {"CLOSE", "TP", "SL", "STOP", "TIME", "EXIT", "PROFIT", "LOSS"}:
        return True
    return abs(pnl) > 1e-12


@dataclass(frozen=True)
class TradeCostSummary:
    generated_at_utc: str
    run_dir: str
    closed_trades: int
    total_pnl: float
    total_commission: float
    total_slippage_cost: float
    total_cost: float
    cost_to_abs_pnl_ratio: Optional[float]
    median_slippage_bps: Optional[float]
    p95_slippage_bps: Optional[float]
    median_spread_bps: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "run_dir": self.run_dir,
            "closed_trades": self.closed_trades,
            "total_pnl": self.total_pnl,
            "total_commission": self.total_commission,
            "total_slippage_cost": self.total_slippage_cost,
            "total_cost": self.total_cost,
            "cost_to_abs_pnl_ratio": self.cost_to_abs_pnl_ratio,
            "median_slippage_bps": self.median_slippage_bps,
            "p95_slippage_bps": self.p95_slippage_bps,
            "median_spread_bps": self.median_spread_bps,
        }


def analyze_trade_costs(run_dir: Path) -> TradeCostSummary:
    trades_path = Path(run_dir) / "trades.csv"
    if not trades_path.exists():
        return TradeCostSummary(
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            run_dir=str(run_dir),
            closed_trades=0,
            total_pnl=0.0,
            total_commission=0.0,
            total_slippage_cost=0.0,
            total_cost=0.0,
            cost_to_abs_pnl_ratio=None,
            median_slippage_bps=None,
            p95_slippage_bps=None,
            median_spread_bps=None,
        )

    with trades_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    closed = [row for row in rows if _is_closed_trade(row)]
    if not closed:
        return TradeCostSummary(
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            run_dir=str(run_dir),
            closed_trades=0,
            total_pnl=0.0,
            total_commission=0.0,
            total_slippage_cost=0.0,
            total_cost=0.0,
            cost_to_abs_pnl_ratio=None,
            median_slippage_bps=None,
            p95_slippage_bps=None,
            median_spread_bps=None,
        )

    total_pnl = 0.0
    total_commission = 0.0
    total_slippage_cost = 0.0
    slip_bps: List[float] = []
    spread_bps: List[float] = []

    for row in closed:
        pnl = _safe_float(row.get("pnl"), 0.0)
        qty = abs(_safe_float(row.get("qty") or row.get("quantity"), 0.0))
        mark_price = _safe_float(row.get("mark_price") or row.get("price"), 0.0)
        commission = _safe_float(row.get("commission"), 0.0)
        slip = _safe_float(row.get("slip_applied"), 0.0)
        spread = _safe_float(row.get("spread_applied"), 0.0)

        notional = qty * mark_price
        slippage_cost = notional * (abs(slip) / 10000.0)

        total_pnl += pnl
        total_commission += commission
        total_slippage_cost += slippage_cost
        if slip != 0.0:
            slip_bps.append(slip)
        if spread != 0.0:
            spread_bps.append(spread)

    total_cost = total_commission + total_slippage_cost
    denom = abs(total_pnl)
    ratio = (total_cost / denom) if denom > 1e-12 else None

    med_slip = median(sorted(slip_bps)) if slip_bps else None
    p95_slip = None
    if slip_bps:
        sorted_slip = sorted(slip_bps)
        idx = min(len(sorted_slip) - 1, int(0.95 * (len(sorted_slip) - 1)))
        p95_slip = sorted_slip[idx]
    med_spread = median(sorted(spread_bps)) if spread_bps else None

    return TradeCostSummary(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        run_dir=str(run_dir),
        closed_trades=len(closed),
        total_pnl=total_pnl,
        total_commission=total_commission,
        total_slippage_cost=total_slippage_cost,
        total_cost=total_cost,
        cost_to_abs_pnl_ratio=ratio,
        median_slippage_bps=med_slip,
        p95_slippage_bps=p95_slip,
        median_spread_bps=med_spread,
    )


def write_trade_cost_report(run_dir: Path, out_md: Path, out_json: Optional[Path] = None) -> TradeCostSummary:
    summary = analyze_trade_costs(run_dir)
    lines = [
        "# Trade Cost Analysis",
        "",
        f"Generated: {summary.generated_at_utc}",
        f"Run Dir: `{run_dir}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Closed Trades | {summary.closed_trades} |",
        f"| Total PnL | {summary.total_pnl:.6f} |",
        f"| Total Commission | {summary.total_commission:.6f} |",
        f"| Total Slippage Cost | {summary.total_slippage_cost:.6f} |",
        f"| Total Cost | {summary.total_cost:.6f} |",
        f"| Cost / |PnL| | {summary.cost_to_abs_pnl_ratio:.4f} |" if summary.cost_to_abs_pnl_ratio is not None else "| Cost / |PnL| | N/A |",
        f"| Median Slippage (bps) | {summary.median_slippage_bps:.4f} |" if summary.median_slippage_bps is not None else "| Median Slippage (bps) | N/A |",
        f"| P95 Slippage (bps) | {summary.p95_slippage_bps:.4f} |" if summary.p95_slippage_bps is not None else "| P95 Slippage (bps) | N/A |",
        f"| Median Spread (bps) | {summary.median_spread_bps:.4f} |" if summary.median_spread_bps is not None else "| Median Spread (bps) | N/A |",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return summary


__all__ = ["TradeCostSummary", "analyze_trade_costs", "write_trade_cost_report"]
