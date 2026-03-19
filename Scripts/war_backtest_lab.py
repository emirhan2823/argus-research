from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.war_forward_report import (  # noqa: E402
    _as_float,
    _build_decision_lookup,
    _build_trade_analytics,
    _load_closed_trades,
    _load_decisions,
    _scenario_metrics,
    _to_iso_z,
    _write_equity_curves,
)
from src.data.local_store import LocalStore  # noqa: E402
from src.data.replay_loader import ReplayLoader  # noqa: E402


TIMEFRAME_TO_MINUTES: dict[str, int] = {
    "15m": 15,
    "1h": 60,
}

EARLY_ENTRY_CANDLES_BACK = 3
LAGGING_ENTRY_DELTA_THRESHOLD = 0.05


@dataclass(frozen=True)
class ScenarioPreset:
    name: str
    start: date
    end: date | None
    assets: tuple[str, ...]
    timeframe: str
    risk_profile: str
    orion: str


@dataclass(frozen=True)
class MonthSlice:
    label: str
    start: datetime
    end: datetime


@dataclass
class MonthRunResult:
    month: str
    status: str
    reason: str
    run_dir: Path
    cycles: int = 0
    trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    long_trade_count: int = 0
    short_trade_count: int = 0
    long_total_return: float = 0.0
    short_total_return: float = 0.0
    long_max_drawdown: float = 0.0
    short_max_drawdown: float = 0.0
    leverage_avg_long: float = 0.0
    leverage_avg_short: float = 0.0


@dataclass
class ScenarioRunResult:
    scenario_id: str
    scenario_name: str
    status: str
    reason: str
    run_dir: Path
    start: date
    end: date
    symbols: tuple[str, ...]
    timeframe: str
    risk_profile: str
    orion_enabled: bool
    months: list[MonthRunResult]
    trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    long_total_return: float = 0.0
    short_total_return: float = 0.0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_max_drawdown: float = 0.0
    short_max_drawdown: float = 0.0
    long_trade_count: int = 0
    short_trade_count: int = 0
    long_avg_rr: float = 0.0
    short_avg_rr: float = 0.0
    long_max_adverse_excursion: float = 0.0
    short_max_adverse_excursion: float = 0.0
    bear_only_short_return: float = 0.0
    bear_only_long_return: float = 0.0
    bear_short_edge_ratio: float = 0.0
    best_engine: str = "N/A"
    worst_engine: str = "N/A"
    regime_dominance: str = "N/A"
    longest_losing_streak: int = 0
    max_consecutive_loss_pct_sum: float = 0.0
    max_consecutive_short_losses: int = 0
    max_consecutive_long_losses: int = 0
    leverage_avg_long: float = 0.0
    leverage_avg_short: float = 0.0


@dataclass(frozen=True)
class CoverageRow:
    scenario_id: str
    month: str
    symbol: str
    bars: int
    status: str


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest-only WAR lab with scenario presets and monthly aggregation")
    parser.add_argument("--scenario", default="bull_2024", help="Scenario name from YAML or 'all'")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbol override list")
    parser.add_argument("--timeframe", choices=["1h", "15m"], default=None, help="Override scenario timeframe")
    parser.add_argument("--orion", choices=["on", "off", "matrix"], default=None, help="Override scenario ORION mode")
    parser.add_argument("--max-cycles-per-scenario", type=int, default=None, help="Optional total cycle cap per scenario")
    parser.add_argument("--scenario-timeout", type=int, default=1800, help="Timeout per monthly backtest slice")
    parser.add_argument("--output-dir", default=None, help="Output root (default: runs/war_backtest_lab/<scenario>/<timestamp>)")
    parser.add_argument("--reports-dir", default="reports", help="Reports output directory")
    parser.add_argument("--cache-root", default="data/binance", help="Replay cache parquet root")
    parser.add_argument("--hold-minutes", type=int, default=30, help="Backtest hold minutes")
    parser.add_argument("--use-risk-config", action="store_true", default=False, help="Pass --use-risk-config to backtest runner.")
    parser.add_argument("--risk-config", default="runs/v25/risk_config.json", help="Risk config path passed to src.main.")
    parser.add_argument(
        "--scenarios-file",
        default="Scripts/scenarios/backtest_scenarios.yaml",
        help="Scenario preset YAML path",
    )
    parser.add_argument(
        "--export-monthly-trades-csv",
        action="store_true",
        default=False,
        help="Export per-month trades CSV under each scenario run",
    )
    return parser.parse_args(argv)


def _parse_symbols(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return tuple()
    values: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        symbol = str(part).strip().upper().replace("/", "").replace("-", "").replace("_", "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        values.append(symbol)
    return tuple(values)


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    return datetime.fromisoformat(text).date()


def _normalize_orion_mode(value: Any) -> str:
    mode = str(value or "matrix").strip().lower()
    if mode not in {"on", "off", "matrix"}:
        return "matrix"
    return mode


def _normalize_risk_profile(value: Any) -> str:
    profile = str(value or "normal").strip().lower()
    if profile not in {"relaxed", "normal"}:
        return "normal"
    return profile


def load_scenario_presets(path: Path) -> dict[str, ScenarioPreset]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = payload.get("defaults", {}) if isinstance(payload, dict) else {}
    scenarios = payload.get("scenarios", {}) if isinstance(payload, dict) else {}
    if not isinstance(scenarios, dict):
        raise ValueError("scenarios section must be a mapping")

    default_assets = tuple(_parse_symbols(",".join(str(x) for x in defaults.get("assets", []))))
    if not default_assets:
        default_assets = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT")
    default_timeframe = str(defaults.get("timeframe", "1h")).strip()
    if default_timeframe not in TIMEFRAME_TO_MINUTES:
        default_timeframe = "1h"
    default_risk_profile = _normalize_risk_profile(defaults.get("risk_profile", "normal"))
    default_orion = _normalize_orion_mode(defaults.get("orion", "matrix"))

    out: dict[str, ScenarioPreset] = {}
    for name, raw in sorted(scenarios.items(), key=lambda item: str(item[0])):
        if not isinstance(raw, dict):
            raise ValueError(f"scenario {name!r} must be a mapping")
        start_raw = raw.get("start")
        if start_raw is None:
            raise ValueError(f"scenario {name!r} is missing start")
        end_raw = raw.get("end")

        assets = _parse_symbols(",".join(str(x) for x in raw.get("assets", default_assets)))
        if not assets:
            assets = default_assets

        timeframe = str(raw.get("timeframe", default_timeframe)).strip()
        if timeframe not in TIMEFRAME_TO_MINUTES:
            timeframe = default_timeframe

        risk_profile = _normalize_risk_profile(raw.get("risk_profile", default_risk_profile))
        orion_mode = _normalize_orion_mode(raw.get("orion", default_orion))

        end_date: date | None
        if isinstance(end_raw, str) and end_raw.strip().lower() == "latest":
            end_date = None
        elif end_raw is None:
            end_date = None
        else:
            end_date = _coerce_date(end_raw)

        out[str(name)] = ScenarioPreset(
            name=str(name),
            start=_coerce_date(start_raw),
            end=end_date,
            assets=tuple(assets),
            timeframe=timeframe,
            risk_profile=risk_profile,
            orion=orion_mode,
        )
    return out


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def generate_month_slices(start: date, end: date) -> list[MonthSlice]:
    if end < start:
        raise ValueError("end date must be >= start date")
    out: list[MonthSlice] = []
    cursor = _month_start(start)
    last_month = _month_start(end)

    while cursor <= last_month:
        next_month = _next_month(cursor)
        month_end_day = next_month - timedelta(days=1)
        slice_start_day = max(start, cursor)
        slice_end_day = min(end, month_end_day)
        out.append(
            MonthSlice(
                label=cursor.strftime("%Y-%m"),
                start=datetime.combine(slice_start_day, time(hour=0, minute=0, tzinfo=timezone.utc)),
                end=datetime.combine(slice_end_day, time(hour=23, minute=59, tzinfo=timezone.utc)),
            )
        )
        cursor = next_month
    return out


def _latest_available_end_date(*, cache_root: str | Path, symbols: Iterable[str], timeframe: str) -> date | None:
    store = LocalStore(root=cache_root)
    latest: date | None = None
    for symbol in sorted(set(str(s).upper() for s in symbols)):
        months = store.list_months(symbol, timeframe)
        if not months:
            continue
        month = months[-1]
        frame = store.load_month(symbol, timeframe, month)
        if frame.empty:
            continue
        ts = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce").dropna()
        if ts.empty:
            continue
        day = ts.max().date()
        if latest is None or day > latest:
            latest = day
    return latest


def _resolve_scenario(
    *,
    preset: ScenarioPreset,
    cache_root: str,
    symbols_override: tuple[str, ...],
    timeframe_override: str | None,
    orion_override: str | None,
) -> tuple[date, date, tuple[str, ...], str, str]:
    symbols = tuple(symbols_override) if symbols_override else preset.assets
    timeframe = timeframe_override or preset.timeframe
    if timeframe not in TIMEFRAME_TO_MINUTES:
        timeframe = "1h"
    orion_mode = _normalize_orion_mode(orion_override or preset.orion)
    start_day = preset.start

    if preset.end is None:
        latest = _latest_available_end_date(cache_root=cache_root, symbols=symbols, timeframe=timeframe)
        end_day = latest or start_day
    else:
        end_day = preset.end
    if end_day < start_day:
        end_day = start_day
    return start_day, end_day, symbols, timeframe, orion_mode


def _collect_month_coverage(
    *,
    loader: ReplayLoader,
    symbols: tuple[str, ...],
    timeframe: str,
    month_slice: MonthSlice,
) -> dict[str, int]:
    coverage: dict[str, int] = {}
    start_key = month_slice.start.strftime("%Y-%m-%d %H:%M:%S")
    end_key = month_slice.end.strftime("%Y-%m-%d %H:%M:%S")
    for symbol in symbols:
        try:
            frame = loader.load_ohlcv(symbol=symbol, interval=timeframe, start=start_key, end=end_key, verify=False)
        except Exception:
            frame = pd.DataFrame()
        coverage[symbol] = int(len(frame))
    return coverage


def _run_backtest_slice(
    *,
    run_dir: Path,
    db_path: Path,
    symbols: tuple[str, ...],
    timeframe: str,
    risk_profile: str,
    replay_anchor: datetime,
    cycle_step_minutes: int,
    cycles: int,
    hold_minutes: int,
    orion_enabled: bool,
    timeout_seconds: int,
    use_risk_config: bool,
    risk_config_path: str,
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
        str(int(max(1, cycles))),
        "--cycle-step-minutes",
        str(int(max(1, cycle_step_minutes))),
        "--hold-minutes",
        str(int(max({"1h": 60, "15m": 15, "4h": 240}.get(str(timeframe), 60), hold_minutes))),
        "--symbols",
        ",".join(symbols),
        "--risk-profile",
        str(risk_profile),
        "--replay-now",
        _to_iso_z(replay_anchor),
        "--forward-sim",
        "--timeframe",
        str(timeframe),
    ]
    if orion_enabled:
        cmd.append("--orion")
    if bool(use_risk_config):
        cmd.extend(["--use-risk-config", "--risk-config", str(risk_config_path)])

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "runner_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=max(60, int(timeout_seconds)),
        )
    except subprocess.TimeoutExpired:
        (run_dir / "runner_stdout.log").write_text("", encoding="utf-8")
        (run_dir / "runner_stderr.log").write_text("timeout\n", encoding="utf-8")
        return "FAILED", "timeout"

    (run_dir / "runner_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "runner_stderr.log").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        return "FAILED", f"main_exit_{proc.returncode}"
    return "COMPLETED", "ok"


def _sort_trade_rows(trade_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        list(trade_rows),
        key=lambda row: (
            str(row.get("exit_time") or row.get("entry_time") or ""),
            str(row.get("trade_id") or ""),
            str(row.get("symbol") or ""),
        ),
    )


def _return_total(returns: Iterable[float]) -> float:
    equity = 1.0
    for value in returns:
        equity *= (1.0 + float(value))
    return float(equity - 1.0)


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))


def _max_drawdown_from_returns(returns: Iterable[float]) -> float:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in returns:
        equity *= (1.0 + float(value))
        peak = max(peak, equity)
        dd = (equity / peak) - 1.0 if peak > 0.0 else 0.0
        max_dd = min(max_dd, dd)
    return float(max_dd)


def _metrics_from_returns(returns: Iterable[float]) -> dict[str, float]:
    values = [float(v) for v in returns]
    trades = len(values)
    wins = sum(1 for item in values if item > 0.0)
    expectancy = _mean(values) if values else 0.0
    return {
        "trades": float(trades),
        "win_rate": float((wins / trades) if trades else 0.0),
        "expectancy": float(expectancy),
        "total_return": float(_return_total(values)),
        "max_drawdown": float(_max_drawdown_from_returns(values)),
    }


def _parse_iso_utc_safe(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = pd.to_datetime(raw, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    dt = parsed.to_pydatetime()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _simulate_flipped_trade_rows(trade_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flipped_rows: list[dict[str, Any]] = []
    for row in _sort_trade_rows(trade_rows):
        entry_price = max(_as_float(row.get("entry_price"), 1.0), 1e-9)
        exit_price = max(_as_float(row.get("exit_price"), entry_price), 1e-9)
        original_net = _as_float(row.get("net_pnl_pct"))
        fee_drag = _as_float(row.get("pnl_pct")) - original_net
        side = str(row.get("side") or "long").lower()
        flipped_side = "short" if side == "long" else "long"
        if flipped_side == "short":
            gross = float((entry_price - exit_price) / entry_price)
        else:
            gross = float((exit_price - entry_price) / entry_price)
        flipped_rows.append(
            {
                "scenario": str(row.get("scenario") or ""),
                "trade_id": str(row.get("trade_id") or ""),
                "engine": str(row.get("engine") or "UNKNOWN"),
                "symbol": str(row.get("symbol") or "UNKNOWN"),
                "side": flipped_side,
                "original_side": side,
                "entry_time": str(row.get("entry_time") or ""),
                "exit_time": str(row.get("exit_time") or ""),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "original_net_pnl_pct": float(original_net),
                "net_pnl_pct": float(gross - fee_drag),
            }
        )
    return flipped_rows


def _simulate_early_entry_trade_rows(
    *,
    trade_rows: list[dict[str, Any]],
    loader: ReplayLoader,
    timeframe: str,
    candles_back: int = EARLY_ENTRY_CANDLES_BACK,
) -> list[dict[str, Any]]:
    if not trade_rows:
        return []
    step_minutes = int(TIMEFRAME_TO_MINUTES.get(str(timeframe), 60))
    by_symbol: dict[str, list[tuple[dict[str, Any], datetime, datetime]]] = defaultdict(list)

    for row in _sort_trade_rows(trade_rows):
        entry_dt = _parse_iso_utc_safe(row.get("entry_time"))
        exit_dt = _parse_iso_utc_safe(row.get("exit_time"))
        if entry_dt is None or exit_dt is None:
            continue
        symbol = str(row.get("symbol") or "UNKNOWN")
        by_symbol[symbol].append((row, entry_dt, exit_dt))

    out_rows: list[dict[str, Any]] = []
    for symbol in sorted(by_symbol):
        symbol_rows = by_symbol[symbol]
        earliest_entry = min(item[1] for item in symbol_rows) - timedelta(minutes=step_minutes * (candles_back + 2))
        latest_exit = max(item[2] for item in symbol_rows)
        start_key = earliest_entry.strftime("%Y-%m-%d %H:%M:%S")
        end_key = latest_exit.strftime("%Y-%m-%d %H:%M:%S")
        try:
            candles = loader.load_ohlcv(
                symbol=symbol,
                interval=str(timeframe),
                start=start_key,
                end=end_key,
                verify=False,
            )
        except Exception:
            candles = pd.DataFrame()

        if candles is not None and not candles.empty:
            frame = candles.copy()
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            frame = frame.dropna(subset=["timestamp", "close"]).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
            ts_index = pd.DatetimeIndex(frame["timestamp"])
            close_values = frame["close"].astype(float).tolist()
        else:
            ts_index = pd.DatetimeIndex([])
            close_values = []

        for row, entry_dt, exit_dt in symbol_rows:
            entry_price = max(_as_float(row.get("entry_price"), 1.0), 1e-9)
            exit_price = max(_as_float(row.get("exit_price"), entry_price), 1e-9)
            early_entry_price = entry_price
            early_entry_time = entry_dt

            if len(ts_index) > 0:
                entry_pos = int(ts_index.searchsorted(pd.Timestamp(entry_dt), side="right")) - 1
                exit_pos = int(ts_index.searchsorted(pd.Timestamp(exit_dt), side="right")) - 1
                if entry_pos >= 0 and exit_pos >= 0:
                    early_pos = max(0, entry_pos - int(max(1, candles_back)))
                    early_entry_price = max(float(close_values[early_pos]), 1e-9)
                    exit_price = max(float(close_values[exit_pos]), 1e-9)
                    early_entry_time = ts_index[early_pos].to_pydatetime().astimezone(timezone.utc)

            side = str(row.get("side") or "long").lower()
            original_net = _as_float(row.get("net_pnl_pct"))
            fee_drag = _as_float(row.get("pnl_pct")) - original_net
            if side == "short":
                gross = float((early_entry_price - exit_price) / early_entry_price)
            else:
                gross = float((exit_price - early_entry_price) / early_entry_price)

            out_rows.append(
                {
                    "scenario": str(row.get("scenario") or ""),
                    "trade_id": str(row.get("trade_id") or ""),
                    "engine": str(row.get("engine") or "UNKNOWN"),
                    "symbol": symbol,
                    "side": side,
                    "entry_time": str(row.get("entry_time") or ""),
                    "exit_time": str(row.get("exit_time") or ""),
                    "early_entry_time": _to_iso_z(early_entry_time),
                    "entry_price": float(entry_price),
                    "early_entry_price": float(early_entry_price),
                    "exit_price": float(exit_price),
                    "original_net_pnl_pct": float(original_net),
                    "net_pnl_pct": float(gross - fee_drag),
                }
            )

    return _sort_trade_rows(out_rows)


def _build_flip_comparison_rows(
    *,
    scenario_trade_rows: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenario_rows: list[dict[str, Any]] = []
    engine_rows: list[dict[str, Any]] = []
    for scenario_id in sorted(scenario_trade_rows):
        original_rows = _sort_trade_rows(scenario_trade_rows.get(scenario_id, []))
        flipped_rows = _simulate_flipped_trade_rows(original_rows)
        original_metrics = _metrics_from_returns(_as_float(row.get("net_pnl_pct")) for row in original_rows)
        flipped_metrics = _metrics_from_returns(_as_float(row.get("net_pnl_pct")) for row in flipped_rows)
        label = "DIRECTIONALLY_INVERTED_ENGINE" if flipped_metrics["total_return"] > original_metrics["total_return"] else "NO_CLEAR_INVERSION"
        scenario_rows.append(
            {
                "scenario": scenario_id,
                "trades": int(original_metrics["trades"]),
                "original_total_return": float(original_metrics["total_return"]),
                "flipped_total_return": float(flipped_metrics["total_return"]),
                "original_win_rate": float(original_metrics["win_rate"]),
                "flipped_win_rate": float(flipped_metrics["win_rate"]),
                "original_expectancy": float(original_metrics["expectancy"]),
                "flipped_expectancy": float(flipped_metrics["expectancy"]),
                "original_max_drawdown": float(original_metrics["max_drawdown"]),
                "flipped_max_drawdown": float(flipped_metrics["max_drawdown"]),
                "label": label,
            }
        )

        original_by_engine: dict[str, list[dict[str, Any]]] = defaultdict(list)
        flipped_by_engine: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in original_rows:
            original_by_engine[str(row.get("engine") or "UNKNOWN")].append(row)
        for row in flipped_rows:
            flipped_by_engine[str(row.get("engine") or "UNKNOWN")].append(row)

        for engine in sorted(set(original_by_engine) | set(flipped_by_engine)):
            original_engine_metrics = _metrics_from_returns(
                _as_float(row.get("net_pnl_pct")) for row in original_by_engine.get(engine, [])
            )
            flipped_engine_metrics = _metrics_from_returns(
                _as_float(row.get("net_pnl_pct")) for row in flipped_by_engine.get(engine, [])
            )
            engine_label = (
                "DIRECTIONALLY_INVERTED_ENGINE"
                if flipped_engine_metrics["total_return"] > original_engine_metrics["total_return"]
                else "NO_CLEAR_INVERSION"
            )
            engine_rows.append(
                {
                    "scenario": scenario_id,
                    "engine": engine,
                    "trades": int(original_engine_metrics["trades"]),
                    "original_total_return": float(original_engine_metrics["total_return"]),
                    "flipped_total_return": float(flipped_engine_metrics["total_return"]),
                    "original_win_rate": float(original_engine_metrics["win_rate"]),
                    "flipped_win_rate": float(flipped_engine_metrics["win_rate"]),
                    "original_expectancy": float(original_engine_metrics["expectancy"]),
                    "flipped_expectancy": float(flipped_engine_metrics["expectancy"]),
                    "original_max_drawdown": float(original_engine_metrics["max_drawdown"]),
                    "flipped_max_drawdown": float(flipped_engine_metrics["max_drawdown"]),
                    "label": engine_label,
                }
            )
    return scenario_rows, engine_rows


def _build_early_entry_comparison_rows(
    *,
    scenario_trade_rows: dict[str, list[dict[str, Any]]],
    scenario_timeframes: dict[str, str],
    loader: ReplayLoader,
    candles_back: int = EARLY_ENTRY_CANDLES_BACK,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenario_rows: list[dict[str, Any]] = []
    engine_rows: list[dict[str, Any]] = []
    for scenario_id in sorted(scenario_trade_rows):
        original_rows = _sort_trade_rows(scenario_trade_rows.get(scenario_id, []))
        timeframe = str(scenario_timeframes.get(scenario_id) or "1h")
        early_rows = _simulate_early_entry_trade_rows(
            trade_rows=original_rows,
            loader=loader,
            timeframe=timeframe,
            candles_back=candles_back,
        )
        original_metrics = _metrics_from_returns(_as_float(row.get("net_pnl_pct")) for row in original_rows)
        early_metrics = _metrics_from_returns(_as_float(row.get("net_pnl_pct")) for row in early_rows)
        delta_total_return = float(early_metrics["total_return"] - original_metrics["total_return"])
        label = "LAGGING_ENTRY_ENGINE" if delta_total_return >= LAGGING_ENTRY_DELTA_THRESHOLD else "NO_CLEAR_LAG"
        scenario_rows.append(
            {
                "scenario": scenario_id,
                "timeframe": timeframe,
                "trades": int(original_metrics["trades"]),
                "original_total_return": float(original_metrics["total_return"]),
                "early_total_return": float(early_metrics["total_return"]),
                "delta_total_return": delta_total_return,
                "original_win_rate": float(original_metrics["win_rate"]),
                "early_win_rate": float(early_metrics["win_rate"]),
                "original_expectancy": float(original_metrics["expectancy"]),
                "early_expectancy": float(early_metrics["expectancy"]),
                "original_max_drawdown": float(original_metrics["max_drawdown"]),
                "early_max_drawdown": float(early_metrics["max_drawdown"]),
                "label": label,
            }
        )

        original_by_engine: dict[str, list[dict[str, Any]]] = defaultdict(list)
        early_by_engine: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in original_rows:
            original_by_engine[str(row.get("engine") or "UNKNOWN")].append(row)
        for row in early_rows:
            early_by_engine[str(row.get("engine") or "UNKNOWN")].append(row)

        for engine in sorted(set(original_by_engine) | set(early_by_engine)):
            original_engine_metrics = _metrics_from_returns(
                _as_float(row.get("net_pnl_pct")) for row in original_by_engine.get(engine, [])
            )
            early_engine_metrics = _metrics_from_returns(
                _as_float(row.get("net_pnl_pct")) for row in early_by_engine.get(engine, [])
            )
            delta_engine_return = float(early_engine_metrics["total_return"] - original_engine_metrics["total_return"])
            engine_label = "LAGGING_ENTRY_ENGINE" if delta_engine_return >= LAGGING_ENTRY_DELTA_THRESHOLD else "NO_CLEAR_LAG"
            engine_rows.append(
                {
                    "scenario": scenario_id,
                    "timeframe": timeframe,
                    "engine": engine,
                    "trades": int(original_engine_metrics["trades"]),
                    "original_total_return": float(original_engine_metrics["total_return"]),
                    "early_total_return": float(early_engine_metrics["total_return"]),
                    "delta_total_return": delta_engine_return,
                    "original_win_rate": float(original_engine_metrics["win_rate"]),
                    "early_win_rate": float(early_engine_metrics["win_rate"]),
                    "original_expectancy": float(original_engine_metrics["expectancy"]),
                    "early_expectancy": float(early_engine_metrics["expectancy"]),
                    "original_max_drawdown": float(original_engine_metrics["max_drawdown"]),
                    "early_max_drawdown": float(early_engine_metrics["max_drawdown"]),
                    "label": engine_label,
                }
            )
    return scenario_rows, engine_rows


def _risk_of_ruin_proxy(returns: Iterable[float]) -> tuple[int, float]:
    longest_streak = 0
    current_streak = 0
    max_loss_sum = 0.0
    current_loss_sum = 0.0
    for value in returns:
        ret = float(value)
        if ret < 0.0:
            current_streak += 1
            current_loss_sum += abs(ret)
            longest_streak = max(longest_streak, current_streak)
            max_loss_sum = max(max_loss_sum, current_loss_sum)
        else:
            current_streak = 0
            current_loss_sum = 0.0
    return int(longest_streak), float(max_loss_sum)


def _max_consecutive_losses_for_side(trade_rows: list[dict[str, Any]], side: str) -> int:
    streak = 0
    longest = 0
    target = str(side).lower()
    for row in _sort_trade_rows(trade_rows):
        row_side = str(row.get("side") or "").lower()
        if row_side != target:
            continue
        ret = _as_float(row.get("net_pnl_pct"))
        if ret < 0.0:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    return int(longest)


def _average_rr(returns: list[float]) -> float:
    wins = [float(v) for v in returns if float(v) > 0.0]
    losses = [abs(float(v)) for v in returns if float(v) < 0.0]
    if not wins or not losses:
        return 0.0
    avg_win = float(sum(wins) / len(wins))
    avg_loss = float(sum(losses) / len(losses))
    if avg_loss <= 1e-12:
        return 0.0
    return float(avg_win / avg_loss)


def _group_breakdown(
    *,
    scenario_id: str,
    trade_rows: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trade_rows:
        grouped[str(row.get(key) or "UNKNOWN")].append(row)

    out: list[dict[str, Any]] = []
    for group_name in sorted(grouped):
        rows = _sort_trade_rows(grouped[group_name])
        returns = [_as_float(item.get("net_pnl_pct")) for item in rows]
        trades = len(returns)
        wins = sum(1 for r in returns if r > 0.0)
        out.append(
            {
                "scenario": scenario_id,
                key: group_name,
                "trades": int(trades),
                "win_rate": float((wins / trades) if trades else 0.0),
                "total_return": float(_return_total(returns)),
                "max_drawdown": float(_max_drawdown_from_returns(returns)),
            }
        )
    return out


def aggregate_trade_metrics(trade_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = _sort_trade_rows(trade_rows)
    metrics = _scenario_metrics(ordered)

    returns = [_as_float(item.get("net_pnl_pct")) for item in ordered]
    longest_streak, max_loss_sum = _risk_of_ruin_proxy(returns)
    long_rows = [row for row in ordered if str(row.get("side") or "").lower() == "long"]
    short_rows = [row for row in ordered if str(row.get("side") or "").lower() == "short"]
    long_returns = [_as_float(row.get("net_pnl_pct")) for row in long_rows]
    short_returns = [_as_float(row.get("net_pnl_pct")) for row in short_rows]
    long_leverage = [_as_float(row.get("leverage_used")) for row in long_rows]
    short_leverage = [_as_float(row.get("leverage_used")) for row in short_rows]

    regime_counter: Counter[str] = Counter()
    by_engine: dict[str, list[float]] = defaultdict(list)
    for row in ordered:
        engine = str(row.get("engine") or "UNKNOWN")
        regime = str(row.get("regime_at_entry") or "UNKNOWN")
        ret = _as_float(row.get("net_pnl_pct"))
        regime_counter[regime] += 1
        by_engine[engine].append(ret)

    if by_engine:
        ranked = sorted(
            by_engine.items(),
            key=lambda item: (_return_total(item[1]), -len(item[1]), item[0]),
            reverse=True,
        )
        best_engine = ranked[0][0]
        worst_engine = ranked[-1][0]
    else:
        best_engine = "N/A"
        worst_engine = "N/A"

    regime_dominance = regime_counter.most_common(1)[0][0] if regime_counter else "N/A"

    return {
        "trades": int(metrics["trades"]),
        "win_rate": float(metrics["win_rate"]),
        "avg_return": float(metrics["avg_return"]),
        "total_return": float(metrics["total_return"]),
        "max_drawdown": float(metrics["max_drawdown"]),
        "long_total_return": float(_return_total(long_returns)),
        "short_total_return": float(_return_total(short_returns)),
        "long_win_rate": float((sum(1 for x in long_returns if x > 0.0) / len(long_returns)) if long_returns else 0.0),
        "short_win_rate": float((sum(1 for x in short_returns if x > 0.0) / len(short_returns)) if short_returns else 0.0),
        "long_max_drawdown": float(_max_drawdown_from_returns(long_returns)),
        "short_max_drawdown": float(_max_drawdown_from_returns(short_returns)),
        "long_trade_count": int(len(long_returns)),
        "short_trade_count": int(len(short_returns)),
        "long_avg_rr": float(_average_rr(long_returns)),
        "short_avg_rr": float(_average_rr(short_returns)),
        "long_max_adverse_excursion": float(min(long_returns)) if long_returns else 0.0,
        "short_max_adverse_excursion": float(min(short_returns)) if short_returns else 0.0,
        "best_engine": best_engine,
        "worst_engine": worst_engine,
        "regime_dominance": regime_dominance,
        "longest_losing_streak": int(longest_streak),
        "max_consecutive_loss_pct_sum": float(max_loss_sum),
        "max_consecutive_short_losses": int(_max_consecutive_losses_for_side(ordered, "short")),
        "max_consecutive_long_losses": int(_max_consecutive_losses_for_side(ordered, "long")),
        "leverage_avg_long": float(_mean(long_leverage)),
        "leverage_avg_short": float(_mean(short_leverage)),
    }


def _bear_edge_metrics(trade_rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    ordered = _sort_trade_rows(trade_rows)
    bear_rows = [
        row
        for row in ordered
        if "CRISIS" in str(row.get("regime_at_entry", "")).upper() or "BEAR" in str(row.get("scenario", "")).upper()
    ]
    if not bear_rows:
        return 0.0, 0.0, 0.0
    short_returns = [
        _as_float(row.get("net_pnl_pct"))
        for row in bear_rows
        if str(row.get("side", "")).lower() == "short"
    ]
    long_returns = [
        _as_float(row.get("net_pnl_pct"))
        for row in bear_rows
        if str(row.get("side", "")).lower() == "long"
    ]
    short_ret = _return_total(short_returns)
    long_ret = _return_total(long_returns)
    edge = float(short_ret / abs(long_ret + 1e-6))
    return float(short_ret), float(long_ret), float(edge)


def build_curve_rows(*, scenario_id: str, trade_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = _sort_trade_rows(trade_rows)
    equity = 1.0
    peak = 1.0
    equity_rows: list[dict[str, Any]] = []
    drawdown_rows: list[dict[str, Any]] = []
    for row in ordered:
        ret = _as_float(row.get("net_pnl_pct"))
        equity *= (1.0 + ret)
        peak = max(peak, equity)
        drawdown = (equity / peak) - 1.0 if peak > 0.0 else 0.0
        ts = str(row.get("exit_time") or row.get("entry_time") or "")
        equity_rows.append({"scenario": scenario_id, "timestamp": ts, "equity": float(equity)})
        drawdown_rows.append({"scenario": scenario_id, "timestamp": ts, "drawdown": float(drawdown)})
    return equity_rows, drawdown_rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})


def _write_monthly_trade_export(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "trade_id",
        "symbol",
        "side",
        "engine",
        "entry_time",
        "exit_time",
        "net_pnl_pct",
        "regime_at_entry",
        "regime_at_exit",
        "confidence_at_entry",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "drawdown_during_trade",
        "leverage_used",
        "size_pct_used",
        "stop_distance",
        "tp_distance",
    ]
    _write_csv(path, _sort_trade_rows(rows), headers)


def _write_data_coverage_report(path: Path, coverage_rows: list[CoverageRow]) -> None:
    lines = [
        "# WAR Backtest Data Coverage",
        "",
        "| scenario | month | symbol | bars | status |",
        "|---|---|---|---:|---|",
    ]
    for row in sorted(coverage_rows, key=lambda item: (item.scenario_id, item.month, item.symbol)):
        lines.append(f"| {row.scenario_id} | {row.month} | {row.symbol} | {row.bars} | {row.status} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_bear_edge_report(path: Path, scenario_results: list[ScenarioRunResult]) -> None:
    lines = [
        "# Bear Edge Report",
        "",
        "| scenario | long_return | short_return | bear_short_edge_ratio | long_trades | short_trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(scenario_results, key=lambda x: x.scenario_id):
        lines.append(
            "| {scenario} | {long_ret:.6f} | {short_ret:.6f} | {edge:.6f} | {long_trades} | {short_trades} |".format(
                scenario=row.scenario_id,
                long_ret=row.bear_only_long_return,
                short_ret=row.bear_only_short_return,
                edge=row.bear_short_edge_ratio,
                long_trades=row.long_trade_count,
                short_trades=row.short_trade_count,
            )
        )

    lines.extend(["", "## Dominance Notes", ""])
    for row in sorted(scenario_results, key=lambda x: x.scenario_id):
        if row.short_total_return > row.long_total_return:
            side_note = "short dominates"
        elif row.long_total_return > row.short_total_return:
            side_note = "long dominates"
        else:
            side_note = "balanced"
        lines.append(
            "- {scenario}: {note}; long_return={lr:.6f}, short_return={sr:.6f}, lev_long={lev_long:.4f}, lev_short={lev_short:.4f}.".format(
                scenario=row.scenario_id,
                note=side_note,
                lr=row.long_total_return,
                sr=row.short_total_return,
                lev_long=row.leverage_avg_long,
                lev_short=row.leverage_avg_short,
            )
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_early_entry_report(
    path: Path,
    scenario_rows: list[dict[str, Any]],
    engine_rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Early Entry Report",
        "",
        f"Model: entry shifted {EARLY_ENTRY_CANDLES_BACK} candles earlier, exit unchanged.",
        f"Lag label rule: early_total_return - original_total_return >= {LAGGING_ENTRY_DELTA_THRESHOLD:.2f}.",
        "",
        "| scenario | timeframe | trades | original_total_return | early_total_return | delta_total_return | original_win_rate | early_win_rate | original_expectancy | early_expectancy | original_max_drawdown | early_max_drawdown | label |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(scenario_rows, key=lambda item: str(item.get("scenario"))):
        lines.append(
            "| {scenario} | {timeframe} | {trades} | {orig_ret:.6f} | {early_ret:.6f} | {delta_ret:.6f} | {orig_wr:.4f} | {early_wr:.4f} | {orig_exp:.6f} | {early_exp:.6f} | {orig_dd:.6f} | {early_dd:.6f} | {label} |".format(
                scenario=row.get("scenario"),
                timeframe=row.get("timeframe"),
                trades=int(_as_float(row.get("trades"))),
                orig_ret=_as_float(row.get("original_total_return")),
                early_ret=_as_float(row.get("early_total_return")),
                delta_ret=_as_float(row.get("delta_total_return")),
                orig_wr=_as_float(row.get("original_win_rate")),
                early_wr=_as_float(row.get("early_win_rate")),
                orig_exp=_as_float(row.get("original_expectancy")),
                early_exp=_as_float(row.get("early_expectancy")),
                orig_dd=_as_float(row.get("original_max_drawdown")),
                early_dd=_as_float(row.get("early_max_drawdown")),
                label=row.get("label"),
            )
        )

    lines.extend(
        [
            "",
            "## Engine Breakdown",
            "",
            "| scenario | timeframe | engine | trades | original_total_return | early_total_return | delta_total_return | original_win_rate | early_win_rate | original_expectancy | early_expectancy | original_max_drawdown | early_max_drawdown | label |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in sorted(engine_rows, key=lambda item: (str(item.get("scenario")), str(item.get("engine")))):
        lines.append(
            "| {scenario} | {timeframe} | {engine} | {trades} | {orig_ret:.6f} | {early_ret:.6f} | {delta_ret:.6f} | {orig_wr:.4f} | {early_wr:.4f} | {orig_exp:.6f} | {early_exp:.6f} | {orig_dd:.6f} | {early_dd:.6f} | {label} |".format(
                scenario=row.get("scenario"),
                timeframe=row.get("timeframe"),
                engine=row.get("engine"),
                trades=int(_as_float(row.get("trades"))),
                orig_ret=_as_float(row.get("original_total_return")),
                early_ret=_as_float(row.get("early_total_return")),
                delta_ret=_as_float(row.get("delta_total_return")),
                orig_wr=_as_float(row.get("original_win_rate")),
                early_wr=_as_float(row.get("early_win_rate")),
                orig_exp=_as_float(row.get("original_expectancy")),
                early_exp=_as_float(row.get("early_expectancy")),
                orig_dd=_as_float(row.get("original_max_drawdown")),
                early_dd=_as_float(row.get("early_max_drawdown")),
                label=row.get("label"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_flip_comparison_report(
    path: Path,
    scenario_rows: list[dict[str, Any]],
    engine_rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Flip Comparison Report",
        "",
        "Model: each long trade simulated as short and each short trade simulated as long.",
        "Inversion label rule: flipped_total_return > original_total_return.",
        "",
        "| scenario | trades | original_total_return | flipped_total_return | original_win_rate | flipped_win_rate | original_expectancy | flipped_expectancy | original_max_drawdown | flipped_max_drawdown | label |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(scenario_rows, key=lambda item: str(item.get("scenario"))):
        lines.append(
            "| {scenario} | {trades} | {orig_ret:.6f} | {flip_ret:.6f} | {orig_wr:.4f} | {flip_wr:.4f} | {orig_exp:.6f} | {flip_exp:.6f} | {orig_dd:.6f} | {flip_dd:.6f} | {label} |".format(
                scenario=row.get("scenario"),
                trades=int(_as_float(row.get("trades"))),
                orig_ret=_as_float(row.get("original_total_return")),
                flip_ret=_as_float(row.get("flipped_total_return")),
                orig_wr=_as_float(row.get("original_win_rate")),
                flip_wr=_as_float(row.get("flipped_win_rate")),
                orig_exp=_as_float(row.get("original_expectancy")),
                flip_exp=_as_float(row.get("flipped_expectancy")),
                orig_dd=_as_float(row.get("original_max_drawdown")),
                flip_dd=_as_float(row.get("flipped_max_drawdown")),
                label=row.get("label"),
            )
        )

    lines.extend(
        [
            "",
            "## Engine Breakdown",
            "",
            "| scenario | engine | trades | original_total_return | flipped_total_return | original_win_rate | flipped_win_rate | original_expectancy | flipped_expectancy | original_max_drawdown | flipped_max_drawdown | label |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in sorted(engine_rows, key=lambda item: (str(item.get("scenario")), str(item.get("engine")))):
        lines.append(
            "| {scenario} | {engine} | {trades} | {orig_ret:.6f} | {flip_ret:.6f} | {orig_wr:.4f} | {flip_wr:.4f} | {orig_exp:.6f} | {flip_exp:.6f} | {orig_dd:.6f} | {flip_dd:.6f} | {label} |".format(
                scenario=row.get("scenario"),
                engine=row.get("engine"),
                trades=int(_as_float(row.get("trades"))),
                orig_ret=_as_float(row.get("original_total_return")),
                flip_ret=_as_float(row.get("flipped_total_return")),
                orig_wr=_as_float(row.get("original_win_rate")),
                flip_wr=_as_float(row.get("flipped_win_rate")),
                orig_exp=_as_float(row.get("original_expectancy")),
                flip_exp=_as_float(row.get("flipped_expectancy")),
                orig_dd=_as_float(row.get("original_max_drawdown")),
                flip_dd=_as_float(row.get("flipped_max_drawdown")),
                label=row.get("label"),
            )
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_summary_markdown(path: Path, scenario_results: list[ScenarioRunResult]) -> None:
    lines: list[str] = [
        "# WAR Backtest Scenario Summary",
        "",
        f"Generated at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "| scenario | status | trades | win_rate | total_return | long_return | short_return | max_drawdown | lev_avg_long | lev_avg_short | best_engine | worst_engine | regime_dominance | longest_losing_streak | max_consecutive_loss_pct_sum |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|",
    ]
    for result in sorted(scenario_results, key=lambda item: item.scenario_id):
        lines.append(
            "| {scenario} | {status} | {trades} | {win_rate:.4f} | {total_return:.6f} | {long_return:.6f} | {short_return:.6f} | {max_drawdown:.6f} | {lev_long:.4f} | {lev_short:.4f} | "
            "{best_engine} | {worst_engine} | {regime_dominance} | {losing} | {loss_sum:.6f} |".format(
                scenario=result.scenario_id,
                status=result.status,
                trades=int(result.trades),
                win_rate=result.win_rate,
                total_return=result.total_return,
                long_return=result.long_total_return,
                short_return=result.short_total_return,
                max_drawdown=result.max_drawdown,
                lev_long=result.leverage_avg_long,
                lev_short=result.leverage_avg_short,
                best_engine=result.best_engine,
                worst_engine=result.worst_engine,
                regime_dominance=result.regime_dominance,
                losing=int(result.longest_losing_streak),
                loss_sum=result.max_consecutive_loss_pct_sum,
            )
        )

    for result in sorted(scenario_results, key=lambda item: item.scenario_id):
        lines.extend(
            [
                "",
                f"## {result.scenario_id}",
                "",
                f"- status: {result.status} ({result.reason})",
                f"- range: {result.start.isoformat()} -> {result.end.isoformat()}",
                f"- symbols: {','.join(result.symbols)}",
                f"- timeframe: {result.timeframe}",
                f"- risk_profile: {result.risk_profile}",
                f"- orion: {'on' if result.orion_enabled else 'off'}",
                f"- long/short trades: {result.long_trade_count}/{result.short_trade_count}",
                f"- long/short returns: {result.long_total_return:.6f}/{result.short_total_return:.6f}",
                f"- leverage avg long/short: {result.leverage_avg_long:.4f}/{result.leverage_avg_short:.4f}",
                f"- bear edge ratio: {result.bear_short_edge_ratio:.6f}",
                "",
                "| month | status | reason | cycles | trades | win_rate | total_return | max_drawdown | long_trades | short_trades | long_return | short_return | long_max_dd | short_max_dd | lev_avg_long | lev_avg_short |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for month in result.months:
            lines.append(
                "| {month} | {status} | {reason} | {cycles} | {trades} | {win_rate:.4f} | {total_return:.6f} | {max_drawdown:.6f} | {long_trades} | {short_trades} | {long_return:.6f} | {short_return:.6f} | {long_dd:.6f} | {short_dd:.6f} | {lev_long:.4f} | {lev_short:.4f} |".format(
                    month=month.month,
                    status=month.status,
                    reason=month.reason,
                    cycles=int(month.cycles),
                    trades=int(month.trades),
                    win_rate=month.win_rate,
                    total_return=month.total_return,
                    max_drawdown=month.max_drawdown,
                    long_trades=int(month.long_trade_count),
                    short_trades=int(month.short_trade_count),
                    long_return=month.long_total_return,
                    short_return=month.short_total_return,
                    long_dd=month.long_max_drawdown,
                    short_dd=month.short_max_drawdown,
                    lev_long=month.leverage_avg_long,
                    lev_short=month.leverage_avg_short,
                )
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_scenario_variant(
    *,
    scenario_name: str,
    scenario_id: str,
    start_day: date,
    end_day: date,
    symbols: tuple[str, ...],
    timeframe: str,
    risk_profile: str,
    orion_enabled: bool,
    output_root: Path,
    loader: ReplayLoader,
    max_cycles_cap: int | None,
    scenario_timeout: int,
    hold_minutes: int,
    export_monthly_trades_csv: bool,
    use_risk_config: bool,
    risk_config_path: str,
) -> tuple[
    ScenarioRunResult,
    list[CoverageRow],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    scenario_dir = output_root / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    month_slices = generate_month_slices(start_day, end_day)

    coverage_rows: list[CoverageRow] = []
    month_results: list[MonthRunResult] = []
    all_trade_rows: list[dict[str, Any]] = []
    cycles_used = 0
    cycle_step_minutes = TIMEFRAME_TO_MINUTES.get(timeframe, 60)
    monthly_trades_export_dir = scenario_dir / "monthly_trades"

    for month_slice in month_slices:
        month_dir = scenario_dir / month_slice.label
        month_dir.mkdir(parents=True, exist_ok=True)
        db_path = month_dir / "war_backtest_lab_v25.db"
        month_result = MonthRunResult(month=month_slice.label, status="FAILED", reason="not_started", run_dir=month_dir)

        coverage = _collect_month_coverage(
            loader=loader,
            symbols=symbols,
            timeframe=timeframe,
            month_slice=month_slice,
        )
        for symbol in sorted(coverage):
            bars = int(coverage[symbol])
            coverage_rows.append(
                CoverageRow(
                    scenario_id=scenario_id,
                    month=month_slice.label,
                    symbol=symbol,
                    bars=bars,
                    status="OK" if bars > 0 else "MISSING",
                )
            )

        missing = sorted(symbol for symbol, bars in coverage.items() if int(bars) <= 0)
        if missing:
            month_result.status = "SKIPPED_DATA_MISSING"
            month_result.reason = "missing:" + ",".join(missing)
            month_results.append(month_result)
            (month_dir / "month_status.json").write_text(
                json.dumps(
                    {
                        "scenario_id": scenario_id,
                        "month": month_slice.label,
                        "status": month_result.status,
                        "reason": month_result.reason,
                        "symbols": list(symbols),
                    },
                    indent=2,
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            continue

        bars_in_month = min(int(coverage[symbol]) for symbol in coverage)
        if bars_in_month <= 0:
            month_result.status = "SKIPPED_DATA_MISSING"
            month_result.reason = "no_bars"
            month_results.append(month_result)
            continue

        cycles = int(max(1, bars_in_month))
        if max_cycles_cap is not None:
            remaining = int(max_cycles_cap) - int(cycles_used)
            if remaining <= 0:
                month_result.status = "SKIPPED_CYCLE_CAP"
                month_result.reason = "max_cycles_per_scenario_reached"
                month_results.append(month_result)
                continue
            cycles = min(cycles, remaining)
        month_result.cycles = int(cycles)

        status, reason = _run_backtest_slice(
            run_dir=month_dir,
            db_path=db_path,
            symbols=symbols,
            timeframe=timeframe,
            risk_profile=risk_profile,
            replay_anchor=month_slice.start,
            cycle_step_minutes=cycle_step_minutes,
            cycles=cycles,
            hold_minutes=hold_minutes,
            orion_enabled=orion_enabled,
            timeout_seconds=scenario_timeout,
            use_risk_config=bool(use_risk_config),
            risk_config_path=str(risk_config_path),
        )
        month_result.status = status
        month_result.reason = reason
        cycles_used += int(cycles)

        if status == "COMPLETED":
            decisions = _load_decisions(db_path)
            trades = _load_closed_trades(db_path)
            decisions_by_symbol = _build_decision_lookup(decisions)
            trade_rows = _build_trade_analytics(
                run_dir=month_dir,
                scenario_id=f"{scenario_id}:{month_slice.label}",
                trades=trades,
                decisions_by_symbol=decisions_by_symbol,
                loader=loader,
            )
            _write_equity_curves(month_dir, trades)
            if export_monthly_trades_csv:
                monthly_trades_export_dir.mkdir(parents=True, exist_ok=True)
                _write_monthly_trade_export(monthly_trades_export_dir / f"{month_slice.label}.csv", trade_rows)
            all_trade_rows.extend(trade_rows)

            metrics = _scenario_metrics(trade_rows)
            side_metrics = aggregate_trade_metrics(trade_rows)
            month_result.trades = int(metrics["trades"])
            month_result.win_rate = float(metrics["win_rate"])
            month_result.avg_return = float(metrics["avg_return"])
            month_result.total_return = float(metrics["total_return"])
            month_result.max_drawdown = float(metrics["max_drawdown"])
            month_result.long_trade_count = int(side_metrics["long_trade_count"])
            month_result.short_trade_count = int(side_metrics["short_trade_count"])
            month_result.long_total_return = float(side_metrics["long_total_return"])
            month_result.short_total_return = float(side_metrics["short_total_return"])
            month_result.long_max_drawdown = float(side_metrics["long_max_drawdown"])
            month_result.short_max_drawdown = float(side_metrics["short_max_drawdown"])
            month_result.leverage_avg_long = float(side_metrics["leverage_avg_long"])
            month_result.leverage_avg_short = float(side_metrics["leverage_avg_short"])

        (month_dir / "month_status.json").write_text(
            json.dumps(
                {
                    "scenario_id": scenario_id,
                    "month": month_slice.label,
                    "status": month_result.status,
                    "reason": month_result.reason,
                    "cycles": int(month_result.cycles),
                    "symbols": list(symbols),
                    "timeframe": timeframe,
                    "risk_profile": risk_profile,
                    "orion_enabled": bool(orion_enabled),
                    "range_start": _to_iso_z(month_slice.start),
                    "range_end": _to_iso_z(month_slice.end),
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        month_results.append(month_result)

    completed_months = sum(1 for row in month_results if row.status == "COMPLETED")
    failed_months = sum(1 for row in month_results if row.status == "FAILED")
    skipped_missing = sum(1 for row in month_results if row.status == "SKIPPED_DATA_MISSING")
    if completed_months > 0:
        scenario_status = "COMPLETED"
        scenario_reason = "ok"
    elif failed_months > 0:
        scenario_status = "FAILED"
        scenario_reason = "all_months_failed"
    elif skipped_missing > 0:
        scenario_status = "SKIPPED_DATA_MISSING"
        scenario_reason = "no_month_with_full_data"
    else:
        scenario_status = "SKIPPED"
        scenario_reason = "no_runnable_month"

    aggregate = aggregate_trade_metrics(all_trade_rows)
    bear_short_ret, bear_long_ret, bear_edge_ratio = _bear_edge_metrics(all_trade_rows)
    scenario_result = ScenarioRunResult(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        status=scenario_status,
        reason=scenario_reason,
        run_dir=scenario_dir,
        start=start_day,
        end=end_day,
        symbols=symbols,
        timeframe=timeframe,
        risk_profile=risk_profile,
        orion_enabled=orion_enabled,
        months=month_results,
        trades=int(aggregate["trades"]),
        win_rate=float(aggregate["win_rate"]),
        avg_return=float(aggregate["avg_return"]),
        total_return=float(aggregate["total_return"]),
        max_drawdown=float(aggregate["max_drawdown"]),
        long_total_return=float(aggregate["long_total_return"]),
        short_total_return=float(aggregate["short_total_return"]),
        long_win_rate=float(aggregate["long_win_rate"]),
        short_win_rate=float(aggregate["short_win_rate"]),
        long_max_drawdown=float(aggregate["long_max_drawdown"]),
        short_max_drawdown=float(aggregate["short_max_drawdown"]),
        long_trade_count=int(aggregate["long_trade_count"]),
        short_trade_count=int(aggregate["short_trade_count"]),
        long_avg_rr=float(aggregate["long_avg_rr"]),
        short_avg_rr=float(aggregate["short_avg_rr"]),
        long_max_adverse_excursion=float(aggregate["long_max_adverse_excursion"]),
        short_max_adverse_excursion=float(aggregate["short_max_adverse_excursion"]),
        bear_only_short_return=float(bear_short_ret),
        bear_only_long_return=float(bear_long_ret),
        bear_short_edge_ratio=float(bear_edge_ratio),
        best_engine=str(aggregate["best_engine"]),
        worst_engine=str(aggregate["worst_engine"]),
        regime_dominance=str(aggregate["regime_dominance"]),
        longest_losing_streak=int(aggregate["longest_losing_streak"]),
        max_consecutive_loss_pct_sum=float(aggregate["max_consecutive_loss_pct_sum"]),
        max_consecutive_short_losses=int(aggregate["max_consecutive_short_losses"]),
        max_consecutive_long_losses=int(aggregate["max_consecutive_long_losses"]),
        leverage_avg_long=float(aggregate["leverage_avg_long"]),
        leverage_avg_short=float(aggregate["leverage_avg_short"]),
    )

    engine_breakdown = _group_breakdown(scenario_id=scenario_id, trade_rows=_sort_trade_rows(all_trade_rows), key="engine")
    regime_breakdown = _group_breakdown(
        scenario_id=scenario_id,
        trade_rows=_sort_trade_rows(all_trade_rows),
        key="regime_at_entry",
    )
    equity_rows, drawdown_rows = build_curve_rows(scenario_id=scenario_id, trade_rows=all_trade_rows)

    scenario_payload = {
        "scenario_id": scenario_result.scenario_id,
        "status": scenario_result.status,
        "reason": scenario_result.reason,
        "start": scenario_result.start.isoformat(),
        "end": scenario_result.end.isoformat(),
        "symbols": list(scenario_result.symbols),
        "timeframe": scenario_result.timeframe,
        "risk_profile": scenario_result.risk_profile,
        "orion_enabled": scenario_result.orion_enabled,
        "trades": int(scenario_result.trades),
        "win_rate": float(scenario_result.win_rate),
        "avg_return": float(scenario_result.avg_return),
        "total_return": float(scenario_result.total_return),
        "max_drawdown": float(scenario_result.max_drawdown),
        "long_total_return": float(scenario_result.long_total_return),
        "short_total_return": float(scenario_result.short_total_return),
        "long_win_rate": float(scenario_result.long_win_rate),
        "short_win_rate": float(scenario_result.short_win_rate),
        "long_max_drawdown": float(scenario_result.long_max_drawdown),
        "short_max_drawdown": float(scenario_result.short_max_drawdown),
        "long_trade_count": int(scenario_result.long_trade_count),
        "short_trade_count": int(scenario_result.short_trade_count),
        "long_avg_rr": float(scenario_result.long_avg_rr),
        "short_avg_rr": float(scenario_result.short_avg_rr),
        "long_max_adverse_excursion": float(scenario_result.long_max_adverse_excursion),
        "short_max_adverse_excursion": float(scenario_result.short_max_adverse_excursion),
        "bear_only_short_return": float(scenario_result.bear_only_short_return),
        "bear_only_long_return": float(scenario_result.bear_only_long_return),
        "bear_short_edge_ratio": float(scenario_result.bear_short_edge_ratio),
        "best_engine": scenario_result.best_engine,
        "worst_engine": scenario_result.worst_engine,
        "regime_dominance": scenario_result.regime_dominance,
        "longest_losing_streak": int(scenario_result.longest_losing_streak),
        "max_consecutive_loss_pct_sum": float(scenario_result.max_consecutive_loss_pct_sum),
        "max_consecutive_short_losses": int(scenario_result.max_consecutive_short_losses),
        "max_consecutive_long_losses": int(scenario_result.max_consecutive_long_losses),
        "leverage_avg_long": float(scenario_result.leverage_avg_long),
        "leverage_avg_short": float(scenario_result.leverage_avg_short),
    }
    (scenario_dir / "scenario_status.json").write_text(
        json.dumps(scenario_payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return scenario_result, coverage_rows, engine_breakdown, regime_breakdown, equity_rows, drawdown_rows, all_trade_rows


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    scenarios_file = PROJECT_ROOT / str(args.scenarios_file)
    if not scenarios_file.exists():
        raise FileNotFoundError(f"scenarios file not found: {scenarios_file}")
    scenarios = load_scenario_presets(scenarios_file)
    if not scenarios:
        raise ValueError("no scenarios found in scenarios file")

    selected: list[ScenarioPreset] = []
    if str(args.scenario).strip().lower() == "all":
        selected = [scenarios[name] for name in sorted(scenarios)]
    else:
        scenario_name = str(args.scenario).strip()
        if scenario_name not in scenarios:
            raise ValueError(f"unknown scenario: {scenario_name}")
        selected = [scenarios[scenario_name]]

    symbols_override = _parse_symbols(args.symbols)
    timeframe_override = str(args.timeframe) if args.timeframe else None
    orion_override = str(args.orion) if args.orion else None

    if args.output_dir:
        output_root = PROJECT_ROOT / str(args.output_dir)
    else:
        now_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        scenario_tag = selected[0].name if len(selected) == 1 else "all"
        output_root = PROJECT_ROOT / "runs" / "war_backtest_lab" / scenario_tag / now_tag
    output_root.mkdir(parents=True, exist_ok=True)

    reports_dir = PROJECT_ROOT / str(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    loader = ReplayLoader(root=args.cache_root)

    summary_rows: list[dict[str, Any]] = []
    coverage_rows: list[CoverageRow] = []
    engine_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    drawdown_rows: list[dict[str, Any]] = []
    scenario_results: list[ScenarioRunResult] = []
    scenario_trade_rows: dict[str, list[dict[str, Any]]] = {}
    scenario_timeframes: dict[str, str] = {}

    for preset in selected:
        start_day, end_day, symbols, timeframe, orion_mode = _resolve_scenario(
            preset=preset,
            cache_root=str(args.cache_root),
            symbols_override=symbols_override,
            timeframe_override=timeframe_override,
            orion_override=orion_override,
        )
        orion_matrix = [False, True] if orion_mode == "matrix" else [orion_mode == "on"]

        for orion_enabled in orion_matrix:
            scenario_id = f"{preset.name}__orion_{'on' if orion_enabled else 'off'}"
            result, cov_rows, eng_rows, reg_rows, eq_rows, dd_rows, trade_rows = _run_scenario_variant(
                scenario_name=preset.name,
                scenario_id=scenario_id,
                start_day=start_day,
                end_day=end_day,
                symbols=symbols,
                timeframe=timeframe,
                risk_profile=preset.risk_profile,
                orion_enabled=orion_enabled,
                output_root=output_root,
                loader=loader,
                max_cycles_cap=args.max_cycles_per_scenario,
                scenario_timeout=int(args.scenario_timeout),
                hold_minutes=max(1, int(args.hold_minutes)),
                export_monthly_trades_csv=bool(args.export_monthly_trades_csv),
                use_risk_config=bool(args.use_risk_config),
                risk_config_path=str(args.risk_config),
            )
            scenario_results.append(result)
            coverage_rows.extend(cov_rows)
            engine_rows.extend(eng_rows)
            regime_rows.extend(reg_rows)
            equity_rows.extend(eq_rows)
            drawdown_rows.extend(dd_rows)
            scenario_trade_rows[result.scenario_id] = _sort_trade_rows(trade_rows)
            scenario_timeframes[result.scenario_id] = str(result.timeframe)

            summary_rows.append(
                {
                    "scenario": result.scenario_id,
                    "status": result.status,
                    "reason": result.reason,
                    "start": result.start.isoformat(),
                    "end": result.end.isoformat(),
                    "symbols": ",".join(result.symbols),
                    "timeframe": result.timeframe,
                    "risk_profile": result.risk_profile,
                    "orion_enabled": int(result.orion_enabled),
                    "months_total": len(result.months),
                    "months_completed": sum(1 for month in result.months if month.status == "COMPLETED"),
                    "months_skipped_data_missing": sum(
                        1 for month in result.months if month.status == "SKIPPED_DATA_MISSING"
                    ),
                    "trades": int(result.trades),
                    "win_rate": float(result.win_rate),
                    "avg_return": float(result.avg_return),
                    "total_return": float(result.total_return),
                    "max_drawdown": float(result.max_drawdown),
                    "long_total_return": float(result.long_total_return),
                    "short_total_return": float(result.short_total_return),
                    "long_win_rate": float(result.long_win_rate),
                    "short_win_rate": float(result.short_win_rate),
                    "long_max_drawdown": float(result.long_max_drawdown),
                    "short_max_drawdown": float(result.short_max_drawdown),
                    "long_trade_count": int(result.long_trade_count),
                    "short_trade_count": int(result.short_trade_count),
                    "long_avg_rr": float(result.long_avg_rr),
                    "short_avg_rr": float(result.short_avg_rr),
                    "long_max_adverse_excursion": float(result.long_max_adverse_excursion),
                    "short_max_adverse_excursion": float(result.short_max_adverse_excursion),
                    "bear_only_short_return": float(result.bear_only_short_return),
                    "bear_only_long_return": float(result.bear_only_long_return),
                    "bear_short_edge_ratio": float(result.bear_short_edge_ratio),
                    "best_engine": result.best_engine,
                    "worst_engine": result.worst_engine,
                    "regime_dominance": result.regime_dominance,
                    "longest_losing_streak": int(result.longest_losing_streak),
                    "max_consecutive_loss_pct_sum": float(result.max_consecutive_loss_pct_sum),
                    "max_consecutive_short_losses": int(result.max_consecutive_short_losses),
                    "max_consecutive_long_losses": int(result.max_consecutive_long_losses),
                    "leverage_avg_long": float(result.leverage_avg_long),
                    "leverage_avg_short": float(result.leverage_avg_short),
                    "run_dir": str(result.run_dir),
                }
            )

    summary_csv = reports_dir / "WAR_BACKTEST_SCENARIO_SUMMARY.csv"
    summary_md = reports_dir / "WAR_BACKTEST_SCENARIO_SUMMARY.md"
    engine_csv = reports_dir / "WAR_BACKTEST_ENGINE_BREAKDOWN.csv"
    regime_csv = reports_dir / "WAR_BACKTEST_REGIME_BREAKDOWN.csv"
    equity_csv = reports_dir / "WAR_BACKTEST_EQUITY_CURVE.csv"
    drawdown_csv = reports_dir / "WAR_BACKTEST_DRAWDOWN_CURVE.csv"
    coverage_md = reports_dir / "WAR_BACKTEST_DATA_COVERAGE.md"
    long_short_csv = reports_dir / "LONG_SHORT_BREAKDOWN.csv"
    bear_edge_md = reports_dir / "BEAR_EDGE_REPORT.md"
    early_entry_md = reports_dir / "EARLY_ENTRY_REPORT.md"
    flip_comparison_md = reports_dir / "FLIP_COMPARISON_REPORT.md"

    _write_csv(
        summary_csv,
        sorted(summary_rows, key=lambda row: str(row.get("scenario"))),
        [
            "scenario",
            "status",
            "reason",
            "start",
            "end",
            "symbols",
            "timeframe",
            "risk_profile",
            "orion_enabled",
            "months_total",
            "months_completed",
            "months_skipped_data_missing",
            "trades",
            "win_rate",
            "avg_return",
            "total_return",
            "max_drawdown",
            "long_total_return",
            "short_total_return",
            "long_win_rate",
            "short_win_rate",
            "long_max_drawdown",
            "short_max_drawdown",
            "long_trade_count",
            "short_trade_count",
            "long_avg_rr",
            "short_avg_rr",
            "long_max_adverse_excursion",
            "short_max_adverse_excursion",
            "bear_only_short_return",
            "bear_only_long_return",
            "bear_short_edge_ratio",
            "best_engine",
            "worst_engine",
            "regime_dominance",
            "longest_losing_streak",
            "max_consecutive_loss_pct_sum",
            "max_consecutive_short_losses",
            "max_consecutive_long_losses",
            "leverage_avg_long",
            "leverage_avg_short",
            "run_dir",
        ],
    )
    _write_summary_markdown(summary_md, scenario_results)
    _write_csv(
        engine_csv,
        sorted(engine_rows, key=lambda row: (str(row.get("scenario")), str(row.get("engine", "")))),
        ["scenario", "engine", "trades", "win_rate", "total_return", "max_drawdown"],
    )
    _write_csv(
        regime_csv,
        sorted(regime_rows, key=lambda row: (str(row.get("scenario")), str(row.get("regime_at_entry", "")))),
        ["scenario", "regime_at_entry", "trades", "win_rate", "total_return", "max_drawdown"],
    )
    _write_csv(
        equity_csv,
        sorted(equity_rows, key=lambda row: (str(row.get("scenario")), str(row.get("timestamp")))),
        ["scenario", "timestamp", "equity"],
    )
    _write_csv(
        drawdown_csv,
        sorted(drawdown_rows, key=lambda row: (str(row.get("scenario")), str(row.get("timestamp")))),
        ["scenario", "timestamp", "drawdown"],
    )
    _write_data_coverage_report(coverage_md, coverage_rows)
    _write_csv(
        long_short_csv,
        sorted(summary_rows, key=lambda row: str(row.get("scenario"))),
        [
            "scenario",
            "status",
            "long_total_return",
            "short_total_return",
            "long_win_rate",
            "short_win_rate",
            "long_max_drawdown",
            "short_max_drawdown",
            "long_trade_count",
            "short_trade_count",
            "long_avg_rr",
            "short_avg_rr",
            "long_max_adverse_excursion",
            "short_max_adverse_excursion",
            "leverage_avg_long",
            "leverage_avg_short",
            "max_consecutive_short_losses",
            "max_consecutive_long_losses",
        ],
    )
    _write_bear_edge_report(bear_edge_md, scenario_results)
    early_scenario_rows, early_engine_rows = _build_early_entry_comparison_rows(
        scenario_trade_rows=scenario_trade_rows,
        scenario_timeframes=scenario_timeframes,
        loader=loader,
    )
    flip_scenario_rows, flip_engine_rows = _build_flip_comparison_rows(
        scenario_trade_rows=scenario_trade_rows,
    )
    _write_early_entry_report(early_entry_md, early_scenario_rows, early_engine_rows)
    _write_flip_comparison_report(flip_comparison_md, flip_scenario_rows, flip_engine_rows)

    print(f"[war_backtest_lab] output_root={output_root}")
    print(f"[war_backtest_lab] summary={summary_md}")
    print(f"[war_backtest_lab] summary_csv={summary_csv}")
    print(f"[war_backtest_lab] coverage={coverage_md}")
    print(f"[war_backtest_lab] long_short={long_short_csv}")
    print(f"[war_backtest_lab] bear_edge={bear_edge_md}")
    print(f"[war_backtest_lab] early_entry={early_entry_md}")
    print(f"[war_backtest_lab] flip_comparison={flip_comparison_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
