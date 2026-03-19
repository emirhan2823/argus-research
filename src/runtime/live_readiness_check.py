"""Stage-2C Live Readiness Check.

Evaluates whether paper trading results warrant transition to live trading.
Read-only analysis — no trading-logic side effects.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Any

from src.v25.reports.engine_observatory import (
    _as_float,
    _safe_query,
    compute_max_drawdown,
    _compute_total_return,
)


def evaluate_live_readiness(
    db_path: str,
    *,
    last_n_days: int = 7,
    min_profitable_days: int = 5,
    max_dd_pct: float = 0.12,
    min_profit_factor: float = 1.2,
    max_avg_slippage_pct: float = 0.003,
) -> dict[str, Any]:
    """Evaluate whether paper results meet live readiness criteria.

    Parameters
    ----------
    db_path : str
        Path to v2.5 SQLite database.
    last_n_days : int
        Lookback window in days (default 7).
    min_profitable_days : int
        Minimum profitable days required (default 5 out of 7).
    max_dd_pct : float
        Maximum acceptable drawdown (default 12%).
    min_profit_factor : float
        Minimum profit factor (default 1.2).
    max_avg_slippage_pct : float
        Maximum acceptable average slippage (default 0.3%).

    Returns
    -------
    dict
        {"ready": bool, "reason": str, "metrics": {...}}
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=last_n_days)).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Fetch recent closed trades
        trades = _safe_query(
            conn,
            """
            SELECT net_pnl_pct, fees_pct, slippage_pct, exit_time
            FROM trades
            WHERE exit_time IS NOT NULL AND exit_time >= ?
            ORDER BY exit_time ASC
            """,
            (cutoff,),
        )

        # Check for runtime crashes
        crash_count = 0
        try:
            state = conn.execute(
                "SELECT consecutive_errors FROM paper_runtime_state WHERE id = 1"
            ).fetchone()
            if state:
                crash_count = int(state["consecutive_errors"] or 0)
        except sqlite3.OperationalError:
            pass  # Table may not exist

    if not trades:
        return {
            "ready": False,
            "reason": f"No closed trades in last {last_n_days} days",
            "metrics": {"trade_count": 0},
        }

    # Extract returns and costs
    returns = [float(_as_float(t["net_pnl_pct"]) or 0.0) for t in trades]
    slippages = [float(_as_float(t["slippage_pct"]) or 0.0) for t in trades]

    # Group by day for profitable-day counting
    daily_returns: dict[str, float] = {}
    for t in trades:
        exit_date = str(t["exit_time"])[:10]  # YYYY-MM-DD
        daily_returns.setdefault(exit_date, 0.0)
        daily_returns[exit_date] += float(_as_float(t["net_pnl_pct"]) or 0.0)

    profitable_days = sum(1 for v in daily_returns.values() if v > 0)
    total_days = len(daily_returns)

    # Compute metrics
    total_return = _compute_total_return(returns)
    max_dd = abs(compute_max_drawdown(returns))
    wins = sum(1 for r in returns if r > 0)
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-12 else float("inf")
    avg_slippage = float(mean(slippages)) if slippages else 0.0

    metrics = {
        "trade_count": len(returns),
        "total_return": round(total_return, 8),
        "max_drawdown": round(max_dd, 8),
        "win_rate": round(wins / len(returns), 6),
        "profit_factor": round(profit_factor, 6),
        "avg_slippage_pct": round(avg_slippage, 8),
        "profitable_days": profitable_days,
        "total_days": total_days,
        "crash_count": crash_count,
    }

    # Evaluation
    reasons: list[str] = []

    if profitable_days < min_profitable_days:
        reasons.append(
            f"Insufficient profitable days: {profitable_days}/{total_days} "
            f"(need {min_profitable_days})"
        )

    if max_dd > max_dd_pct:
        reasons.append(f"Max drawdown {max_dd:.4f} exceeds threshold {max_dd_pct}")

    if profit_factor < min_profit_factor:
        reasons.append(f"Profit factor {profit_factor:.4f} below minimum {min_profit_factor}")

    if avg_slippage > max_avg_slippage_pct:
        reasons.append(f"Avg slippage {avg_slippage:.6f} exceeds band {max_avg_slippage_pct}")

    if crash_count > 0:
        reasons.append(f"Runtime crashes detected: {crash_count}")

    ready = len(reasons) == 0
    reason = "All criteria met" if ready else "; ".join(reasons)

    return {
        "ready": ready,
        "reason": reason,
        "metrics": metrics,
    }
