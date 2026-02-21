from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.replay_loader import ReplayLoader
from src.main import ArgusPipeline


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    risk_profile: str
    allow_crisis: bool


@dataclass
class ScenarioOutcome:
    scenario: str
    orion_enabled: bool
    run_dir: Path
    status: str
    reason: str
    trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    return_volatility: float = 0.0
    risk_adjusted_return: float = 0.0


def _parse_iso_utc(raw: str) -> datetime:
    text = str(raw).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _to_iso_z(dt: datetime) -> str:
    as_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return as_utc.isoformat().replace("+00:00", "Z")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _scenario_id(scenario: ScenarioConfig, orion_enabled: bool) -> str:
    suffix = "on" if orion_enabled else "off"
    return f"{scenario.name}__orion_{suffix}"


def _build_scenarios(smoke: bool) -> list[ScenarioConfig]:
    base = [
        ScenarioConfig(name="baseline", risk_profile="normal", allow_crisis=False),
        ScenarioConfig(name="strict_guard", risk_profile="strict", allow_crisis=False),
        ScenarioConfig(name="relaxed_crisis", risk_profile="relaxed", allow_crisis=True),
    ]
    if smoke:
        return [ScenarioConfig(name="smoke_relaxed", risk_profile="relaxed", allow_crisis=True)]
    return base


def _resolve_replay_anchor(*, loader: ReplayLoader, symbol: str, cycles: int) -> str:
    try:
        df = loader.load_ohlcv(symbol=symbol, interval="1m", verify=False)
    except Exception:
        return _to_iso_z(datetime.now(timezone.utc) - timedelta(minutes=max(5, cycles + 5)))

    if df.empty:
        return _to_iso_z(datetime.now(timezone.utc) - timedelta(minutes=max(5, cycles + 5)))

    idx_from_end = max(int(cycles) + 5, 120)
    anchor_idx = max(0, len(df) - idx_from_end)
    anchor_ts = df["timestamp"].iloc[anchor_idx]
    if isinstance(anchor_ts, datetime):
        return _to_iso_z(anchor_ts)
    try:
        return _to_iso_z(_parse_iso_utc(str(anchor_ts)))
    except Exception:
        return _to_iso_z(datetime.now(timezone.utc) - timedelta(minutes=max(5, cycles + 5)))


def _resolve_smoke_anchor_with_activity(*, loader: ReplayLoader, symbol: str, cycles: int) -> str:
    try:
        df = loader.load_ohlcv(symbol=symbol, interval="1m", verify=False)
    except Exception:
        return _resolve_replay_anchor(loader=loader, symbol=symbol, cycles=cycles)

    if df.empty:
        return _resolve_replay_anchor(loader=loader, symbol=symbol, cycles=cycles)

    start_min = max(0, len(df) - 50_000)
    start_max = max(start_min + 1, len(df) - max(cycles + 600, 2_000))
    sample_points = 20
    step = max(1, (start_max - start_min) // sample_points)

    best_anchor: datetime | None = None
    best_exec = -1

    idx = start_min
    while idx <= start_max:
        ts_raw = df["timestamp"].iloc[idx]
        anchor_ts = pd.Timestamp(ts_raw)
        if anchor_ts.tzinfo is None:
            anchor_ts = anchor_ts.tz_localize("UTC")
        else:
            anchor_ts = anchor_ts.tz_convert("UTC")

        pipeline = ArgusPipeline(
            mode="backtest",
            assets=["crypto"],
            replay_now=anchor_ts,
            forward_sim=True,
            ohlcv_limit=260,
            risk_profile="relaxed",
            allow_crisis=True,
            symbols_override={"crypto": [symbol]},
        )

        executed = 0
        for cycle in range(max(1, int(cycles))):
            now_dt = anchor_ts.to_pydatetime() + timedelta(minutes=cycle)
            pipeline.replay_now = pd.Timestamp(now_dt)
            outputs = pipeline.run_once(now=now_dt)
            for out in outputs:
                if str(out.get("status", "")).lower() == "executed":
                    executed += 1

        if executed > best_exec:
            best_exec = executed
            best_anchor = anchor_ts.to_pydatetime()
        if executed > 0:
            break
        idx += step

    if best_anchor is None:
        return _resolve_replay_anchor(loader=loader, symbol=symbol, cycles=cycles)
    return _to_iso_z(best_anchor)


def _run_main_scenario(
    *,
    scenario: ScenarioConfig,
    orion_enabled: bool,
    run_dir: Path,
    db_path: Path,
    cycles: int,
    hold_minutes: int,
    symbols: str,
    replay_anchor: str | None,
    forward_sim: bool,
    smoke: bool,
    timeout_seconds: int,
) -> tuple[str, str]:
    cmd: list[str] = [
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
        "--run-dir",
        str(run_dir),
        "--max-cycles",
        str(int(cycles)),
        "--cycle-step-minutes",
        "1",
        "--hold-minutes",
        str(int(hold_minutes)),
        "--symbols",
        symbols,
        "--risk-profile",
        scenario.risk_profile,
        "--limit",
        "260",
    ]

    if replay_anchor:
        cmd.extend(["--replay-now", replay_anchor])
    if forward_sim:
        cmd.append("--forward-sim")
    if smoke:
        cmd.append("--smoke")
    if orion_enabled:
        cmd.append("--orion")
    if scenario.allow_crisis:
        cmd.append("--allow-crisis")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "runner_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=max(int(timeout_seconds), 60),
        )
    except subprocess.TimeoutExpired:
        (run_dir / "runner_stdout.log").write_text("", encoding="utf-8")
        (run_dir / "runner_stderr.log").write_text("scenario timed out\n", encoding="utf-8")
        return "FAILED", "timeout"

    (run_dir / "runner_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "runner_stderr.log").write_text(proc.stderr or "", encoding="utf-8")

    if proc.returncode == 0:
        return "COMPLETED", "ok"

    combined = f"{proc.stdout}\n{proc.stderr}".lower()
    if "binance" in combined and ("failed" in combined or "circuit breaker" in combined):
        fallback_anchor = replay_anchor or _to_iso_z(
            datetime.now(timezone.utc) - timedelta(minutes=max(int(cycles) + 5, 60))
        )
        fallback_cmd = [part for part in cmd if part != "--live-data"]
        if "--replay-now" not in fallback_cmd:
            fallback_cmd.extend(["--replay-now", fallback_anchor])
        try:
            fb = subprocess.run(
                fallback_cmd,
                cwd=str(PROJECT_ROOT),
                text=True,
                capture_output=True,
                timeout=max(int(timeout_seconds), 60),
            )
            (run_dir / "fallback_stdout.log").write_text(fb.stdout or "", encoding="utf-8")
            (run_dir / "fallback_stderr.log").write_text(fb.stderr or "", encoding="utf-8")
        except subprocess.TimeoutExpired:
            (run_dir / "fallback_stdout.log").write_text("", encoding="utf-8")
            (run_dir / "fallback_stderr.log").write_text("fallback timed out\n", encoding="utf-8")
        return "FAILED", "binance_failure_fallback_to_cache"
    return "FAILED", f"main_exit_{proc.returncode}"


def _load_decisions(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT decision_id, timestamp, symbol, action, engine, reason, status,
                       confidence, gate_results_json
                FROM decisions
                ORDER BY decision_id ASC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(row) for row in rows]


def _load_closed_trades(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT trade_id, symbol, side, engine,
                       entry_time, exit_time, entry_price, exit_price,
                       hold_minutes, pnl_pct, net_pnl_pct, confidence,
                       regime_at_entry, regime_at_exit, stop_distance,
                       size
                FROM trades
                WHERE exit_time IS NOT NULL
                ORDER BY COALESCE(exit_time, entry_time) ASC, entry_time ASC, trade_id ASC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(row) for row in rows]


def _build_decision_lookup(decisions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        symbol = str(row.get("symbol", "UNKNOWN"))
        try:
            row["_dt"] = _parse_iso_utc(str(row.get("timestamp")))
        except Exception:
            row["_dt"] = datetime.min.replace(tzinfo=timezone.utc)
        row["_gate"] = _parse_json(row.get("gate_results_json"))
        by_symbol[symbol].append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda item: item.get("_dt", datetime.min.replace(tzinfo=timezone.utc)))
    return by_symbol


def _nearest_decision(symbol_rows: list[dict[str, Any]], at: datetime) -> dict[str, Any] | None:
    if not symbol_rows:
        return None
    chosen: dict[str, Any] | None = None
    for row in symbol_rows:
        row_dt = row.get("_dt")
        if isinstance(row_dt, datetime) and row_dt <= at:
            chosen = row
        else:
            break
    return chosen


def _compute_excursions(
    *,
    loader: ReplayLoader,
    symbol: str,
    side: str,
    entry_time: datetime,
    exit_time: datetime,
    entry_price: float,
) -> tuple[float, float, float]:
    start_key = entry_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    end_key = exit_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        df = loader.load_ohlcv(
            symbol=symbol,
            interval="1m",
            start=start_key,
            end=end_key,
            verify=False,
        )
    except Exception:
        df = None

    if df is None or df.empty:
        return 0.0, 0.0, 0.0

    entry = max(float(entry_price), 1e-9)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    closes = df["close"].astype(float).clip(lower=1e-9)

    if str(side).lower() == "short":
        mfe = float((entry / max(float(lows.min()), 1e-9)) - 1.0)
        mae = float((entry / max(float(highs.max()), 1e-9)) - 1.0)
        mae = min(mae, 0.0)
        equity = entry / closes
    else:
        mfe = float((float(highs.max()) / entry) - 1.0)
        mae = float((float(lows.min()) / entry) - 1.0)
        mae = min(mae, 0.0)
        equity = closes / entry

    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    dd = float(drawdown.min()) if len(drawdown) else 0.0
    return dd, mfe, mae


def _improvement_suggestion(trade: dict[str, Any]) -> str:
    regime = str(trade.get("regime_at_entry", "")).upper()
    engine = str(trade.get("engine", "")).upper()
    net = _as_float(trade.get("net_pnl_pct"))
    stop_distance = _as_float(trade.get("stop_distance"))
    atr_pct = _as_float(trade.get("volatility_at_entry"))
    adx = _as_float(trade.get("adx_at_entry"))
    hold_minutes = int(max(1, _as_float(trade.get("hold_minutes"), 1.0)))
    mfe = _as_float(trade.get("max_favorable_excursion"))
    confidence = _as_float(trade.get("confidence_at_entry"))
    vol_ratio = _as_float(trade.get("volume_ratio_at_entry"))

    breakout_engines = {"TITAN", "PHOENIX", "HYDRA", "NAUTILUS"}
    if net < 0.0 and "CHOP" in regime and engine in breakout_engines:
        return "Breakout failed in CHOP -> tighten regime compatibility filters."
    if net < 0.0 and atr_pct > 0.0 and stop_distance < (atr_pct * 0.8):
        return "Stop looked tight versus ATR -> review stop multiplier calibration."
    if net > 0.0 and adx >= 25.0 and hold_minutes <= 20 and mfe > (net * 1.4):
        return "Trend remained strong after exit -> consider dynamic take-profit extension."
    if confidence >= 0.75 and vol_ratio < 0.9:
        return "High confidence with weak volume -> increase volume weighting in conviction model."
    if net < 0.0 and _as_float(trade.get("drawdown_during_trade")) < -0.03:
        return "Adverse path was persistent -> reduce size in weak microstructure conditions."
    return "Refine entry timing with tighter confirmation on regime + volume alignment."


def _trade_texts(trade: dict[str, Any]) -> tuple[str, str]:
    net = _as_float(trade.get("net_pnl_pct"))
    adx = _as_float(trade.get("adx_at_entry"))
    vol_ratio = _as_float(trade.get("volume_ratio_at_entry"))
    regime = str(trade.get("regime_at_entry", "UNKNOWN"))
    dd = _as_float(trade.get("drawdown_during_trade"))

    if net >= 0.0:
        right_parts: list[str] = ["Directional bias remained positive into exit."]
        if adx >= 20.0:
            right_parts.append("Trend strength at entry was supportive.")
        if vol_ratio >= 1.0:
            right_parts.append("Participation volume confirmed move quality.")
        return " ".join(right_parts), "No major structural breakdown observed."

    wrong_parts: list[str] = ["Trade closed negative versus entry."]
    if "CHOP" in regime.upper():
        wrong_parts.append("Regime was choppy for directional execution.")
    if vol_ratio < 0.9:
        wrong_parts.append("Volume confirmation was weak.")
    if dd < -0.02:
        wrong_parts.append("Adverse excursion built quickly after entry.")
    return "Entry thesis had partial alignment.", " ".join(wrong_parts)


def _write_equity_curves(run_dir: Path, trades: list[dict[str, Any]]) -> None:
    rows: list[tuple[str, float, float]] = []
    equity = 1.0
    peak = 1.0

    for row in trades:
        trade_ret = _as_float(row.get("net_pnl_pct"))
        equity *= (1.0 + trade_ret)
        peak = max(peak, equity)
        drawdown = (equity / peak) - 1.0 if peak > 0 else 0.0
        ts = str(row.get("exit_time") or row.get("entry_time") or "")
        rows.append((ts, float(equity), float(drawdown)))

    for filename in ("equity_curve.csv", "drawdown_curve.csv"):
        path = run_dir / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "equity", "drawdown"])
            for ts, eq, dd in rows:
                writer.writerow([ts, f"{eq:.10f}", f"{dd:.10f}"])


def _build_trade_analytics(
    *,
    run_dir: Path,
    scenario_id: str,
    trades: list[dict[str, Any]],
    decisions_by_symbol: dict[str, list[dict[str, Any]]],
    loader: ReplayLoader,
) -> list[dict[str, Any]]:
    trades_dir = run_dir / "trades"
    trades_dir.mkdir(parents=True, exist_ok=True)

    analytics_rows: list[dict[str, Any]] = []
    for row in trades:
        trade_id = str(row.get("trade_id", "unknown_trade"))
        symbol = str(row.get("symbol", "UNKNOWN"))
        side = str(row.get("side", "long")).lower()
        engine = str(row.get("engine", "UNKNOWN"))

        entry_time = _parse_iso_utc(str(row.get("entry_time")))
        exit_time = _parse_iso_utc(str(row.get("exit_time")))
        entry_price = max(_as_float(row.get("entry_price"), 1.0), 1e-9)
        exit_price = max(_as_float(row.get("exit_price"), entry_price), 1e-9)
        hold_minutes = int(max(1, _as_float(row.get("hold_minutes"), (exit_time - entry_time).total_seconds() / 60.0)))

        symbol_decisions = decisions_by_symbol.get(symbol, [])
        entry_decision = _nearest_decision(symbol_decisions, entry_time)
        exit_decision = _nearest_decision(symbol_decisions, exit_time)

        entry_gate = entry_decision.get("_gate", {}) if isinstance(entry_decision, dict) else {}
        entry_snapshot = entry_gate.get("features_snapshot", {}) if isinstance(entry_gate.get("features_snapshot"), dict) else {}
        regime_at_entry = str(
            entry_snapshot.get("regime")
            or (entry_decision.get("reason") if isinstance(entry_decision, dict) else None)
            or row.get("regime_at_entry")
            or "UNKNOWN"
        )
        exit_gate = exit_decision.get("_gate", {}) if isinstance(exit_decision, dict) else {}
        exit_snapshot = exit_gate.get("features_snapshot", {}) if isinstance(exit_gate.get("features_snapshot"), dict) else {}
        regime_at_exit = str(
            exit_snapshot.get("regime")
            or (exit_decision.get("reason") if isinstance(exit_decision, dict) else None)
            or row.get("regime_at_exit")
            or regime_at_entry
        )

        drawdown_during_trade, mfe, mae = _compute_excursions(
            loader=loader,
            symbol=symbol,
            side=side,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=entry_price,
        )

        trade_payload: dict[str, Any] = {
            "scenario": scenario_id,
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "engine": engine,
            "entry_time": _to_iso_z(entry_time),
            "exit_time": _to_iso_z(exit_time),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "hold_minutes": int(hold_minutes),
            "pnl_pct": _as_float(row.get("pnl_pct")),
            "net_pnl_pct": _as_float(row.get("net_pnl_pct")),
            "confidence_at_entry": _as_float(
                entry_decision.get("confidence") if isinstance(entry_decision, dict) else row.get("confidence")
            ),
            "regime_at_entry": regime_at_entry,
            "regime_at_exit": regime_at_exit,
            "volatility_at_entry": _as_float(entry_snapshot.get("atr_14_pct")),
            "adx_at_entry": _as_float(entry_snapshot.get("adx_14")),
            "volume_ratio_at_entry": _as_float(entry_snapshot.get("volume_ratio")),
            "drawdown_during_trade": float(drawdown_during_trade),
            "max_favorable_excursion": float(mfe),
            "max_adverse_excursion": float(mae),
            "stop_distance": _as_float(row.get("stop_distance")),
        }

        what_right, what_wrong = _trade_texts(trade_payload)
        trade_payload["what_went_right"] = what_right
        trade_payload["what_went_wrong"] = what_wrong
        trade_payload["improvement_suggestion"] = _improvement_suggestion(trade_payload)

        out_payload = {
            "symbol": trade_payload["symbol"],
            "side": trade_payload["side"],
            "engine": trade_payload["engine"],
            "entry_time": trade_payload["entry_time"],
            "exit_time": trade_payload["exit_time"],
            "entry_price": trade_payload["entry_price"],
            "exit_price": trade_payload["exit_price"],
            "hold_minutes": trade_payload["hold_minutes"],
            "pnl_pct": trade_payload["pnl_pct"],
            "net_pnl_pct": trade_payload["net_pnl_pct"],
            "confidence_at_entry": trade_payload["confidence_at_entry"],
            "regime_at_entry": trade_payload["regime_at_entry"],
            "regime_at_exit": trade_payload["regime_at_exit"],
            "volatility_at_entry": trade_payload["volatility_at_entry"],
            "adx_at_entry": trade_payload["adx_at_entry"],
            "volume_ratio_at_entry": trade_payload["volume_ratio_at_entry"],
            "drawdown_during_trade": trade_payload["drawdown_during_trade"],
            "max_favorable_excursion": trade_payload["max_favorable_excursion"],
            "max_adverse_excursion": trade_payload["max_adverse_excursion"],
            "what_went_right": trade_payload["what_went_right"],
            "what_went_wrong": trade_payload["what_went_wrong"],
            "improvement_suggestion": trade_payload["improvement_suggestion"],
        }

        (trades_dir / f"{trade_id}.json").write_text(
            json.dumps(out_payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        analytics_rows.append(trade_payload)

    return analytics_rows


def _scenario_metrics(trade_rows: list[dict[str, Any]]) -> dict[str, float]:
    if not trade_rows:
        return {
            "trades": 0.0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "return_volatility": 0.0,
            "risk_adjusted_return": 0.0,
        }

    returns = [_as_float(row.get("net_pnl_pct")) for row in trade_rows]
    wins = sum(1 for ret in returns if ret > 0.0)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret in returns:
        equity *= (1.0 + ret)
        peak = max(peak, equity)
        dd = (equity / peak) - 1.0 if peak > 0 else 0.0
        max_dd = min(max_dd, dd)

    avg_ret = statistics.mean(returns)
    vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    risk_adj = 0.0
    if vol > 0.0:
        risk_adj = (avg_ret / vol) * math.sqrt(len(returns))

    return {
        "trades": float(len(returns)),
        "win_rate": float(wins / len(returns)),
        "avg_return": float(avg_ret),
        "total_return": float(equity - 1.0),
        "max_drawdown": float(max_dd),
        "return_volatility": float(vol),
        "risk_adjusted_return": float(risk_adj),
    }


def _write_monthly_summary(
    *,
    reports_dir: Path,
    all_trades: list[dict[str, Any]],
) -> None:
    csv_path = reports_dir / "WAR_FORWARD_MONTHLY_SUMMARY.csv"
    md_path = reports_dir / "WAR_FORWARD_MONTHLY_SUMMARY.md"

    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_trades:
        exit_time = str(row.get("exit_time", ""))
        month = exit_time[:7] if len(exit_time) >= 7 else "UNKNOWN"
        by_month[month].append(row)

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "month",
                "trades",
                "win_rate",
                "avg_return",
                "total_return",
                "max_drawdown",
                "best_engine",
                "worst_engine",
                "regime_dominance",
            ]
        )

        for month in sorted(by_month):
            rows = sorted(by_month[month], key=lambda item: str(item.get("exit_time", "")))
            returns = [_as_float(item.get("net_pnl_pct")) for item in rows]
            trades = len(returns)
            wins = sum(1 for ret in returns if ret > 0.0)
            avg_return = statistics.mean(returns) if returns else 0.0

            equity = 1.0
            peak = 1.0
            max_dd = 0.0
            for ret in returns:
                equity *= (1.0 + ret)
                peak = max(peak, equity)
                dd = (equity / peak) - 1.0 if peak > 0 else 0.0
                max_dd = min(max_dd, dd)

            by_engine: dict[str, list[float]] = defaultdict(list)
            regime_counts: Counter[str] = Counter()
            for item in rows:
                by_engine[str(item.get("engine", "UNKNOWN"))].append(_as_float(item.get("net_pnl_pct")))
                regime_counts[str(item.get("regime_at_entry", "UNKNOWN"))] += 1

            engine_rank = sorted(
                ((eng, statistics.mean(vals) if vals else 0.0) for eng, vals in by_engine.items()),
                key=lambda pair: pair[1],
                reverse=True,
            )
            best_engine = engine_rank[0][0] if engine_rank else "N/A"
            worst_engine = engine_rank[-1][0] if engine_rank else "N/A"
            regime_dominance = regime_counts.most_common(1)[0][0] if regime_counts else "N/A"

            writer.writerow(
                [
                    month,
                    trades,
                    f"{(wins / trades) if trades else 0.0:.6f}",
                    f"{avg_return:.6f}",
                    f"{(equity - 1.0) if trades else 0.0:.6f}",
                    f"{max_dd:.6f}",
                    best_engine,
                    worst_engine,
                    regime_dominance,
                ]
            )

    md_lines: list[str] = [
        "# WAR Forward Monthly Summary",
        "",
        "| month | trades | win_rate | avg_return | total_return | max_drawdown | best_engine | worst_engine | regime_dominance |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            md_lines.append(
                "| {month} | {trades} | {win_rate} | {avg_return} | {total_return} | {max_drawdown} | {best_engine} | {worst_engine} | {regime_dominance} |".format(
                    **row
                )
            )

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def _reason_bucket(reason: str, status: str, action: str) -> str:
    r = str(reason).lower()
    s = str(status).lower()
    a = str(action).lower()

    if s == "executed" and a in {"long", "short"}:
        return "executed"
    if "no_signal" in r:
        return "no_signal"
    if "gate9_fail" in r:
        return "gate9_fail"
    if "veto" in r or "hermes" in r:
        return "veto"
    if "orion_risk_block" in r:
        return "orion_risk_block"
    if "precision_grade" in r:
        return "precision_fail"
    if "signal_quality" in r:
        return "signal_quality_fail"
    if "warmup" in r or "forward_wait_next_candle" in r:
        return "warmup"
    return "other_reject"


def _build_improvement_ranking(
    *,
    funnel: Counter[str],
    decisions_count: int,
    trades: list[dict[str, Any]],
) -> list[str]:
    trades_count = len(trades)
    chop_losses = sum(1 for t in trades if _as_float(t.get("net_pnl_pct")) < 0.0 and "CHOP" in str(t.get("regime_at_entry", "")).upper())
    stop_tight_losses = sum(
        1
        for t in trades
        if _as_float(t.get("net_pnl_pct")) < 0.0 and _as_float(t.get("stop_distance")) < (_as_float(t.get("volatility_at_entry")) * 0.8)
    )
    early_exit = sum(
        1
        for t in trades
        if _as_float(t.get("net_pnl_pct")) > 0.0
        and _as_float(t.get("adx_at_entry")) >= 25.0
        and int(max(1, _as_float(t.get("hold_minutes"), 1.0))) <= 20
        and _as_float(t.get("max_favorable_excursion")) > (_as_float(t.get("net_pnl_pct")) * 1.4)
    )
    high_conf_low_vol = sum(
        1
        for t in trades
        if _as_float(t.get("confidence_at_entry")) >= 0.75 and _as_float(t.get("volume_ratio_at_entry")) < 0.9
    )

    suggestions: list[tuple[float, str]] = []
    if decisions_count > 0:
        suggestions.append((
            (funnel.get("no_signal", 0) / decisions_count) * 100.0,
            "Reduce no-signal dead zones by relaxing entry threshold only in high-liquidity windows.",
        ))
        suggestions.append((
            (funnel.get("gate9_fail", 0) / decisions_count) * 100.0,
            "Revisit Gate9 fee-to-risk threshold by regime to recover blocked yet viable entries.",
        ))
        suggestions.append((
            (funnel.get("veto", 0) / decisions_count) * 100.0,
            "Audit veto pathways and separate hard veto from soft confidence haircut.",
        ))

    if trades_count > 0:
        suggestions.append((100.0 * chop_losses / trades_count, "Tighten breakout engine compatibility when regime is CHOP."))
        suggestions.append((100.0 * stop_tight_losses / trades_count, "Increase ATR-based stop multiplier where stop_distance is repeatedly too tight."))
        suggestions.append((100.0 * early_exit / trades_count, "Deploy dynamic TP extension for strong-trend trades exiting too early."))
        suggestions.append((100.0 * high_conf_low_vol / trades_count, "Boost volume weighting inside confidence model to avoid thin-market entries."))

        returns = [_as_float(t.get("net_pnl_pct")) for t in trades]
        ret_vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        avg_ret = statistics.mean(returns) if returns else 0.0
        risk_adj = (avg_ret / ret_vol) * math.sqrt(len(returns)) if ret_vol > 0 else 0.0
        suggestions.append((abs(ret_vol) * 100.0, "Lower return volatility via regime-scaled size throttling and cooldowns."))
        suggestions.append((max(0.0, 10.0 - risk_adj), "Improve risk-adjusted return through drawdown-aware leverage tapering."))

    suggestions.append((2.0, "Track engine drift monthly and auto-reweight underperforming engines."))
    suggestions.append((1.0, "Add scenario-level fail-fast retries with explicit cache freshness checks."))

    ranked = sorted(suggestions, key=lambda item: item[0], reverse=True)
    out: list[str] = []
    for _, text in ranked:
        if text in out:
            continue
        out.append(text)
        if len(out) >= 10:
            break
    while len(out) < 10:
        out.append("Expand regime-specific calibration datasets before next war-forward cycle.")
    return out


def _write_meta_analysis(
    *,
    reports_dir: Path,
    outcomes: list[ScenarioOutcome],
    all_decisions: list[dict[str, Any]],
    all_trades: list[dict[str, Any]],
) -> None:
    path = reports_dir / "WAR_FORWARD_ANALYSIS.md"

    by_regime_engine: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in all_trades:
        key = (str(row.get("regime_at_entry", "UNKNOWN")), str(row.get("engine", "UNKNOWN")))
        by_regime_engine[key].append(_as_float(row.get("net_pnl_pct")))

    funnel: Counter[str] = Counter()
    for row in all_decisions:
        bucket = _reason_bucket(
            reason=str(row.get("reason", "")),
            status=str(row.get("status", "")),
            action=str(row.get("action", "")),
        )
        funnel[bucket] += 1

    hold_minutes = [int(max(1, _as_float(r.get("hold_minutes"), 1.0))) for r in all_trades]
    net_returns = [_as_float(r.get("net_pnl_pct")) for r in all_trades]
    avg_hold = statistics.mean(hold_minutes) if hold_minutes else 0.0
    med_hold = statistics.median(hold_minutes) if hold_minutes else 0.0
    return_per_hour = (
        statistics.mean(
            _as_float(r.get("net_pnl_pct")) / max(int(max(1, _as_float(r.get("hold_minutes"), 1.0))) / 60.0, 1e-6)
            for r in all_trades
        )
        if all_trades
        else 0.0
    )
    signal_to_trade = (len(all_trades) / len(all_decisions)) if all_decisions else 0.0

    ret_vol = statistics.pstdev(net_returns) if len(net_returns) > 1 else 0.0
    avg_ret = statistics.mean(net_returns) if net_returns else 0.0
    risk_adj = (avg_ret / ret_vol) * math.sqrt(len(net_returns)) if ret_vol > 0 else 0.0

    ranked_suggestions = _build_improvement_ranking(
        funnel=funnel,
        decisions_count=len(all_decisions),
        trades=all_trades,
    )

    lines: list[str] = [
        "# WAR Forward Analysis",
        "",
        "## 1) Overall comparison table (scenario x ORION on/off)",
        "",
        "| scenario | orion | status | trades | win_rate | avg_return | total_return | max_drawdown |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in outcomes:
        lines.append(
            "| {scenario} | {orion} | {status} | {trades} | {win_rate:.4f} | {avg_return:.6f} | {total_return:.6f} | {max_drawdown:.6f} |".format(
                scenario=row.scenario,
                orion="on" if row.orion_enabled else "off",
                status=row.status,
                trades=int(row.trades),
                win_rate=row.win_rate,
                avg_return=row.avg_return,
                total_return=row.total_return,
                max_drawdown=row.max_drawdown,
            )
        )

    lines.extend(
        [
            "",
            "## 2) Engine performance per regime",
            "",
            "| regime | engine | trades | win_rate | avg_net_return |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for (regime, engine), values in sorted(by_regime_engine.items(), key=lambda item: (item[0][0], item[0][1])):
        wins = sum(1 for val in values if val > 0.0)
        lines.append(
            f"| {regime} | {engine} | {len(values)} | {(wins / len(values)) if values else 0.0:.4f} | {statistics.mean(values) if values else 0.0:.6f} |"
        )

    lines.extend(
        [
            "",
            "## 3) Failure funnel",
            "",
            "| bucket | count | share |",
            "|---|---:|---:|",
        ]
    )
    total_funnel = sum(funnel.values())
    for bucket, count in funnel.most_common():
        share = (count / total_funnel) if total_funnel else 0.0
        lines.append(f"| {bucket} | {count} | {share:.4f} |")

    lines.extend(
        [
            "",
            "## 4) Capital efficiency metrics",
            "",
            f"- Avg hold minutes: {avg_hold:.2f}",
            f"- Median hold minutes: {med_hold:.2f}",
            f"- Return per hold-hour: {return_per_hour:.6f}",
            f"- Signal-to-trade conversion: {signal_to_trade:.4f}",
            "",
            "## 5) Stability metrics",
            "",
            f"- Return volatility: {ret_vol:.6f}",
            f"- Risk-adjusted return: {risk_adj:.6f}",
            "",
            "## 6) Improvement suggestions (ranked by impact)",
            "",
        ]
    )
    for idx, text in enumerate(ranked_suggestions, start=1):
        lines.append(f"{idx}. {text}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="WAR forward-style incremental simulation runner + analytics")
    parser.add_argument("--forward-sim", action="store_true", default=False, help="Enable incremental candle stepping")
    parser.add_argument("--smoke", action="store_true", default=False, help="Run quick mode: 50 cycles, BTCUSDT")
    parser.add_argument("--cycles", type=int, default=240, help="Cycles per scenario")
    parser.add_argument("--symbols", default="BTCUSDT", help="Comma-separated symbol list")
    parser.add_argument("--replay-anchor", default=None, help="Replay anchor UTC ISO string")
    parser.add_argument("--hold-minutes", type=int, default=30, help="Backtest hold minutes for simulator")
    parser.add_argument("--run-root", default="runs/war_forward", help="Scenario outputs directory")
    parser.add_argument("--reports-dir", default="reports", help="Reports output directory")
    parser.add_argument("--cache-root", default="data/binance", help="Cached Binance parquet root")
    parser.add_argument("--scenario-timeout", type=int, default=900, help="Per-scenario timeout seconds")
    args = parser.parse_args()

    run_root = PROJECT_ROOT / args.run_root
    reports_dir = PROJECT_ROOT / args.reports_dir
    run_root.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    cycles = 50 if args.smoke else max(1, int(args.cycles))
    symbols = "BTCUSDT" if args.smoke else str(args.symbols)

    loader = ReplayLoader(root=args.cache_root)
    replay_anchor = args.replay_anchor
    if replay_anchor is None:
        if args.smoke:
            replay_anchor = _resolve_smoke_anchor_with_activity(loader=loader, symbol="BTCUSDT", cycles=cycles)
        else:
            replay_anchor = _resolve_replay_anchor(loader=loader, symbol="BTCUSDT", cycles=cycles)

    scenarios = _build_scenarios(smoke=args.smoke)
    orion_matrix = [False, True]

    outcomes: list[ScenarioOutcome] = []
    all_decisions: list[dict[str, Any]] = []
    all_trade_rows: list[dict[str, Any]] = []

    for scenario in scenarios:
        for orion_enabled in orion_matrix:
            scenario_id = _scenario_id(scenario, orion_enabled)
            run_dir = run_root / scenario_id
            db_path = run_dir / "war_forward_v25.db"

            status, reason = _run_main_scenario(
                scenario=scenario,
                orion_enabled=orion_enabled,
                run_dir=run_dir,
                db_path=db_path,
                cycles=cycles,
                hold_minutes=max(1, int(args.hold_minutes)),
                symbols=symbols,
                replay_anchor=replay_anchor,
                forward_sim=bool(args.forward_sim),
                smoke=bool(args.smoke),
                timeout_seconds=int(args.scenario_timeout),
            )

            outcome = ScenarioOutcome(
                scenario=scenario.name,
                orion_enabled=orion_enabled,
                run_dir=run_dir,
                status=status,
                reason=reason,
            )

            if status == "COMPLETED":
                decisions = _load_decisions(db_path)
                trades = _load_closed_trades(db_path)
                decisions_by_symbol = _build_decision_lookup(decisions)

                trade_analytics = _build_trade_analytics(
                    run_dir=run_dir,
                    scenario_id=scenario_id,
                    trades=trades,
                    decisions_by_symbol=decisions_by_symbol,
                    loader=loader,
                )
                _write_equity_curves(run_dir, trades)

                metrics = _scenario_metrics(trade_analytics)
                outcome.trades = int(metrics["trades"])
                outcome.win_rate = float(metrics["win_rate"])
                outcome.avg_return = float(metrics["avg_return"])
                outcome.total_return = float(metrics["total_return"])
                outcome.max_drawdown = float(metrics["max_drawdown"])
                outcome.return_volatility = float(metrics["return_volatility"])
                outcome.risk_adjusted_return = float(metrics["risk_adjusted_return"])

                all_decisions.extend(decisions)
                all_trade_rows.extend(trade_analytics)

            state_path = run_dir / "scenario_status.json"
            state_path.write_text(
                json.dumps(
                    {
                        "scenario": scenario.name,
                        "orion_enabled": bool(orion_enabled),
                        "status": outcome.status,
                        "reason": outcome.reason,
                        "cycles": int(cycles),
                        "symbols": symbols,
                        "replay_anchor": replay_anchor,
                        "forward_sim": bool(args.forward_sim),
                    },
                    indent=2,
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )

            outcomes.append(outcome)

    _write_monthly_summary(reports_dir=reports_dir, all_trades=all_trade_rows)
    _write_meta_analysis(
        reports_dir=reports_dir,
        outcomes=outcomes,
        all_decisions=all_decisions,
        all_trades=all_trade_rows,
    )

    print(f"[war_forward] completed scenarios={len(outcomes)}")
    print(f"[war_forward] monthly_summary={reports_dir / 'WAR_FORWARD_MONTHLY_SUMMARY.csv'}")
    print(f"[war_forward] analysis={reports_dir / 'WAR_FORWARD_ANALYSIS.md'}")


if __name__ == "__main__":
    main()
