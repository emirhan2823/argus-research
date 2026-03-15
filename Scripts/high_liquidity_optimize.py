#!/usr/bin/env python3
"""BTC/ETH high-liquidity optimization runner (1h + 15m).

Runs baseline and candidate backtests, compares return-driven performance
with drawdown guardrail, and writes winner policy/config artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.replay_loader import ReplayLoader  # noqa: E402


@dataclass(frozen=True)
class Candidate:
    name: str
    hydra_mode_15m: str
    confluence_offset: float
    precision_min_grade: str
    rr_offset: float
    grade_c_min_conf: float


@dataclass(frozen=True)
class RunMetrics:
    timeframe: str
    candidate: str
    return_code: int
    trades: int
    win_rate: float
    total_return: float
    profit_factor: float
    max_drawdown: float
    long_trades: int
    short_trades: int
    top_reasons: list[tuple[str, int]]
    run_dir: Path
    db_path: Path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize BTC/ETH high-liquidity policy.")
    parser.add_argument("--replay-start", default="2024-02-24T00:00:00Z")
    parser.add_argument("--replay-end", default="2024-03-26T23:00:00Z")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    parser.add_argument("--timeframes", default="1h,15m")
    parser.add_argument("--run-root", default="runs/high_liquidity_optimize")
    parser.add_argument("--strategy-profiles-config", default="config/strategy_profiles.yaml")
    parser.add_argument("--liquidity-policy-config", default="config/high_liquidity_filters.yaml")
    parser.add_argument("--max-candidates", type=int, default=None, help="Optional cap for quick sweeps.")
    parser.add_argument("--main-timeout-seconds", type=int, default=7200)
    parser.add_argument("--risk-profile", choices=["strict", "normal", "relaxed"], default="normal")
    parser.add_argument(
        "--apply-winner",
        action="store_true",
        default=False,
        help="Persist winner into config/high_liquidity_filters.yaml and strategy_profiles metadata.",
    )
    parser.add_argument("--ensure-eth-15m-backfill", action="store_true", default=True)
    parser.add_argument("--no-ensure-eth-15m-backfill", dest="ensure_eth_15m_backfill", action="store_false")
    parser.add_argument("--backfill-start", default="2024-02-01")
    parser.add_argument("--backfill-end", default="2024-03-31")
    return parser.parse_args(argv)


def _norm_symbol(symbol: str) -> str:
    return str(symbol or "").upper().replace("/", "").replace("-", "").replace("_", "")


def _parse_symbols(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        sym = _norm_symbol(part)
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def _parse_timeframes(raw: str) -> list[str]:
    out: list[str] = []
    for part in str(raw).split(","):
        tf = str(part).strip().lower()
        if tf and tf not in out:
            out.append(tf)
    return out


def _step_for_timeframe(tf: str) -> int:
    if tf == "15m":
        return 15
    if tf == "1h":
        return 60
    return 60


def _parse_iso_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _compute_metrics(db_path: Path, *, timeframe: str, candidate: str, rc: int, run_dir: Path) -> RunMetrics:
    if not db_path.exists():
        return RunMetrics(
            timeframe=timeframe,
            candidate=candidate,
            return_code=rc,
            trades=0,
            win_rate=0.0,
            total_return=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            long_trades=0,
            short_trades=0,
            top_reasons=[],
            run_dir=run_dir,
            db_path=db_path,
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        trades = conn.execute(
            """
            SELECT lower(coalesce(side, '')) AS side, coalesce(net_pnl_pct, 0.0) AS r
            FROM trades
            WHERE exit_time IS NOT NULL
            ORDER BY entry_time
            """
        ).fetchall()
        reasons = conn.execute(
            """
            SELECT reason, count(*) AS c
            FROM decisions
            GROUP BY reason
            ORDER BY c DESC
            LIMIT 10
            """
        ).fetchall()
    finally:
        conn.close()

    rets = [float(r["r"]) for r in trades]
    wins = sum(1 for x in rets if x > 0.0)
    gross_profit = sum(x for x in rets if x > 0.0)
    gross_loss_abs = abs(sum(x for x in rets if x < 0.0))
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0.0 else (float("inf") if gross_profit > 0 else 0.0)

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rets:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    long_trades = sum(1 for r in trades if str(r["side"]) == "long")
    short_trades = sum(1 for r in trades if str(r["side"]) == "short")
    reason_rows = [(str(r["reason"]), int(r["c"])) for r in reasons]

    return RunMetrics(
        timeframe=timeframe,
        candidate=candidate,
        return_code=rc,
        trades=len(rets),
        win_rate=(wins / len(rets)) if rets else 0.0,
        total_return=sum(rets),
        profit_factor=profit_factor,
        max_drawdown=max_dd,
        long_trades=long_trades,
        short_trades=short_trades,
        top_reasons=reason_rows,
        run_dir=run_dir,
        db_path=db_path,
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _apply_candidate(base: dict[str, Any], cand: Candidate) -> dict[str, Any]:
    payload = json.loads(json.dumps(base))
    node = payload.get("high_liquidity_filters", payload)
    if not isinstance(node, dict):
        node = {}
        payload = {"high_liquidity_filters": node}
    node["enabled"] = True
    policies = node.setdefault("policies", {})
    if not isinstance(policies, dict):
        policies = {}
        node["policies"] = policies

    for tf_key in ("1h", "15m"):
        tf_node = policies.setdefault(tf_key, {})
        if not isinstance(tf_node, dict):
            tf_node = {}
            policies[tf_key] = tf_node
        defaults = tf_node.setdefault("defaults", {})
        if not isinstance(defaults, dict):
            defaults = {}
            tf_node["defaults"] = defaults

        precision = defaults.setdefault("precision", {})
        confluence = defaults.setdefault("confluence", {})
        risk = defaults.setdefault("risk", {})
        tq = defaults.setdefault("trade_quality", {})

        precision["min_grade"] = cand.precision_min_grade
        confluence["min_score"] = _clamp(float(confluence.get("min_score", 0.50)) + cand.confluence_offset, 0.30, 0.95)
        risk["min_rr"] = _clamp(float(risk.get("min_rr", 2.0)) + cand.rr_offset, 0.5, 6.0)
        risk["crypto_min_rr"] = _clamp(float(risk.get("crypto_min_rr", 2.0)) + cand.rr_offset, 0.5, 6.0)
        tq["grade_c_min_confidence"] = _clamp(cand.grade_c_min_conf, 0.50, 0.99)

    tf_15m = policies.setdefault("15m", {})
    engines_15m = tf_15m.setdefault("engines", {})
    hydra = engines_15m.setdefault("HYDRA", {})
    hydra["mode"] = cand.hydra_mode_15m
    return payload


def _candidate_grid(max_candidates: int | None) -> list[Candidate]:
    out: list[Candidate] = []
    idx = 0
    for hydra_mode, conf_off, grade, rr_off, c_conf in product(
        ("off", "strict"),
        (0.00, 0.05, 0.10),
        ("D", "C"),
        (0.00, 0.20, 0.40),
        (0.85, 0.80, 0.75),
    ):
        idx += 1
        out.append(
            Candidate(
                name=f"cand_{idx:03d}_{hydra_mode}_co{conf_off:.2f}_pg{grade}_rr{rr_off:.2f}_c{c_conf:.2f}",
                hydra_mode_15m=hydra_mode,
                confluence_offset=conf_off,
                precision_min_grade=grade,
                rr_offset=rr_off,
                grade_c_min_conf=c_conf,
            )
        )
        if max_candidates is not None and len(out) >= max(1, int(max_candidates)):
            break
    return out


def _coverage_ok(symbol: str, timeframe: str, replay_start: str, replay_end: str) -> bool:
    loader = ReplayLoader(root="data/binance")
    try:
        start_day = _parse_iso_utc(replay_start).strftime("%Y-%m-%d")
        end_day = _parse_iso_utc(replay_end).strftime("%Y-%m-%d")
        frame = loader.load_ohlcv(
            symbol=symbol,
            interval=timeframe,
            start=start_day,
            end=end_day,
            verify=False,
        )
    except FileNotFoundError:
        return False
    except ValueError:
        return False
    return not frame.empty


def _ensure_eth_15m_backfill(*, replay_start: str, replay_end: str, backfill_start: str, backfill_end: str) -> tuple[bool, str]:
    if _coverage_ok("ETHUSDT", "15m", replay_start, replay_end):
        return True, "ETHUSDT/15m already available"

    cmd = [
        sys.executable,
        "Scripts/download_historical.py",
        "--symbol",
        "ETHUSDT",
        "--interval",
        "15m",
        "--start",
        backfill_start,
        "--end",
        backfill_end,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, f"backfill command failed rc={proc.returncode}"
    ok = _coverage_ok("ETHUSDT", "15m", replay_start, replay_end)
    return ok, "backfill completed" if ok else "backfill done but replay-window coverage still missing"


def _run_main(
    *,
    run_dir: Path,
    db_path: Path,
    symbols: list[str],
    timeframe: str,
    replay_start: str,
    replay_end: str,
    risk_profile: str,
    strategy_profiles_config: str,
    liquidity_policy_config: Path,
    timeout_s: int,
) -> int:
    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "--mode",
        "backtest",
        "--assets",
        "crypto",
        "--v25",
        "--v25-db",
        str(db_path),
        "--symbols",
        ",".join(symbols),
        "--timeframe",
        timeframe,
        "--replay-start",
        replay_start,
        "--replay-end",
        replay_end,
        "--cycle-step-minutes",
        str(_step_for_timeframe(timeframe)),
        "--risk-profile",
        risk_profile,
        "--run-dir",
        str(run_dir),
        "--strategy-profiles-config",
        str(strategy_profiles_config),
        "--enable-strategy-profiles",
        "--liquidity-policy-config",
        str(liquidity_policy_config),
    ]
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "stdout.log"
    with log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=f,
            stderr=subprocess.STDOUT,
            timeout=max(300, int(timeout_s)),
            check=False,
        )
    return int(proc.returncode)


def _persist_winner_to_strategy_profiles(
    *,
    strategy_profiles_path: Path,
    winner: Candidate,
    replay_start: str,
    replay_end: str,
    run_root: Path,
) -> None:
    payload = _load_yaml(strategy_profiles_path)
    node = payload.get("strategy_profiles", payload)
    if not isinstance(node, dict):
        node = {}
        payload = {"strategy_profiles": node}
    presets = node.setdefault("optimization_presets", {})
    if not isinstance(presets, dict):
        presets = {}
        node["optimization_presets"] = presets
    presets["high_liquidity_btc_eth"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "replay_start": replay_start,
        "replay_end": replay_end,
        "winner_candidate": winner.name,
        "hydra_mode_15m": winner.hydra_mode_15m,
        "confluence_offset": winner.confluence_offset,
        "precision_min_grade": winner.precision_min_grade,
        "rr_offset": winner.rr_offset,
        "grade_c_min_confidence": winner.grade_c_min_conf,
        "reports_root": str(run_root),
    }
    _write_yaml(strategy_profiles_path, payload)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    symbols = _parse_symbols(args.symbols)
    timeframes = _parse_timeframes(args.timeframes)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_root = Path(args.run_root) / f"campaign_{run_stamp}"
    run_root.mkdir(parents=True, exist_ok=True)

    base_policy_path = Path(args.liquidity_policy_config)
    base_policy = _load_yaml(base_policy_path)
    if not base_policy:
        raise SystemExit(f"missing or invalid liquidity policy config: {base_policy_path}")

    backfill_ok = True
    backfill_msg = "skipped"
    if args.ensure_eth_15m_backfill and "15m" in timeframes and "ETHUSDT" in symbols:
        backfill_ok, backfill_msg = _ensure_eth_15m_backfill(
            replay_start=str(args.replay_start),
            replay_end=str(args.replay_end),
            backfill_start=str(args.backfill_start),
            backfill_end=str(args.backfill_end),
        )
    print(f"[prep] ETHUSDT 15m backfill status: ok={backfill_ok} msg={backfill_msg}")

    baseline_policy = json.loads(json.dumps(base_policy))
    baseline_node = baseline_policy.get("high_liquidity_filters", baseline_policy)
    if isinstance(baseline_node, dict):
        baseline_node["enabled"] = False
    baseline_policy_path = run_root / "configs" / "baseline_policy.yaml"
    _write_yaml(baseline_policy_path, baseline_policy)

    metrics_rows: list[RunMetrics] = []
    baseline_by_tf: dict[str, RunMetrics] = {}
    for tf in timeframes:
        tf_symbols = list(symbols)
        if tf == "15m" and not _coverage_ok("ETHUSDT", "15m", str(args.replay_start), str(args.replay_end)):
            tf_symbols = [s for s in tf_symbols if s != "ETHUSDT"]
        run_dir = run_root / "baseline" / tf
        db_path = run_dir / "v25.db"
        rc = _run_main(
            run_dir=run_dir,
            db_path=db_path,
            symbols=tf_symbols,
            timeframe=tf,
            replay_start=str(args.replay_start),
            replay_end=str(args.replay_end),
            risk_profile=str(args.risk_profile),
            strategy_profiles_config=str(args.strategy_profiles_config),
            liquidity_policy_config=baseline_policy_path,
            timeout_s=int(args.main_timeout_seconds),
        )
        met = _compute_metrics(db_path, timeframe=tf, candidate="baseline", rc=rc, run_dir=run_dir)
        baseline_by_tf[tf] = met
        metrics_rows.append(met)
        print(f"[baseline] tf={tf} trades={met.trades} ret={met.total_return:.6f} dd={met.max_drawdown:.6f}")

    candidates = _candidate_grid(args.max_candidates)
    winner: Candidate | None = None
    winner_return = -10**18
    winner_config_payload: dict[str, Any] | None = None
    agg_rows: list[dict[str, Any]] = []

    for i, cand in enumerate(candidates, start=1):
        cand_payload = _apply_candidate(base_policy, cand)
        cand_cfg_path = run_root / "configs" / f"{cand.name}.yaml"
        _write_yaml(cand_cfg_path, cand_payload)

        cand_runs: dict[str, RunMetrics] = {}
        for tf in timeframes:
            tf_symbols = list(symbols)
            if tf == "15m" and not _coverage_ok("ETHUSDT", "15m", str(args.replay_start), str(args.replay_end)):
                tf_symbols = [s for s in tf_symbols if s != "ETHUSDT"]
            run_dir = run_root / cand.name / tf
            db_path = run_dir / "v25.db"
            rc = _run_main(
                run_dir=run_dir,
                db_path=db_path,
                symbols=tf_symbols,
                timeframe=tf,
                replay_start=str(args.replay_start),
                replay_end=str(args.replay_end),
                risk_profile=str(args.risk_profile),
                strategy_profiles_config=str(args.strategy_profiles_config),
                liquidity_policy_config=cand_cfg_path,
                timeout_s=int(args.main_timeout_seconds),
            )
            met = _compute_metrics(db_path, timeframe=tf, candidate=cand.name, rc=rc, run_dir=run_dir)
            cand_runs[tf] = met
            metrics_rows.append(met)

        total_return = sum(m.total_return for m in cand_runs.values())
        dd_ok = True
        for tf, met in cand_runs.items():
            base_dd = baseline_by_tf.get(tf).max_drawdown if tf in baseline_by_tf else 0.0
            if base_dd <= 1e-12:
                if met.max_drawdown > 1e-12:
                    dd_ok = False
                    break
            else:
                if met.max_drawdown > base_dd * 1.15:
                    dd_ok = False
                    break
        agg_rows.append(
            {
                "candidate": cand.name,
                "hydra_mode_15m": cand.hydra_mode_15m,
                "confluence_offset": cand.confluence_offset,
                "precision_min_grade": cand.precision_min_grade,
                "rr_offset": cand.rr_offset,
                "grade_c_min_conf": cand.grade_c_min_conf,
                "total_return": total_return,
                "dd_constraint_pass": int(dd_ok),
            }
        )
        print(
            f"[cand {i}/{len(candidates)}] {cand.name} ret={total_return:.6f} dd_pass={dd_ok}"
        )

        if dd_ok and total_return > winner_return:
            winner_return = total_return
            winner = cand
            winner_config_payload = cand_payload

    detail_csv = run_root / "timeframe_metrics.csv"
    with detail_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "candidate",
                "timeframe",
                "return_code",
                "trades",
                "win_rate",
                "total_return",
                "profit_factor",
                "max_drawdown",
                "long_trades",
                "short_trades",
                "top_reasons_json",
                "run_dir",
            ]
        )
        for m in metrics_rows:
            w.writerow(
                [
                    m.candidate,
                    m.timeframe,
                    m.return_code,
                    m.trades,
                    round(m.win_rate, 6),
                    round(m.total_return, 6),
                    "inf" if math.isinf(m.profit_factor) else round(m.profit_factor, 6),
                    round(m.max_drawdown, 6),
                    m.long_trades,
                    m.short_trades,
                    json.dumps(m.top_reasons, ensure_ascii=True),
                    str(m.run_dir),
                ]
            )

    agg_csv = run_root / "aggregate_candidates.csv"
    with agg_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "candidate",
                "hydra_mode_15m",
                "confluence_offset",
                "precision_min_grade",
                "rr_offset",
                "grade_c_min_conf",
                "total_return",
                "dd_constraint_pass",
            ],
        )
        w.writeheader()
        for row in sorted(agg_rows, key=lambda x: float(x["total_return"]), reverse=True):
            w.writerow(row)

    summary_path = run_root / "summary.md"
    lines = [
        "# BTC/ETH High-Liquidity Optimization",
        "",
        f"- replay_window: `{args.replay_start}` -> `{args.replay_end}`",
        f"- symbols: `{','.join(symbols)}`",
        f"- timeframes: `{','.join(timeframes)}`",
        f"- eth_15m_backfill_ok: `{backfill_ok}`",
        f"- eth_15m_backfill_msg: `{backfill_msg}`",
        "",
    ]
    if winner is None or winner_config_payload is None:
        lines.append("- winner: `NONE` (no candidate passed drawdown guardrail)")
    else:
        lines.extend(
            [
                f"- winner: `{winner.name}`",
                f"- winner_total_return: `{winner_return:.6f}`",
                f"- winner_hydra_mode_15m: `{winner.hydra_mode_15m}`",
                f"- winner_precision_min_grade: `{winner.precision_min_grade}`",
                f"- winner_confluence_offset: `{winner.confluence_offset:.2f}`",
                f"- winner_rr_offset: `{winner.rr_offset:.2f}`",
                f"- winner_grade_c_min_conf: `{winner.grade_c_min_conf:.2f}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Baseline (by timeframe)",
        ]
    )
    for tf in timeframes:
        m = baseline_by_tf.get(tf)
        if m is None:
            continue
        lines.append(
            f"- {tf}: trades={m.trades}, return={m.total_return:.6f}, pf={m.profit_factor:.4f}, dd={m.max_drawdown:.6f}"
        )
    lines.append("")
    lines.append("## Top 10 Aggregate Candidates")
    lines.append("")
    lines.append("| candidate | return | dd_pass | hydra_15m | p_grade | conf_off | rr_off | c_conf |")
    lines.append("|---|---:|---:|---|---|---:|---:|---:|")
    for row in sorted(agg_rows, key=lambda x: float(x["total_return"]), reverse=True)[:10]:
        lines.append(
            f"| {row['candidate']} | {float(row['total_return']):.6f} | {int(row['dd_constraint_pass'])} | "
            f"{row['hydra_mode_15m']} | {row['precision_min_grade']} | {float(row['confluence_offset']):.2f} | "
            f"{float(row['rr_offset']):.2f} | {float(row['grade_c_min_conf']):.2f} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if winner is not None and winner_config_payload is not None and bool(args.apply_winner):
        _write_yaml(Path(args.liquidity_policy_config), winner_config_payload)
        _persist_winner_to_strategy_profiles(
            strategy_profiles_path=Path(args.strategy_profiles_config),
            winner=winner,
            replay_start=str(args.replay_start),
            replay_end=str(args.replay_end),
            run_root=run_root,
        )
        print(f"[winner] {winner.name} written to {args.liquidity_policy_config}")
        print(f"[winner] metadata updated in {args.strategy_profiles_config}")
    elif winner is not None and winner_config_payload is not None:
        print(f"[winner] {winner.name} selected (not applied, use --apply-winner)")
    else:
        print("[winner] none selected due to drawdown guardrail")

    print(f"[report] summary={summary_path}")
    print(f"[report] details={detail_csv}")
    print(f"[report] aggregate={agg_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
