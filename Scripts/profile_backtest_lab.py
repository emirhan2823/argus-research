#!/usr/bin/env python3
"""Strategy-profile backtest lab with optional SONAR listing simulation.

This script runs a fixed replay window across multiple strategy-profile
variants, ranks the outcomes, and writes a best-profile YAML for promotion.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.local_store import LocalStore  # noqa: E402
from src.data.replay_loader import ReplayLoader  # noqa: E402


@dataclass(frozen=True)
class VariantResult:
    name: str
    run_dir: Path
    config_path: Path
    enabled: bool
    return_code: int
    trades: int
    win_rate: float
    total_return: float
    profit_factor: float
    max_drawdown: float
    long_trades: int
    short_trades: int
    long_return: float
    short_return: float
    score: float


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run strategy-profile matrix backtests and rank variants.",
    )
    parser.add_argument("--replay-start", required=True, help="UTC start, e.g. 2024-02-24T00:00:00Z")
    parser.add_argument("--replay-end", required=True, help="UTC end, e.g. 2024-03-26T23:00:00Z")
    parser.add_argument("--timeframe", default="1h", help="Backtest timeframe (default: 1h)")
    parser.add_argument("--cycle-step-minutes", type=int, default=60, help="Cycle step minutes (default: 60)")
    parser.add_argument("--hold-minutes", type=int, default=30, help="Synthetic hold minutes (default: 30)")
    parser.add_argument(
        "--risk-profile",
        choices=["strict", "normal", "relaxed"],
        default="normal",
        help="Risk profile passed to src.main",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help=(
            "Optional fixed symbols list. Leave empty when using --backtest-sonar "
            "so dynamic universe can drive symbols."
        ),
    )
    parser.add_argument("--backtest-sonar", action="store_true", default=False, help="Enable SONAR in backtest runs.")
    parser.add_argument(
        "--profile-config",
        default="config/strategy_profiles.yaml",
        help="Base strategy profile YAML path.",
    )
    parser.add_argument(
        "--run-root",
        default="runs/profile_backtest_lab",
        help="Output directory for campaign artifacts.",
    )
    parser.add_argument(
        "--main-timeout-seconds",
        type=int,
        default=5400,
        help="Timeout for each src.main invocation.",
    )
    parser.add_argument(
        "--inject-synthetic-listing",
        action="store_true",
        default=False,
        help="Create a synthetic listed coin from local replay data before campaign.",
    )
    parser.add_argument(
        "--synthetic-symbol",
        default="HYPESIMUSDT",
        help="Synthetic symbol name for listing simulation.",
    )
    parser.add_argument(
        "--synthetic-source",
        default="BTCUSDT",
        help="Source symbol used to generate synthetic OHLCV.",
    )
    parser.add_argument(
        "--synthetic-listing-time",
        default=None,
        help="UTC listing time for synthetic symbol. Default: replay-start + 2 days.",
    )
    parser.add_argument(
        "--synthetic-price-scale",
        type=float,
        default=0.06,
        help="Price scaling for synthetic symbol (default: 0.06).",
    )
    parser.add_argument(
        "--synthetic-volume-mult",
        type=float,
        default=6.0,
        help="Volume multiplier for synthetic symbol (default: 6.0).",
    )
    parser.add_argument(
        "--cache-root",
        default="data/binance",
        help="Replay cache root for synthetic listing generation.",
    )
    return parser.parse_args(argv)


def _parse_symbols(raw: str | None) -> list[str]:
    if raw is None:
        return []
    symbols: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        sym = str(part).strip().upper().replace("/", "").replace("-", "").replace("_", "")
        if not sym or sym in seen:
            continue
        seen.add(sym)
        symbols.append(sym)
    return symbols


def _parse_utc_datetime(text: str) -> datetime:
    dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _deepcopy_json(node: Any) -> Any:
    return json.loads(json.dumps(node))


def _load_strategy_profile_node(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid yaml mapping at {path}")
    node = payload.get("strategy_profiles", payload)
    if not isinstance(node, dict):
        raise ValueError("strategy_profiles node must be a mapping")
    return _deepcopy_json(node)


def _iter_profile_rows(cfg: dict[str, Any]):
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        return
    for setup, setup_node in profiles.items():
        if not isinstance(setup_node, dict):
            continue
        for side, side_node in setup_node.items():
            if not isinstance(side_node, dict):
                continue
            for vol_bucket, row in side_node.items():
                if not isinstance(row, dict):
                    continue
                yield str(setup), str(side), str(vol_bucket), row


def _tweak_rows(
    cfg: dict[str, Any],
    *,
    setups: set[str] | None = None,
    sides: set[str] | None = None,
    vol_buckets: set[str] | None = None,
    min_conf_add: float = 0.0,
    min_rr_add: float = 0.0,
    crypto_rr_add: float = 0.0,
    tp_scale: float = 1.0,
    sl_scale: float = 1.0,
    conf_shift_add: float = 0.0,
    confluence_score_add: float = 0.0,
    confluence_factors_add: int = 0,
) -> None:
    for setup, side, vol_bucket, row in _iter_profile_rows(cfg):
        if setups is not None and setup not in setups:
            continue
        if sides is not None and side not in sides:
            continue
        if vol_buckets is not None and vol_bucket not in vol_buckets:
            continue

        if "min_confidence" in row:
            row["min_confidence"] = max(0.30, min(0.98, float(row["min_confidence"]) + min_conf_add))
        if "min_rr" in row:
            row["min_rr"] = max(0.8, min(6.0, float(row["min_rr"]) + min_rr_add))
        if "crypto_min_rr" in row:
            row["crypto_min_rr"] = max(0.8, min(6.0, float(row["crypto_min_rr"]) + crypto_rr_add))
        if "tp_mult" in row:
            row["tp_mult"] = max(0.5, min(3.0, float(row["tp_mult"]) * tp_scale))
        if "sl_mult" in row:
            row["sl_mult"] = max(0.5, min(2.5, float(row["sl_mult"]) * sl_scale))

        conf_shift = float(row.get("confidence_shift", 0.0))
        row["confidence_shift"] = max(-0.25, min(0.25, conf_shift + conf_shift_add))

        if "confluence_min_score" in row:
            row["confluence_min_score"] = max(
                0.20,
                min(0.95, float(row["confluence_min_score"]) + confluence_score_add),
            )
        if "confluence_min_factors" in row:
            row["confluence_min_factors"] = max(
                1,
                min(8, int(row["confluence_min_factors"]) + int(confluence_factors_add)),
            )


def _build_variants(base_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base_enabled = _deepcopy_json(base_cfg)
    base_enabled["enabled"] = True

    variants: dict[str, dict[str, Any]] = {
        "baseline_no_profiles": {**_deepcopy_json(base_cfg), "enabled": False},
        "matrix_default": _deepcopy_json(base_enabled),
    }

    trend_long_bias = _deepcopy_json(base_enabled)
    _tweak_rows(
        trend_long_bias,
        setups={"trend"},
        sides={"long"},
        min_conf_add=0.02,
        min_rr_add=0.15,
        crypto_rr_add=0.15,
        tp_scale=1.12,
        sl_scale=0.95,
        conf_shift_add=0.02,
    )
    _tweak_rows(
        trend_long_bias,
        setups={"trend"},
        sides={"short"},
        min_conf_add=0.01,
        min_rr_add=0.10,
        crypto_rr_add=0.10,
        tp_scale=1.05,
        sl_scale=1.02,
        conf_shift_add=0.01,
    )
    variants["trend_long_bias"] = trend_long_bias

    short_pressure = _deepcopy_json(base_enabled)
    _tweak_rows(
        short_pressure,
        sides={"short"},
        min_conf_add=0.02,
        min_rr_add=0.20,
        crypto_rr_add=0.20,
        tp_scale=1.08,
        sl_scale=1.03,
        conf_shift_add=0.015,
    )
    _tweak_rows(
        short_pressure,
        setups={"trend", "pump"},
        sides={"short"},
        vol_buckets={"high_vol"},
        min_conf_add=0.03,
        min_rr_add=0.25,
        crypto_rr_add=0.25,
        confluence_score_add=0.03,
        confluence_factors_add=1,
    )
    variants["short_pressure"] = short_pressure

    mr_defensive = _deepcopy_json(base_enabled)
    _tweak_rows(
        mr_defensive,
        setups={"mr"},
        vol_buckets={"high_vol"},
        min_conf_add=0.04,
        min_rr_add=0.30,
        crypto_rr_add=0.30,
        tp_scale=1.04,
        sl_scale=1.10,
        confluence_score_add=0.04,
        confluence_factors_add=1,
    )
    _tweak_rows(
        mr_defensive,
        setups={"mr"},
        vol_buckets={"low_vol"},
        tp_scale=1.06,
        sl_scale=0.96,
        conf_shift_add=0.01,
    )
    variants["mr_defensive"] = mr_defensive

    pump_strict = _deepcopy_json(base_enabled)
    _tweak_rows(
        pump_strict,
        setups={"pump"},
        min_conf_add=0.05,
        min_rr_add=0.40,
        crypto_rr_add=0.40,
        tp_scale=1.10,
        sl_scale=1.08,
        confluence_score_add=0.05,
        confluence_factors_add=1,
    )
    variants["pump_strict"] = pump_strict

    vol_adaptive = _deepcopy_json(base_enabled)
    _tweak_rows(
        vol_adaptive,
        vol_buckets={"high_vol"},
        min_conf_add=0.03,
        min_rr_add=0.25,
        crypto_rr_add=0.25,
        tp_scale=1.06,
        sl_scale=1.10,
        confluence_score_add=0.03,
    )
    _tweak_rows(
        vol_adaptive,
        vol_buckets={"low_vol"},
        min_conf_add=-0.01,
        min_rr_add=-0.05,
        crypto_rr_add=-0.05,
        tp_scale=1.06,
        sl_scale=0.95,
    )
    variants["vol_adaptive"] = vol_adaptive

    return variants


def _write_variant_config(path: Path, profile_cfg: dict[str, Any]) -> None:
    payload = {"strategy_profiles": profile_cfg}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _compute_metrics(db_path: Path) -> dict[str, float | int]:
    if not db_path.exists():
        return {
            "trades": 0,
            "win_rate": 0.0,
            "total_return": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "long_return": 0.0,
            "short_return": 0.0,
        }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT side, net_pnl_pct
            FROM trades
            WHERE exit_time IS NOT NULL
            ORDER BY entry_time
            """,
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()

    returns: list[float] = []
    long_returns: list[float] = []
    short_returns: list[float] = []
    for row in rows:
        pnl = float(row["net_pnl_pct"] or 0.0)
        returns.append(pnl)
        side = str(row["side"] or "").lower()
        if side == "long":
            long_returns.append(pnl)
        elif side == "short":
            short_returns.append(pnl)

    trades = len(returns)
    wins = sum(1 for x in returns if x > 0.0)
    gross_profit = sum(x for x in returns if x > 0.0)
    gross_loss_abs = abs(sum(x for x in returns if x < 0.0))
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0.0 else (float("inf") if gross_profit > 0 else 0.0)

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for r in returns:
        equity += r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_drawdown:
            max_drawdown = dd

    return {
        "trades": trades,
        "win_rate": (wins / trades) if trades else 0.0,
        "total_return": sum(returns),
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "long_trades": len(long_returns),
        "short_trades": len(short_returns),
        "long_return": sum(long_returns),
        "short_return": sum(short_returns),
    }


def _score_metrics(metrics: dict[str, float | int]) -> float:
    trades = float(metrics["trades"])
    win_rate_pct = float(metrics["win_rate"]) * 100.0
    total_return = float(metrics["total_return"])
    pf = float(metrics["profit_factor"])
    max_dd = float(metrics["max_drawdown"])
    if trades <= 0:
        return -1_000_000.0
    pf_term = 5.0 if np.isinf(pf) else (pf - 1.0) * 8.0
    trade_term = min(trades, 300.0) * 0.03
    wr_term = (win_rate_pct - 50.0) * 0.4
    dd_penalty = max_dd * 1.6
    return total_return + pf_term + trade_term + wr_term - dd_penalty


def _run_variant(
    *,
    name: str,
    cfg_path: Path,
    cfg_enabled: bool,
    args: argparse.Namespace,
    run_root: Path,
    symbols: list[str],
) -> VariantResult:
    run_dir = run_root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "v25.db"

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
        "--timeframe",
        str(args.timeframe),
        "--replay-start",
        str(args.replay_start),
        "--replay-end",
        str(args.replay_end),
        "--cycle-step-minutes",
        str(int(args.cycle_step_minutes)),
        "--hold-minutes",
        str(int(args.hold_minutes)),
        "--risk-profile",
        str(args.risk_profile),
        "--run-dir",
        str(run_dir),
        "--synthetic-exit",
        "--strategy-profiles-config",
        str(cfg_path),
    ]
    if cfg_enabled:
        cmd.append("--enable-strategy-profiles")
    if bool(args.backtest_sonar):
        cmd.append("--backtest-sonar")
    if symbols:
        cmd.extend(["--symbols", ",".join(symbols)])

    log_path = run_dir / "main.log"
    with log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=f,
            stderr=subprocess.STDOUT,
            timeout=max(300, int(args.main_timeout_seconds)),
            check=False,
        )

    metrics = _compute_metrics(db_path)
    score = _score_metrics(metrics)
    return VariantResult(
        name=name,
        run_dir=run_dir,
        config_path=cfg_path,
        enabled=cfg_enabled,
        return_code=int(proc.returncode),
        trades=int(metrics["trades"]),
        win_rate=float(metrics["win_rate"]),
        total_return=float(metrics["total_return"]),
        profit_factor=float(metrics["profit_factor"]),
        max_drawdown=float(metrics["max_drawdown"]),
        long_trades=int(metrics["long_trades"]),
        short_trades=int(metrics["short_trades"]),
        long_return=float(metrics["long_return"]),
        short_return=float(metrics["short_return"]),
        score=float(score),
    )


def _write_campaign_reports(*, results: list[VariantResult], run_root: Path) -> None:
    leaderboard_path = run_root / "leaderboard.csv"
    with leaderboard_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "variant",
                "enabled",
                "return_code",
                "trades",
                "win_rate",
                "total_return",
                "profit_factor",
                "max_drawdown",
                "long_trades",
                "short_trades",
                "long_return",
                "short_return",
                "score",
                "run_dir",
                "config_path",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.name,
                    int(r.enabled),
                    r.return_code,
                    r.trades,
                    round(r.win_rate, 6),
                    round(r.total_return, 6),
                    round(r.profit_factor, 6),
                    round(r.max_drawdown, 6),
                    r.long_trades,
                    r.short_trades,
                    round(r.long_return, 6),
                    round(r.short_return, 6),
                    round(r.score, 6),
                    str(r.run_dir),
                    str(r.config_path),
                ]
            )

    summary_path = run_root / "summary.md"
    if not results:
        summary_path.write_text("# Profile Backtest Lab\n\nNo results.\n", encoding="utf-8")
        return

    best = results[0]
    lines = [
        "# Profile Backtest Lab",
        "",
        f"- best_variant: `{best.name}`",
        f"- score: `{best.score:.4f}`",
        f"- trades: `{best.trades}`",
        f"- win_rate: `{best.win_rate * 100.0:.2f}%`",
        f"- total_return: `{best.total_return:.4f}`",
        f"- profit_factor: `{best.profit_factor:.4f}`",
        f"- max_drawdown: `{best.max_drawdown:.4f}`",
        f"- config: `{best.config_path}`",
        "",
        "## Top 5",
        "",
        "| variant | trades | win_rate | total_return | profit_factor | max_drawdown | score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results[:5]:
        lines.append(
            f"| {r.name} | {r.trades} | {r.win_rate * 100.0:.2f}% | "
            f"{r.total_return:.4f} | {r.profit_factor:.4f} | {r.max_drawdown:.4f} | {r.score:.4f} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best_cfg_output = run_root / "best_strategy_profiles.yaml"
    best_cfg_output.write_text(best.config_path.read_text(encoding="utf-8"), encoding="utf-8")


def _inject_synthetic_listing(
    *,
    cache_root: Path,
    interval: str,
    source_symbol: str,
    target_symbol: str,
    listing_time: datetime,
    replay_end: datetime,
    price_scale: float,
    volume_mult: float,
) -> dict[str, Any]:
    loader = ReplayLoader(root=cache_root)
    store = LocalStore(root=cache_root)
    source = loader.load_ohlcv(
        symbol=source_symbol,
        interval=interval,
        start=None,
        end=None,
        verify=False,
    )
    if source.empty:
        raise ValueError(f"source symbol has no data: {source_symbol}/{interval}")

    ts = pd.to_datetime(source["timestamp"], utc=True, errors="coerce")
    source = source.assign(timestamp=ts).dropna(subset=["timestamp"])
    clipped = source[
        (source["timestamp"] >= pd.Timestamp(listing_time))
        & (source["timestamp"] <= pd.Timestamp(replay_end))
    ].copy()
    if clipped.empty:
        raise ValueError(
            f"no source candles after listing time {listing_time.isoformat()} for {source_symbol}/{interval}"
        )

    rng = np.random.default_rng(42)
    noise = rng.normal(loc=0.0, scale=0.004, size=len(clipped))

    open_px = clipped["open"].astype(float).to_numpy() * price_scale * (1.0 + noise)
    close_px = clipped["close"].astype(float).to_numpy() * price_scale * (1.0 + noise)
    high_src = clipped["high"].astype(float).to_numpy() * price_scale * (1.0 + np.abs(noise))
    low_src = clipped["low"].astype(float).to_numpy() * price_scale * (1.0 - np.abs(noise))

    high_px = np.maximum.reduce([open_px, close_px, high_src])
    low_px = np.minimum.reduce([open_px, close_px, low_src])
    volume = clipped["volume"].astype(float).to_numpy() * max(0.1, float(volume_mult)) * (1.0 + np.abs(noise) * 4.0)

    synth = pd.DataFrame(
        {
            "timestamp": clipped["timestamp"].to_numpy(),
            "open": open_px,
            "high": high_px,
            "low": low_px,
            "close": close_px,
            "volume": volume,
        }
    )

    store.save(df=synth, symbol=target_symbol, interval=interval)
    return {
        "symbol": target_symbol,
        "rows_written": int(len(synth)),
        "first_ts": str(synth["timestamp"].iloc[0]),
        "last_ts": str(synth["timestamp"].iloc[-1]),
        "interval": interval,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    replay_start = _parse_utc_datetime(str(args.replay_start))
    replay_end = _parse_utc_datetime(str(args.replay_end))
    if replay_end < replay_start:
        raise SystemExit("--replay-end must be >= --replay-start")

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_root = Path(args.run_root) / f"campaign_{run_stamp}"
    run_root.mkdir(parents=True, exist_ok=True)

    print(f"[lab] run_root={run_root}")
    print(f"[lab] window={replay_start.isoformat()} -> {replay_end.isoformat()}")

    symbols = _parse_symbols(args.symbols)
    if symbols:
        print(f"[lab] fixed symbols={','.join(symbols)}")
    elif bool(args.backtest_sonar):
        print("[lab] symbols=dynamic (SONAR driven)")
    else:
        print("[lab] symbols=default from config (no explicit override)")

    if bool(args.inject_synthetic_listing):
        listing_time = (
            _parse_utc_datetime(str(args.synthetic_listing_time))
            if args.synthetic_listing_time
            else replay_start + timedelta(days=2)
        )
        sim_info = _inject_synthetic_listing(
            cache_root=Path(args.cache_root),
            interval=str(args.timeframe),
            source_symbol=str(args.synthetic_source).upper(),
            target_symbol=str(args.synthetic_symbol).upper(),
            listing_time=listing_time,
            replay_end=replay_end,
            price_scale=float(args.synthetic_price_scale),
            volume_mult=float(args.synthetic_volume_mult),
        )
        print(
            "[lab] synthetic listing prepared "
            f"symbol={sim_info['symbol']} rows={sim_info['rows_written']} "
            f"first={sim_info['first_ts']} last={sim_info['last_ts']}"
        )

    profile_cfg_path = Path(str(args.profile_config))
    profile_node = _load_strategy_profile_node(profile_cfg_path)
    variants = _build_variants(profile_node)

    cfg_dir = run_root / "configs"
    results: list[VariantResult] = []
    ordered_names = sorted(variants.keys())
    for idx, name in enumerate(ordered_names, start=1):
        cfg = variants[name]
        cfg_path = cfg_dir / f"{name}.yaml"
        _write_variant_config(cfg_path, cfg)
        enabled = bool(cfg.get("enabled", False))
        print(f"[lab] ({idx}/{len(ordered_names)}) running={name} enabled={enabled}")
        result = _run_variant(
            name=name,
            cfg_path=cfg_path,
            cfg_enabled=enabled,
            args=args,
            run_root=run_root,
            symbols=symbols,
        )
        results.append(result)
        print(
            f"[lab] done={name} rc={result.return_code} trades={result.trades} "
            f"ret={result.total_return:.4f} score={result.score:.4f}"
        )

    results.sort(key=lambda r: r.score, reverse=True)
    _write_campaign_reports(results=results, run_root=run_root)

    if results:
        best = results[0]
        print(
            f"[lab] best={best.name} score={best.score:.4f} trades={best.trades} "
            f"ret={best.total_return:.4f} wr={best.win_rate * 100.0:.2f}%"
        )
    print(f"[lab] leaderboard={run_root / 'leaderboard.csv'}")
    print(f"[lab] summary={run_root / 'summary.md'}")
    print(f"[lab] best_profiles={run_root / 'best_strategy_profiles.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

