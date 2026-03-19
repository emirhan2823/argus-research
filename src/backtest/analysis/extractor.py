"""Extract and enrich trades from backtest DB files.

Matches trades ↔ decisions, parses gate_results_json into flat columns,
and adds match quality guardrails.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Match quality thresholds (user kritik ayar #1 & #2)
# ---------------------------------------------------------------------------
# "exact" = fixed small window (truly exact)
# "close" / "stale" scale with bar_seconds
EXACT_THRESHOLD_SECONDS = 10  # fixed — real exact match

# Feature columns to flatten from gate_results_json → features_snapshot
_FEATURE_NAMES = [
    "atr_14_pct", "atr_ratio_5_20", "bb_width", "realized_vol_20d",
    "adx_14", "price_vs_ma200", "ema_21_vs_55", "lr_slope_20", "aroon_osc",
    "rsi_14", "bb_pct_b", "roc_10", "willr_14", "cci_20",
    "volume_ratio", "obv_slope_10", "vwap_dev_pct", "cmf_20", "volume_delta",
    "hurst_exponent", "entropy_50",
]

# Filter score columns to flatten from gate_results_json
_FILTER_NAMES = [
    "sq_score", "sq_adjusted_conf",
    "precision_score", "precision_grade",
    "regime_align_score",
    "confluence_score", "confluence_factors",
    "tq_composite", "tq_grade",
    "dir_bias",
]

# Confluence detail columns
_CONFLUENCE_NAMES = [
    "momentum", "mtf", "orderbook", "statistical", "volatility", "volume",
]

# Timeframe → bar seconds mapping
_TF_TO_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
    "1d": 86400,
}


def timeframe_to_seconds(tf: str) -> int:
    """Convert timeframe string to seconds."""
    return _TF_TO_SECONDS.get(tf, 3600)


def classify_match_quality(
    dt_seconds: float | None,
    bar_seconds: int = 3600,
    is_future: bool = False,
) -> str:
    """Classify match quality given time delta.

    Thresholds (user kritik ayar #1):
    - exact: < EXACT_THRESHOLD_SECONDS (fixed 10s)
    - close: < 0.5 × bar_seconds
    - stale: >= 0.5 × bar_seconds but < 2 × bar_seconds
    - unmatched: no match found (dt_seconds is None)
    - future: decision_ts > entry_time (kritik ayar #2)
    """
    if dt_seconds is None:
        return "unmatched"
    if is_future:
        return "future"
    abs_dt = abs(dt_seconds)
    if abs_dt < EXACT_THRESHOLD_SECONDS:
        return "exact"
    if abs_dt < 0.5 * bar_seconds:
        return "close"
    if abs_dt < 2.0 * bar_seconds:
        return "stale"
    return "stale"


def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_json_safe(s: str | None) -> dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# DB loading
# ---------------------------------------------------------------------------

def _load_closed_trades(db_path: Path) -> list[dict[str, Any]]:
    """Load closed trades from a DB file."""
    if not db_path.exists():
        return []
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT trade_id, symbol, side, engine,
                       entry_time, exit_time, entry_price, exit_price,
                       hold_minutes, pnl_pct, net_pnl_pct, confidence,
                       regime_at_entry, regime_at_exit, stop_distance,
                       size, COALESCE(leverage, 1.0) AS leverage,
                       reason_entry, reason_exit,
                       sqs_score, sub_strategy
                FROM trades
                WHERE exit_time IS NOT NULL
                ORDER BY entry_time ASC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            # Try backtest_trades table
            try:
                rows = conn.execute(
                    """
                    SELECT trade_id, symbol, side, engine,
                           entry_time, exit_time, entry_price, exit_price,
                           hold_minutes, pnl_pct, net_pnl_pct, confidence,
                           regime_at_entry, regime_at_exit, stop_distance,
                           size, COALESCE(leverage, 1.0) AS leverage,
                           reason_entry, reason_exit,
                           sqs_score, sub_strategy
                    FROM backtest_trades
                    WHERE exit_time IS NOT NULL
                    ORDER BY entry_time ASC
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                return []
    return [dict(row) for row in rows]


def _load_decisions(db_path: Path) -> list[dict[str, Any]]:
    """Load decisions from a DB file."""
    if not db_path.exists():
        return []
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT decision_id, timestamp, symbol, action, engine, reason,
                       status, confidence, gate_results_json
                FROM decisions
                ORDER BY decision_id ASC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _build_decision_lookup(decisions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group decisions by symbol with parsed timestamps, sorted by time."""
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in decisions:
        symbol = str(row.get("symbol", "UNKNOWN"))
        dt = _parse_iso_utc(str(row.get("timestamp")))
        if dt is None:
            continue
        row["_dt"] = dt
        by_symbol.setdefault(symbol, []).append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda r: r["_dt"])
    return by_symbol


def _find_nearest_decision(
    symbol_rows: list[dict[str, Any]],
    at: datetime,
) -> tuple[dict[str, Any] | None, float | None, bool]:
    """Find nearest decision with dt <= at (kritik ayar #2).

    Returns (decision, dt_seconds, is_future).
    Prefers decisions BEFORE the trade entry time.
    Falls back to future match only if no past match exists.
    """
    if not symbol_rows:
        return None, None, False

    # Find best past match (decision_ts <= entry_time)
    past_best: dict[str, Any] | None = None
    for row in symbol_rows:
        row_dt = row.get("_dt")
        if isinstance(row_dt, datetime) and row_dt <= at:
            past_best = row
        elif isinstance(row_dt, datetime) and row_dt > at:
            break

    if past_best is not None:
        dt_seconds = (at - past_best["_dt"]).total_seconds()
        return past_best, dt_seconds, False

    # No past match — try future match (kritik ayar #2: label as "future")
    future_best: dict[str, Any] | None = None
    for row in symbol_rows:
        row_dt = row.get("_dt")
        if isinstance(row_dt, datetime) and row_dt > at:
            future_best = row
            break

    if future_best is not None:
        dt_seconds = (future_best["_dt"] - at).total_seconds()
        return future_best, dt_seconds, True

    return None, None, False


# ---------------------------------------------------------------------------
# Feature flattening
# ---------------------------------------------------------------------------

def _flatten_gate_results(gate: dict[str, Any]) -> dict[str, Any]:
    """Flatten gate_results_json into prefixed columns."""
    flat: dict[str, Any] = {}

    # Features snapshot
    snap = gate.get("features_snapshot", {})
    snap_version = snap.get("_version", 1)
    flat["snap_version"] = snap_version
    flat["feat_regime"] = snap.get("regime")
    for name in _FEATURE_NAMES:
        val = snap.get(name)
        flat[f"feat_{name}"] = float(val) if val is not None else np.nan

    # Filter scores
    for name in _FILTER_NAMES:
        val = gate.get(name)
        if val is not None:
            flat[f"filt_{name}"] = val
        else:
            flat[f"filt_{name}"] = np.nan

    # Confluence details
    conf_detail = gate.get("confluence_detail", {})
    for name in _CONFLUENCE_NAMES:
        val = conf_detail.get(name)
        flat[f"conf_{name}"] = float(val) if val is not None else np.nan

    return flat


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_enriched_trades(
    db_paths: list[Path],
    bar_seconds: int = 3600,
) -> pd.DataFrame:
    """Extract and enrich trades from one or more backtest DB files.

    Parameters
    ----------
    db_paths : list of DB file paths
    bar_seconds : timeframe in seconds for match quality thresholds

    Returns
    -------
    pd.DataFrame with ~45 columns including match quality, features, filters.
    """
    all_rows: list[dict[str, Any]] = []

    for db_path in db_paths:
        trades = _load_closed_trades(db_path)
        decisions = _load_decisions(db_path)
        decision_lookup = _build_decision_lookup(decisions)

        logger.info(
            "DB %s: %d closed trades, %d decisions",
            db_path.name, len(trades), len(decisions),
        )

        for trade in trades:
            row: dict[str, Any] = {
                "db_source": str(db_path.name),
                "trade_id": trade.get("trade_id"),
                "symbol": trade.get("symbol"),
                "side": trade.get("side"),
                "engine": trade.get("engine"),
                "sub_strategy": trade.get("sub_strategy"),
                "entry_time": _parse_iso_utc(str(trade.get("entry_time"))),
                "exit_time": _parse_iso_utc(str(trade.get("exit_time"))),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "pnl_pct": trade.get("pnl_pct"),
                "net_pnl_pct": trade.get("net_pnl_pct"),
                "is_winner": (trade.get("net_pnl_pct") or 0) > 0,
                "confidence": trade.get("confidence"),
                "leverage": trade.get("leverage", 1.0),
                "stop_distance": trade.get("stop_distance"),
                "hold_minutes": trade.get("hold_minutes"),
                "reason_entry": trade.get("reason_entry"),
                "reason_exit": trade.get("reason_exit"),
                "sqs_score": trade.get("sqs_score"),
                "regime_at_entry": trade.get("regime_at_entry"),
                "regime_at_exit": trade.get("regime_at_exit"),
                "size": trade.get("size"),
            }

            # Match trade ↔ decision
            entry_dt = row["entry_time"]
            symbol = row["symbol"]
            symbol_decisions = decision_lookup.get(symbol, [])

            gate_flat: dict[str, Any] = {}
            if entry_dt and symbol_decisions:
                decision, dt_seconds, is_future = _find_nearest_decision(
                    symbol_decisions, entry_dt,
                )
                row["match_dt_seconds"] = dt_seconds
                row["match_quality"] = classify_match_quality(
                    dt_seconds, bar_seconds=bar_seconds, is_future=is_future,
                )

                # Only use gate_results for exact/close matches
                if decision and row["match_quality"] in ("exact", "close"):
                    gate_json = _parse_json_safe(decision.get("gate_results_json"))
                    gate_flat = _flatten_gate_results(gate_json)
                # Stale/future/unmatched → NaN gate features
            else:
                row["match_dt_seconds"] = None
                row["match_quality"] = "unmatched"

            row.update(gate_flat)
            all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Ensure feature columns exist even if no gate data matched
    for name in _FEATURE_NAMES:
        col = f"feat_{name}"
        if col not in df.columns:
            df[col] = np.nan
    for name in _FILTER_NAMES:
        col = f"filt_{name}"
        if col not in df.columns:
            df[col] = np.nan
    for name in _CONFLUENCE_NAMES:
        col = f"conf_{name}"
        if col not in df.columns:
            df[col] = np.nan
    if "snap_version" not in df.columns:
        df["snap_version"] = np.nan

    # PnL sanity checks (kritik ayar #3: warn + hard cap)
    _pnl_sanity_check(df)

    return df


def _pnl_sanity_check(df: pd.DataFrame) -> None:
    """Validate PnL scale, filter non-finite values, and log distribution stats."""
    if df.empty or "net_pnl_pct" not in df.columns:
        return

    # Filter non-finite PnL values (NaN, inf, -inf)
    non_finite_mask = ~np.isfinite(df["net_pnl_pct"])
    n_non_finite = int(non_finite_mask.sum())
    if n_non_finite > 0:
        logger.warning(
            "Dropping %d trades with non-finite net_pnl_pct (NaN/inf)",
            n_non_finite,
        )
        df.drop(df.index[non_finite_mask], inplace=True)

    pnl_abs = df["net_pnl_pct"].dropna().abs()
    if pnl_abs.empty:
        return

    max_pnl = float(pnl_abs.max())
    p99 = float(pnl_abs.quantile(0.99))
    p999 = float(pnl_abs.quantile(0.999))

    logger.info(
        "PnL distribution: max=%.4f, p99=%.4f, p999=%.4f",
        max_pnl, p99, p999,
    )

    # Soft outlier warning (> 3x IQR beyond p75)
    if len(pnl_abs) > 10:
        q75 = float(pnl_abs.quantile(0.75))
        iqr = float(pnl_abs.quantile(0.75) - pnl_abs.quantile(0.25))
        outlier_threshold = q75 + 3 * iqr
        n_outliers = int((pnl_abs > outlier_threshold).sum())
        if n_outliers > 0:
            logger.warning(
                "PnL outliers: %d trades exceed %.4f (3x IQR threshold)",
                n_outliers, outlier_threshold,
            )

    if max_pnl >= 5.0:
        raise ValueError(
            f"PnL > 500% detected (max={max_pnl:.4f}) — scale error? "
            f"Expected fraction (0.01 = 1%)"
        )

    if "stop_distance" in df.columns:
        sd_max = df["stop_distance"].dropna().max()
        if sd_max is not None and float(sd_max) >= 1.0:
            raise ValueError(
                f"Stop distance >= 100% detected (max={sd_max:.4f}) — "
                f"fraction expected"
            )

    # Unknown exit_reason check
    if "reason_exit" in df.columns:
        known_reasons = {
            "stop_loss_hit", "breakeven_stop_hit", "trailing_stop_hit",
            "time_stop_hit", "time_exit_backtest_sim", "sl", "tp",
            "trailing", "be_stop", "time_stop",
        }
        unique_reasons = set(df["reason_exit"].dropna().unique())
        unknown = unique_reasons - known_reasons
        if unknown:
            logger.warning("Unknown exit_reason values: %s", unknown)


def get_match_quality_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Compute match quality distribution for reporting."""
    if df.empty or "match_quality" not in df.columns:
        return {"total": 0}

    total = len(df)
    counts = df["match_quality"].value_counts().to_dict()
    pnl_abs = df["net_pnl_pct"].dropna().abs()

    summary: dict[str, Any] = {
        "total": total,
        "exact": counts.get("exact", 0),
        "close": counts.get("close", 0),
        "stale": counts.get("stale", 0),
        "future": counts.get("future", 0),
        "unmatched": counts.get("unmatched", 0),
        "pnl_p99": float(pnl_abs.quantile(0.99)) if not pnl_abs.empty else 0.0,
        "pnl_p999": float(pnl_abs.quantile(0.999)) if not pnl_abs.empty else 0.0,
        "pnl_max": float(pnl_abs.max()) if not pnl_abs.empty else 0.0,
    }

    # Regime distribution
    if "regime_at_entry" in df.columns:
        regime_counts = df["regime_at_entry"].value_counts().to_dict()
        summary["regime_distribution"] = regime_counts

    # Exit reason distribution
    if "reason_exit" in df.columns:
        exit_counts = df["reason_exit"].value_counts().to_dict()
        summary["exit_reason_distribution"] = exit_counts

    return summary
