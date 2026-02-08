#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional


STRATEGY_RE = re.compile(r"strategy_id=([A-Za-z0-9_\-]+)")
RISK_VIOLATION_CODES = {
    "REJECT_RISK_CAP",
    "REJECT_KILL_SWITCH",
    "KILL_SWITCH_DD",
    "DAILY_STOP",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        s = str(value).strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_strategy_id(decision_row: Dict[str, str]) -> Optional[str]:
    if "strategy_id" in decision_row and decision_row.get("strategy_id"):
        return str(decision_row.get("strategy_id", "")).strip()
    reasons = str(decision_row.get("reasons", ""))
    m = STRATEGY_RE.search(reasons)
    if m:
        return m.group(1).strip()
    return None


def parse_iso(ts_iso: Optional[str]) -> Optional[datetime]:
    if not ts_iso:
        return None
    try:
        return datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
    except Exception:
        return None


def trade_close_events() -> set[str]:
    return {"CLOSE", "TP", "SL", "STOP", "TIME", "EXIT", "PROFIT", "LOSS"}


def is_closed_trade(row: Dict[str, str]) -> bool:
    event = str(row.get("event", "")).strip().upper()
    if event in {"OPEN", "ENTRY", "REJECTED", ""}:
        return False
    if event in trade_close_events():
        return True
    pnl = safe_float(row.get("pnl"), 0.0)
    return abs(pnl) > 1e-12


def compute_equity_metrics(trades: List[Dict[str, str]], start_balance: float) -> Dict[str, float]:
    closed = [r for r in trades if is_closed_trade(r)]
    if not closed:
        return {
            "closed_trades": 0,
            "win_rate": 0.0,
            "expectancy": 0.0,
            "sharpe": 0.0,
            "max_dd_pct": 0.0,
            "total_pnl": 0.0,
            "avg_trade_return": 0.0,
        }

    equity = max(start_balance, 1.0)
    peak = equity
    max_dd = 0.0
    wins = 0
    pnl_series: List[float] = []
    returns: List[float] = []

    for row in closed:
        pnl = safe_float(row.get("pnl"), 0.0)
        if pnl > 0:
            wins += 1
        pnl_series.append(pnl)

        before = max(equity, 1e-9)
        equity += pnl
        trade_ret = pnl / before
        returns.append(trade_ret)

        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)

    n = len(closed)
    mean_ret = sum(returns) / n if n else 0.0
    variance = sum((r - mean_ret) ** 2 for r in returns) / (n - 1) if n > 1 else 0.0
    std_ret = variance ** 0.5
    sharpe = (mean_ret / std_ret) * (n ** 0.5) if std_ret > 1e-12 else 0.0

    total_pnl = sum(pnl_series)
    expectancy = total_pnl / n if n else 0.0

    return {
        "closed_trades": n,
        "win_rate": wins / n if n else 0.0,
        "expectancy": expectancy,
        "sharpe": sharpe,
        "max_dd_pct": max_dd * 100.0,
        "total_pnl": total_pnl,
        "avg_trade_return": mean_ret,
    }


def compute_slippage_metrics(trades: List[Dict[str, str]]) -> Dict[str, Optional[float]]:
    slips: List[float] = []
    for row in trades:
        if not is_closed_trade(row):
            continue
        if "slip_applied" in row and row.get("slip_applied") not in {None, ""}:
            slips.append(safe_float(row.get("slip_applied"), 0.0))

    if not slips:
        return {"slippage_bps_median": None, "slippage_bps_p95": None}

    sorted_slips = sorted(slips)
    idx = min(len(sorted_slips) - 1, int(0.95 * (len(sorted_slips) - 1)))
    return {
        "slippage_bps_median": float(median(sorted_slips)),
        "slippage_bps_p95": float(sorted_slips[idx]),
    }


def compute_drift_bps(decisions: List[Dict[str, str]], trades: List[Dict[str, str]]) -> Optional[float]:
    expected = [
        safe_float(r.get("exp_move"), 0.0)
        for r in decisions
        if str(r.get("decision", "")).upper() == "GO"
    ]
    realized: List[float] = []
    for row in trades:
        if not is_closed_trade(row):
            continue
        qty = safe_float(row.get("qty"), 0.0)
        px = safe_float(row.get("price"), 0.0)
        notional = abs(qty * px)
        pnl = safe_float(row.get("pnl"), 0.0)
        if notional > 0:
            realized.append((pnl / notional) * 10000.0)

    if not expected or not realized:
        return None

    k = min(len(expected), len(realized))
    drifts = [realized[i] - expected[i] for i in range(k)]
    return float(median(drifts)) if drifts else None


def compute_regime_stats(decisions: List[Dict[str, str]]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for row in decisions:
        regime = str(row.get("regime", "UNKNOWN")).strip() or "UNKNOWN"
        dec = str(row.get("decision", "UNKNOWN")).strip().upper() or "UNKNOWN"
        if regime not in out:
            out[regime] = {"GO": 0, "BLOCK": 0, "NO_GO": 0, "OTHER": 0}
        if dec in out[regime]:
            out[regime][dec] += 1
        else:
            out[regime]["OTHER"] += 1
    return out


def infer_strategy(decisions: List[Dict[str, str]], daemon_state: Dict[str, Any]) -> str:
    for row in reversed(decisions):
        sid = parse_strategy_id(row)
        if sid:
            return sid

    cfg_snap = daemon_state.get("config_snapshot", {}) if isinstance(daemon_state, dict) else {}
    strategy_raw = str(cfg_snap.get("strategy", "")).strip().lower()
    if strategy_raw == "tophunter_short_v1":
        return "TOPHUNTER_SHORT_V1"
    if strategy_raw:
        return strategy_raw.upper()
    return "COUNCIL_BASELINE"


def compute_metrics(run_dir: Path, start_balance_override: Optional[float] = None) -> Dict[str, Any]:
    decisions = load_csv_rows(run_dir / "decisions.csv")
    rejects = load_csv_rows(run_dir / "rejects.csv")
    trades = load_csv_rows(run_dir / "trades.csv")

    heartbeat = load_json(run_dir / "heartbeat.json")
    daemon_state = load_json(run_dir / "daemon_state.json")

    start_balance = start_balance_override
    if start_balance is None:
        cfg_snap = daemon_state.get("config_snapshot", {}) if isinstance(daemon_state, dict) else {}
        start_balance = safe_float(cfg_snap.get("start_balance"), 0.0)
    if not start_balance:
        start_balance = 1000.0

    equity_m = compute_equity_metrics(trades, start_balance)
    slip_m = compute_slippage_metrics(trades)
    drift_bps = compute_drift_bps(decisions, trades)

    bars_seen = int(
        heartbeat.get("counters", {}).get("bars_seen", 0)
        if isinstance(heartbeat, dict)
        else 0
    )
    decisions_total = len(decisions)
    rejects_total = len(rejects)
    bars_denom = max(bars_seen, decisions_total)
    error_rate_pct = ((rejects_total / bars_denom) * 100.0) if bars_denom > 0 else 0.0

    reject_codes = Counter()
    for row in rejects:
        code = str(row.get("code") or row.get("reason") or "UNKNOWN").strip() or "UNKNOWN"
        reject_codes[code] += 1

    violations = sum(reject_codes.get(code, 0) for code in RISK_VIOLATION_CODES)

    hb_ts = parse_iso(heartbeat.get("ts_iso") if isinstance(heartbeat, dict) else None)
    stale_seconds = None
    if hb_ts is not None:
        now = datetime.now(tz=hb_ts.tzinfo) if hb_ts.tzinfo else datetime.now()
        stale_seconds = (now - hb_ts).total_seconds()

    strategy_id = infer_strategy(decisions, daemon_state)

    out: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "strategy_id": strategy_id,
        "bars_seen": bars_seen,
        "bars_denom": bars_denom,
        "decisions_total": decisions_total,
        "rejects_total": rejects_total,
        "error_rate_pct": error_rate_pct,
        "telemetry_stale_seconds": stale_seconds,
        "telemetry_stable": bool(stale_seconds is not None and stale_seconds <= 180.0),
        "trades_closed": equity_m["closed_trades"],
        "win_rate": equity_m["win_rate"],
        "expectancy": equity_m["expectancy"],
        "sharpe": equity_m["sharpe"],
        "max_dd_pct": equity_m["max_dd_pct"],
        "total_pnl": equity_m["total_pnl"],
        "avg_trade_return": equity_m["avg_trade_return"],
        "slippage_bps_median": slip_m["slippage_bps_median"],
        "slippage_bps_p95": slip_m["slippage_bps_p95"],
        "drift_bps_median": drift_bps,
        "reject_distribution": dict(sorted(reject_codes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "regime_stats": compute_regime_stats(decisions),
        "risk_violations": violations,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Year-2 metrics JSON from run telemetry")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start-balance", type=float, default=None)
    args = parser.parse_args()

    metrics = compute_metrics(args.run_dir, start_balance_override=args.start_balance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[year2-metrics] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
