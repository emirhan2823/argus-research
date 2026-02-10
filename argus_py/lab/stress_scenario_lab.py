from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
import csv
import json
import math
import random


@dataclass(frozen=True)
class StressScenarioResult:
    name: str
    trades: int
    win_rate: float
    expectancy: float
    sharpe: float
    max_dd_pct: float
    total_pnl: float


@dataclass(frozen=True)
class StressScenarioReport:
    generated_at_utc: str
    run_dir: str
    scenarios: List[StressScenarioResult]

    def to_json(self) -> Dict[str, object]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "run_dir": self.run_dir,
            "scenarios": [s.__dict__ for s in self.scenarios],
        }


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def load_closed_pnls(run_dir: Path) -> List[float]:
    path = Path(run_dir) / "trades.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        out: List[float] = []
        for row in reader:
            event = str(row.get("event", "")).upper()
            if event in {"REJECTED", "OPEN", "ENTRY", "SIGNAL"}:
                continue
            pnl = _safe_float(row.get("pnl"), 0.0)
            if abs(pnl) <= 1e-12:
                continue
            out.append(pnl)
        return out


def _scenario_transform(base: Sequence[float], scenario: str) -> List[float]:
    name = str(scenario).lower().strip()
    if name == "baseline":
        return list(base)
    if name == "fee_slippage_x2":
        return [float(p) - (abs(float(p)) * 0.06) for p in base]
    if name == "latency_shock":
        return [float(p) - (0.25 * abs(float(p))) for p in base]
    if name == "gap_down":
        return [float(p) * (0.70 if float(p) < 0 else 0.90) for p in base]
    if name == "loss_cluster":
        rng = random.Random(42)
        vals = list(base)
        rng.shuffle(vals)
        return [float(p) * (1.35 if float(p) < 0 else 0.85) for p in vals]
    raise ValueError(f"Unknown scenario: {scenario}")


def _stats(pnls: Sequence[float], scenario: str) -> StressScenarioResult:
    vals = [float(x) for x in pnls]
    trades = len(vals)
    if trades == 0:
        return StressScenarioResult(
            name=scenario,
            trades=0,
            win_rate=0.0,
            expectancy=0.0,
            sharpe=0.0,
            max_dd_pct=0.0,
            total_pnl=0.0,
        )

    total_pnl = float(sum(vals))
    wins = sum(1 for x in vals if x > 0)
    win_rate = wins / trades
    expectancy = total_pnl / trades
    std = float(math.sqrt(sum((x - expectancy) ** 2 for x in vals) / max(1, trades - 1))) if trades > 1 else 0.0
    sharpe = (expectancy / std) if std > 1e-12 else 0.0

    equity = 1000.0
    peak = equity
    max_dd = 0.0
    for pnl in vals:
        equity += pnl
        peak = max(peak, equity)
        dd = ((peak - equity) / peak) * 100.0 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    return StressScenarioResult(
        name=scenario,
        trades=trades,
        win_rate=float(win_rate),
        expectancy=float(expectancy),
        sharpe=float(sharpe),
        max_dd_pct=float(max_dd),
        total_pnl=float(total_pnl),
    )


def run_stress_scenario_lab(run_dir: Path, scenarios: Iterable[str] | None = None) -> StressScenarioReport:
    run_dir = Path(run_dir)
    base = load_closed_pnls(run_dir)
    scenario_list = list(scenarios or ["baseline", "fee_slippage_x2", "latency_shock", "gap_down", "loss_cluster"])
    results: List[StressScenarioResult] = []
    for scenario in scenario_list:
        variant = _scenario_transform(base, scenario)
        results.append(_stats(variant, scenario))

    return StressScenarioReport(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        run_dir=str(run_dir),
        scenarios=results,
    )


def write_stress_report(report: StressScenarioReport, *, out_md: Path, out_json: Path) -> Tuple[Path, Path]:
    out_md = Path(out_md)
    out_json = Path(out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Stress Scenario Lab",
        "",
        f"Generated: {report.generated_at_utc}",
        f"Run Dir: `{report.run_dir}`",
        "",
        "| Scenario | Trades | Win% | Expectancy | Sharpe | MaxDD% | TotalPnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report.scenarios:
        lines.append(
            f"| `{row.name}` | {row.trades} | {row.win_rate:.2%} | {row.expectancy:.6f} | {row.sharpe:.4f} | {row.max_dd_pct:.4f} | {row.total_pnl:.6f} |"
        )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_json.write_text(json.dumps(report.to_json(), ensure_ascii=True, indent=2), encoding="utf-8")
    return out_md, out_json


__all__ = [
    "StressScenarioReport",
    "StressScenarioResult",
    "load_closed_pnls",
    "run_stress_scenario_lab",
    "write_stress_report",
]
