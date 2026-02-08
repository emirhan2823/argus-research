#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Scripts.year2_generate_metrics import compute_metrics, is_closed_trade, safe_float
from argus_py.data.market_state import Bar
from argus_py.reporting.signal_audit import run_audit
from argus_py.strategy.tophunter_short import evaluate_tophunter_short_v1


@dataclass
class TuneParams:
    max_adx: float
    pivot_window: int
    cooldown_bars: int
    tp2_ratio: float
    exp_move_min_bps: float


@dataclass
class TuneResult:
    params: TuneParams
    trades: int
    win_rate: float
    expectancy: float
    sharpe: float
    max_dd_pct: float
    total_pnl: float
    reject_counts: Dict[str, int]


def safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def is_float_token(token: str) -> bool:
    try:
        float(token)
        return True
    except Exception:
        return False


def load_market_bars(data_input: Path) -> List[Bar]:
    files: List[Path]
    if data_input.is_file():
        files = [data_input]
    else:
        files = sorted(data_input.glob("*.csv"))

    out: Dict[float, Bar] = {}
    for path in files:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header_checked = False
            for row in reader:
                if len(row) < 6:
                    continue

                if not header_checked:
                    header_checked = True
                    if not is_float_token(row[0]):
                        continue

                ts = safe_float(row[0], 0.0)
                if ts <= 0:
                    continue
                if ts > 1_000_000_000_000:
                    ts /= 1000.0

                idx = 1
                if len(row) >= 7 and not is_float_token(row[1]):
                    idx = 2
                if len(row) < idx + 5:
                    continue

                o = safe_float(row[idx + 0], 0.0)
                h = safe_float(row[idx + 1], 0.0)
                l = safe_float(row[idx + 2], 0.0)
                c = safe_float(row[idx + 3], 0.0)
                v = safe_float(row[idx + 4], 0.0)
                if min(o, h, l, c) <= 0:
                    continue

                out[ts] = Bar(timestamp=ts, open=o, high=h, low=l, close=c, volume=v)

    bars = sorted(out.values(), key=lambda b: b.timestamp)
    return bars


def slice_last_days(bars: Sequence[Bar], days: int) -> List[Bar]:
    if not bars:
        return []
    end_ts = bars[-1].timestamp
    start_ts = end_ts - (days * 86400)
    sliced = [b for b in bars if b.timestamp >= start_ts]
    return sliced if sliced else list(bars)


def summarize_pnl_series(pnls: List[float], start_equity: float = 1000.0) -> Dict[str, float]:
    if not pnls:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "expectancy": 0.0,
            "sharpe": 0.0,
            "max_dd_pct": 0.0,
            "total_pnl": 0.0,
        }

    equity = start_equity
    peak = equity
    max_dd = 0.0
    wins = 0
    returns: List[float] = []

    for pnl in pnls:
        if pnl > 0:
            wins += 1
        base = max(equity, 1e-9)
        returns.append(pnl / base)
        equity += pnl
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    n = len(pnls)
    mean_ret = sum(returns) / n
    if n > 1:
        variance = sum((r - mean_ret) ** 2 for r in returns) / (n - 1)
        std = variance ** 0.5
    else:
        std = 0.0
    sharpe = (mean_ret / std) * (n ** 0.5) if std > 1e-12 else 0.0

    return {
        "trades": n,
        "win_rate": wins / n,
        "expectancy": sum(pnls) / n,
        "sharpe": sharpe,
        "max_dd_pct": max_dd * 100.0,
        "total_pnl": sum(pnls),
    }


def compute_adx_series(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14
) -> List[Optional[float]]:
    n = len(closes)
    if n == 0:
        return []
    if n == 1:
        return [None]

    tr: List[float] = [0.0] * n
    plus_dm: List[float] = [0.0] * n
    minus_dm: List[float] = [0.0] * n

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        plus_dm[i] = up_move if (up_move > down_move and up_move > 0.0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0.0) else 0.0

        tr0 = abs(highs[i] - lows[i])
        tr1 = abs(highs[i] - closes[i - 1])
        tr2 = abs(lows[i] - closes[i - 1])
        tr[i] = max(tr0, tr1, tr2)

    alpha = 1.0 / float(period)
    atr: List[Optional[float]] = [None] * n
    plus_dm_s: List[Optional[float]] = [None] * n
    minus_dm_s: List[Optional[float]] = [None] * n

    for i in range(1, n):
        if i < period:
            continue
        if i == period:
            atr[i] = sum(tr[1 : period + 1]) / float(period)
            plus_dm_s[i] = sum(plus_dm[1 : period + 1]) / float(period)
            minus_dm_s[i] = sum(minus_dm[1 : period + 1]) / float(period)
            continue

        prev_atr = atr[i - 1] if atr[i - 1] is not None else tr[i]
        prev_plus = plus_dm_s[i - 1] if plus_dm_s[i - 1] is not None else plus_dm[i]
        prev_minus = minus_dm_s[i - 1] if minus_dm_s[i - 1] is not None else minus_dm[i]
        atr[i] = prev_atr + alpha * (tr[i] - prev_atr)
        plus_dm_s[i] = prev_plus + alpha * (plus_dm[i] - prev_plus)
        minus_dm_s[i] = prev_minus + alpha * (minus_dm[i] - prev_minus)

    adx: List[Optional[float]] = [None] * n
    dx_vals: List[Optional[float]] = [None] * n

    for i in range(period, n):
        if atr[i] is None or atr[i] <= 0.0:
            continue
        plus_di = 100.0 * (plus_dm_s[i] or 0.0) / atr[i]
        minus_di = 100.0 * (minus_dm_s[i] or 0.0) / atr[i]
        denom = plus_di + minus_di
        if denom <= 0.0:
            continue
        dx_vals[i] = (abs(plus_di - minus_di) / denom) * 100.0

    for i in range(period, n):
        if i < period * 2 - 1:
            continue
        window = [v for v in dx_vals[(i - period + 1) : i + 1] if v is not None]
        if len(window) < period:
            continue
        if i == period * 2 - 1:
            adx[i] = sum(window) / float(period)
        else:
            prev = adx[i - 1] if adx[i - 1] is not None else (sum(window) / float(period))
            cur_dx = dx_vals[i] if dx_vals[i] is not None else prev
            adx[i] = ((prev * (period - 1)) + cur_dx) / float(period)

    return adx


def run_tophunter_backtest(
    bars: Sequence[Bar],
    params: TuneParams,
    start_equity: float = 1000.0,
    roundtrip_cost_bps: float = 12.0,
) -> TuneResult:
    if len(bars) < 50:
        return TuneResult(
            params=params,
            trades=0,
            win_rate=0.0,
            expectancy=0.0,
            sharpe=0.0,
            max_dd_pct=0.0,
            total_pnl=0.0,
            reject_counts={"INSUFFICIENT_DATA": 1},
        )

    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    closes = [b.close for b in bars]
    adx_series = compute_adx_series(highs, lows, closes, period=14)

    equity = start_equity
    day_start_equity = start_equity
    current_day = None
    daily_stop = False

    cooldown = 0
    position: Optional[Dict[str, float]] = None
    reject_counts: Counter[str] = Counter()
    pnl_series: List[float] = []

    # Need i+1 for next-open entry.
    for i in range(40, len(bars) - 1):
        bar = bars[i]
        next_bar = bars[i + 1]

        day = datetime.fromtimestamp(bar.timestamp, tz=timezone.utc).date()
        if current_day != day:
            current_day = day
            day_start_equity = equity
            daily_stop = False

        daily_dd = ((day_start_equity - equity) / day_start_equity) * 100.0 if day_start_equity > 0 else 0.0
        if daily_dd >= 1.5:
            daily_stop = True

        if position is not None:
            position["bars_held"] += 1.0
            exit_price = None

            if bar.high >= position["stop"]:
                exit_price = position["stop"]
            elif bar.low <= position["tp2"]:
                exit_price = position["tp2"]
            elif position["bars_held"] >= 24:
                exit_price = bar.close

            if exit_price is not None:
                qty = position["qty"]
                entry = position["entry"]
                pnl = (entry - exit_price) * qty
                notional = abs(entry * qty)
                pnl -= notional * (roundtrip_cost_bps / 10000.0)

                equity += pnl
                pnl_series.append(pnl)

                if pnl < 0:
                    cooldown = params.cooldown_bars
                position = None

        if position is not None:
            continue

        if cooldown > 0:
            cooldown -= 1

        adx_value = adx_series[i] if i < len(adx_series) and adx_series[i] is not None else 0.0
        signal = evaluate_tophunter_short_v1(
            bars[: i + 1],
            adx_value=adx_value,
            max_adx=params.max_adx,
            left=params.pivot_window,
            right=params.pivot_window,
        )

        if signal.decision != "GO":
            reject_counts[signal.reason_code] += 1
            continue

        if daily_stop:
            reject_counts["REJECT_RISK_CAP"] += 1
            continue

        if cooldown > 0:
            reject_counts["REJECT_COOLDOWN"] += 1
            continue

        entry = next_bar.open
        atr = signal.atr if signal.atr is not None else (entry * 0.003)
        pivot_high = signal.pivot_high if signal.pivot_high is not None else (entry * 1.002)
        stop = max(pivot_high, entry + (1.2 * atr))
        if stop <= entry:
            reject_counts["REJECT_TRIGGER_NOT_MET"] += 1
            continue

        r = stop - entry
        if r <= 0:
            reject_counts["REJECT_TRIGGER_NOT_MET"] += 1
            continue

        tp2 = entry - (params.tp2_ratio * r)
        expected_move_bps = ((entry - tp2) / entry) * 10000.0 if entry > 0 else 0.0
        if expected_move_bps < params.exp_move_min_bps:
            reject_counts["REJECT_EXP_MOVE_FILTER"] += 1
            continue

        # Keep risk caps unchanged: 0.5% max risk per trade, max concurrent position=1.
        risk_amount = equity * 0.005
        qty = risk_amount / r
        if qty <= 0:
            reject_counts["REJECT_RISK_CAP"] += 1
            continue

        position = {
            "entry": entry,
            "stop": stop,
            "tp2": tp2,
            "qty": qty,
            "bars_held": 0.0,
        }

    metrics = summarize_pnl_series(pnl_series, start_equity=start_equity)
    return TuneResult(
        params=params,
        trades=safe_int(str(metrics["trades"]), 0),
        win_rate=metrics["win_rate"],
        expectancy=metrics["expectancy"],
        sharpe=metrics["sharpe"],
        max_dd_pct=metrics["max_dd_pct"],
        total_pnl=metrics["total_pnl"],
        reject_counts=dict(reject_counts),
    )


def rank_tuning(results: Sequence[TuneResult]) -> List[TuneResult]:
    return sorted(
        results,
        key=lambda r: (
            -r.expectancy,
            -r.sharpe,
            r.max_dd_pct,
            -r.trades,
        ),
    )


def write_markdown(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pct(v: float) -> str:
    return f"{v * 100.0:.2f}%"


def write_weekly_review(metrics: Dict[str, object], out_path: Path) -> None:
    weak_reasons: List[str] = []
    if float(metrics.get("expectancy", 0.0)) <= 0.0:
        weak_reasons.append("negative expectancy")
    if float(metrics.get("win_rate", 0.0)) < 0.40:
        weak_reasons.append("winrate below 40%")
    if float(metrics.get("max_dd_pct", 0.0)) > 6.0:
        weak_reasons.append("maxDD above 6%")
    if float(metrics.get("error_rate_pct", 0.0)) > 0.20:
        weak_reasons.append("error rate above 0.20%")
    if int(metrics.get("trades_closed", 0)) < 30:
        weak_reasons.append("insufficient trade count (<30)")

    status = "WEAK" if weak_reasons else "HEALTHY"

    lines = [
        "# Year-2 Weekly Review",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Run Dir: `{metrics.get('run_dir', '')}`",
        "",
        "## Performance",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Strategy | `{metrics.get('strategy_id', 'UNKNOWN')}` |",
        f"| Closed Trades | {int(metrics.get('trades_closed', 0))} |",
        f"| Win Rate | {pct(float(metrics.get('win_rate', 0.0)))} |",
        f"| Expectancy | {float(metrics.get('expectancy', 0.0)):.4f} |",
        f"| Sharpe | {float(metrics.get('sharpe', 0.0)):.3f} |",
        f"| Max DD | {float(metrics.get('max_dd_pct', 0.0)):.2f}% |",
        f"| Error Rate | {float(metrics.get('error_rate_pct', 0.0)):.3f}% |",
        "",
        "## Reject Distribution",
        "",
        "| Code | Count |",
        "|---|---:|",
    ]

    reject_dist = metrics.get("reject_distribution", {})
    if isinstance(reject_dist, dict) and reject_dist:
        for code, count in reject_dist.items():
            lines.append(f"| `{code}` | {int(count)} |")
    else:
        lines.append("| `N/A` | 0 |")

    lines.extend(
        [
            "",
            "## Regime Stats",
            "",
            "| Regime | GO | BLOCK | NO_GO | OTHER |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    regime_stats = metrics.get("regime_stats", {})
    if isinstance(regime_stats, dict) and regime_stats:
        for regime, item in regime_stats.items():
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {regime} | {int(item.get('GO', 0))} | {int(item.get('BLOCK', 0))} | {int(item.get('NO_GO', 0))} | {int(item.get('OTHER', 0))} |"
            )
    else:
        lines.append("| UNKNOWN | 0 | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Weak Strategy Flag",
            "",
            f"Status: **{status}**",
        ]
    )

    if weak_reasons:
        lines.append("")
        for reason in weak_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("\n- No weak-strategy flags triggered.")

    write_markdown(out_path, lines)


def write_tuning_report(results: Sequence[TuneResult], out_path: Path) -> None:
    ranked = rank_tuning(results)
    top = ranked[:10]

    lines = [
        "# TopHunter Short Tuning (Last 30 Days Paper)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "Risk caps unchanged: maxRiskPerTrade=0.5%, dailyLossCap=1.5%, maxConcurrent=1.",
        "",
        "| Rank | max_adx | pivot | cooldown | tp2_ratio | exp_move_min_bps | trades | winrate | expectancy | sharpe | maxDD% | totalPnL |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for i, r in enumerate(top, start=1):
        p = r.params
        lines.append(
            f"| {i} | {p.max_adx:.1f} | {p.pivot_window} | {p.cooldown_bars} | {p.tp2_ratio:.2f} | {p.exp_move_min_bps:.1f} | {r.trades} | {pct(r.win_rate)} | {r.expectancy:.4f} | {r.sharpe:.3f} | {r.max_dd_pct:.2f} | {r.total_pnl:.2f} |"
        )

    if ranked:
        best = ranked[0]
        lines.extend(
            [
                "",
                "## Recommended Parameter Set",
                "",
                f"- `max_adx={best.params.max_adx:.1f}`",
                f"- `pivot_window={best.params.pivot_window}`",
                f"- `cooldown_bars={best.params.cooldown_bars}`",
                f"- `tp2_ratio={best.params.tp2_ratio:.2f}`",
                f"- `exp_move_min_bps={best.params.exp_move_min_bps:.1f}`",
                f"- Expected expectancy: `{best.expectancy:.4f}` (paper simulation)",
            ]
        )

    write_markdown(out_path, lines)


def write_strategy_governance(
    metrics: Dict[str, object],
    tuning_best: Optional[TuneResult],
    out_path: Path,
    disable_path: Path,
) -> None:
    strategy_id = str(metrics.get("strategy_id", "COUNCIL_BASELINE"))
    expectancy = float(metrics.get("expectancy", 0.0))
    win_rate = float(metrics.get("win_rate", 0.0))
    trades = int(metrics.get("trades_closed", 0))

    if trades < 30:
        cls = "REFINE"
        reason = "trade_count_below_threshold"
    elif expectancy < 0.0:
        cls = "KILL"
        reason = "negative_expectancy"
    elif win_rate >= 0.45 and expectancy > 0.0:
        cls = "KEEP"
        reason = "stable_positive_profile"
    else:
        cls = "REFINE"
        reason = "needs_parameter_refinement"

    disabled: Dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "disabled_strategies": [],
    }
    if expectancy < 0.0:
        disabled["disabled_strategies"] = [
            {
                "strategy_id": strategy_id,
                "reason": "negative_expectancy",
                "expectancy": expectancy,
            }
        ]

    disable_path.parent.mkdir(parents=True, exist_ok=True)
    disable_path.write_text(json.dumps(disabled, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# Strategy Governance",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Strategy | Class | Reason | Trades | WinRate | Expectancy |",
        "|---|---|---|---:|---:|---:|",
        f"| `{strategy_id}` | **{cls}** | `{reason}` | {trades} | {pct(win_rate)} | {expectancy:.4f} |",
        "",
        "## Auto-Disable Decisions",
        "",
    ]

    if disabled["disabled_strategies"]:
        lines.append(f"- Disabled: `{strategy_id}` due to negative expectancy.")
    else:
        lines.append("- No strategy auto-disabled in this cycle.")

    if tuning_best is not None:
        p = tuning_best.params
        lines.extend(
            [
                "",
                "## Refine Inputs",
                "",
                f"- Suggested params from tuning: `max_adx={p.max_adx:.1f}`, `pivot={p.pivot_window}`, `cooldown={p.cooldown_bars}`, `tp2_ratio={p.tp2_ratio:.2f}`, `exp_move_min_bps={p.exp_move_min_bps:.1f}`",
            ]
        )

    write_markdown(out_path, lines)


def write_micro_live_gate(metrics: Dict[str, object], out_path: Path, runbook_path: Path) -> None:
    checks = [
        ("trades>=100", int(metrics.get("trades_closed", 0)) >= 100),
        ("expectancy>0", float(metrics.get("expectancy", 0.0)) > 0.0),
        ("stable_telemetry", bool(metrics.get("telemetry_stable", False))),
        ("error_rate<=0.20%", float(metrics.get("error_rate_pct", 0.0)) <= 0.20),
        ("no_risk_violations", int(metrics.get("risk_violations", 0)) == 0),
    ]
    passed = all(ok for _, ok in checks)

    lines = [
        "# Paper to Micro-Live Readiness",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Overall Gate: **{'PASS' if passed else 'FAIL'}**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for name, ok in checks:
        lines.append(f"| `{name}` | {'PASS' if ok else 'FAIL'} |")

    blockers = [name for name, ok in checks if not ok]
    if blockers:
        lines.extend(["", "## Blockers", ""])
        for b in blockers:
            lines.append(f"- `{b}`")
    else:
        lines.extend(["", "## Promotion", "", "- Gate passed. Micro-live runbook generated."])

    write_markdown(out_path, lines)

    if passed:
        runbook_lines = [
            "# Micro-Live Runbook",
            "",
            "## Start",
            "",
            "```bash",
            "venv/bin/python -m argus_py.runner.live_cli \\",
            "  --exchange bingx \\",
            "  --symbol BTCUSDT \\",
            "  --tf 15m \\",
            "  --mode dry_run \\",
            "  --profile AUTO \\",
            "  --poll_seconds 30 \\",
            "  --max_daily_loss_pct 0.02 \\",
            "  --max_dd_pct 0.05 \\",
            "  --max_consecutive_losses 3",
            "```",
            "",
            "## Snapshot to Year-2",
            "",
            "```bash",
            "rsync -av runs/live/ runs/year2/micro_live_main/",
            "```",
            "",
            "## Fallback",
            "",
            "- Kill-switch `SOFT`: block new entries, continue monitoring.",
            "- Kill-switch `HARD`: close all and stop daemon.",
            "- Telemetry stale > 180s: restart supervisor profile and re-check heartbeat.",
        ]
        write_markdown(runbook_path, runbook_lines)


def load_closed_trade_pnls(run_dir: Path) -> List[float]:
    trades = []
    with (run_dir / "trades.csv").open("r", newline="", encoding="utf-8") as f:
        trades = list(csv.DictReader(f))
    return [safe_float(r.get("pnl"), 0.0) for r in trades if is_closed_trade(r)]


def stress_variant(base: List[float], mode: str) -> List[float]:
    if mode == "fee_slippage_x2":
        return [p * 0.75 for p in base]
    if mode == "latency_shock":
        return [p * 0.85 for p in base]
    if mode == "gap_down":
        out = []
        for p in base:
            if p < 0:
                out.append(p * 1.30)
            else:
                out.append(p * 0.90)
        return out
    return list(base)


def monte_carlo_dd_probability(base: List[float], threshold_pct: float, runs: int = 300) -> float:
    if not base:
        return 0.0
    rng = Random(42)
    breaches = 0
    for _ in range(runs):
        seq = [base[rng.randrange(0, len(base))] for _ in range(len(base))]
        dd = summarize_pnl_series(seq, start_equity=1000.0)["max_dd_pct"]
        if dd > threshold_pct:
            breaches += 1
    return breaches / runs


def write_night_cycle(run_dir: Path, metrics: Dict[str, object], tuning_best: Optional[TuneResult], out_path: Path) -> None:
    base_pnls = []
    if (run_dir / "trades.csv").exists():
        base_pnls = load_closed_trade_pnls(run_dir)

    base_stats = summarize_pnl_series(base_pnls, start_equity=1000.0)
    stress_modes = ["fee_slippage_x2", "latency_shock", "gap_down"]

    lines = [
        "# Night Research Cycle",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Run Dir: `{run_dir}`",
        "",
        "## Stress Tests",
        "",
        "| Scenario | Trades | Expectancy | Sharpe | MaxDD% | TotalPnL |",
        "|---|---:|---:|---:|---:|---:|",
        f"| baseline | {int(base_stats['trades'])} | {base_stats['expectancy']:.4f} | {base_stats['sharpe']:.3f} | {base_stats['max_dd_pct']:.2f} | {base_stats['total_pnl']:.2f} |",
    ]

    for mode in stress_modes:
        variant = stress_variant(base_pnls, mode)
        st = summarize_pnl_series(variant, start_equity=1000.0)
        lines.append(
            f"| {mode} | {int(st['trades'])} | {st['expectancy']:.4f} | {st['sharpe']:.3f} | {st['max_dd_pct']:.2f} | {st['total_pnl']:.2f} |"
        )

    dd_breach_prob = monte_carlo_dd_probability(base_pnls, threshold_pct=8.0, runs=300)
    lines.extend(
        [
            "",
            "## Scenario Simulation",
            "",
            f"- Monte Carlo P(maxDD > 8%): **{pct(dd_breach_prob)}**",
        ]
    )

    audit = run_audit(str(run_dir))
    lines.extend(["", "## Audit Regeneration", ""])
    if audit is None:
        lines.append("- Signal audit skipped: required CSV set not found.")
    else:
        lines.append(
            f"- Signals: {audit.total_signals}, Trades: {audit.total_trades}, Rejects: {audit.total_rejects}, Conversion: {audit.overall_conversion*100:.1f}%"
        )

    lines.extend(["", "## Next-Day Plan", ""])
    if float(metrics.get("expectancy", 0.0)) <= 0.0:
        lines.append("- Prioritize parameter refinement before scaling activity.")
    else:
        lines.append("- Keep current profile and monitor drift in first 2 sessions.")
    if tuning_best is not None:
        p = tuning_best.params
        lines.append(
            f"- Trial config (paper-only): max_adx={p.max_adx:.1f}, pivot={p.pivot_window}, cooldown={p.cooldown_bars}, tp2_ratio={p.tp2_ratio:.2f}, exp_move_min_bps={p.exp_move_min_bps:.1f}."
        )
    lines.append("- Regenerate weekly review after next session close.")

    write_markdown(out_path, lines)


def write_supervisor_integration(out_path: Path) -> None:
    lines = [
        "# Supervisor Integration Status",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Profiles prepared: `STRICT`, `SOFT`, `TOPHUNTER`.",
        "",
        "Fallback rules:",
        "- If a profile exceeds restart budget, keep other profiles running and mark degraded mode.",
        "- If heartbeat is stale (>180s), restart only affected profile.",
        "- If TOPHUNTER fails, continue STRICT+SOFT and log incident for morning review.",
    ]
    write_markdown(out_path, lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Argus Year-2 Autopilot (Research/Evaluate/Refine/Gate)")
    parser.add_argument("--run-dir", type=Path, default=Path("runs/overnight_paper_live"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/BTCUSDT/1h"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/year2"))
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    args.reports_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1
    metrics = compute_metrics(args.run_dir)
    metrics_out = args.reports_dir / "nightly" / datetime.now().strftime("%Y%m%d") / "metrics.json"
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.write_text(json.dumps(metrics, ensure_ascii=True, indent=2), encoding="utf-8")
    write_weekly_review(metrics, args.reports_dir / "weekly_review.md")

    # Phase 2
    bars = slice_last_days(load_market_bars(args.data_dir), args.days)
    grid: List[TuneResult] = []
    for max_adx, pivot, cooldown, tp2, exp_move_min in itertools.product(
        [16.0, 18.0, 20.0],
        [2, 3],
        [2, 3, 4],
        [1.6, 2.0, 2.4],
        [8.0, 12.0, 16.0, 20.0],
    ):
        params = TuneParams(
            max_adx=max_adx,
            pivot_window=pivot,
            cooldown_bars=cooldown,
            tp2_ratio=tp2,
            exp_move_min_bps=exp_move_min,
        )
        grid.append(run_tophunter_backtest(bars, params))

    ranked = rank_tuning(grid)
    best = ranked[0] if ranked else None
    write_tuning_report(grid, args.reports_dir / "tophunter_tuning.md")

    # Phase 3
    governance_disable = Path("runs/year2/governance/disabled_strategies.json")
    write_strategy_governance(
        metrics,
        tuning_best=best,
        out_path=args.reports_dir / "strategy_governance.md",
        disable_path=governance_disable,
    )

    # Phase 4
    write_micro_live_gate(
        metrics,
        out_path=args.reports_dir / "micro_live_ready.md",
        runbook_path=args.reports_dir / "micro_live_runbook.md",
    )

    # Phase 5
    write_night_cycle(
        args.run_dir,
        metrics,
        tuning_best=best,
        out_path=args.reports_dir / "night_cycle.md",
    )

    # Phase 6 artifact
    write_supervisor_integration(args.reports_dir / "supervisor_integration.md")

    print("[autopilot] reports generated under", args.reports_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
