"""Append-only telemetry writers for v2.5 tables."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_decision(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    symbol: str,
    action: str,
    capital_engine: str,
    regime: str,
    reason: str,
    timestamp: str | None = None,
    position_size_pct: float | None = None,
    leverage: float | None = None,
    stop_loss_pct: float | None = None,
    confidence: float | None = None,
    sqs_score: float | None = None,
    engine: str | None = None,
    sub_strategy: str | None = None,
    status: str | None = None,
    gate_results: dict[str, Any] | None = None,
    inputs_hash: str | None = None,
) -> int | None:
    """Insert one decision row. Never mutates existing rows."""

    cur = conn.execute(
        """
        INSERT INTO decisions (
          run_id, timestamp, symbol, action, capital_engine, position_size_pct,
          leverage, stop_loss_pct, confidence, sqs_score, engine, sub_strategy,
          regime, reason, status, gate_results_json, inputs_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            timestamp or _now_iso(),
            symbol,
            action,
            capital_engine,
            position_size_pct,
            leverage,
            stop_loss_pct,
            confidence,
            sqs_score,
            engine,
            sub_strategy,
            regime,
            reason,
            status,
            json.dumps(gate_results or {}, ensure_ascii=True),
            inputs_hash,
        ),
    )
    try:
        if cur.lastrowid is None:
            return None
        rid = int(cur.lastrowid)
        return rid if rid > 0 else None
    except Exception:
        return None


def log_sqs(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    total_score: float,
    regime_consistency: float,
    trend_structure: float,
    microstructure: float,
    fee_adj_expectancy: float,
    hermes_news_risk: float,
    threshold_used: float,
    passed: bool,
    reason_if_failed: str | None = None,
    timestamp: str | None = None,
) -> None:
    """Insert one sqs_log row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO sqs_log (
          timestamp, symbol, total_score, regime_consistency, trend_structure,
          microstructure, fee_adj_expectancy, hermes_news_risk, threshold_used,
          passed, reason_if_failed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp or _now_iso(),
            symbol,
            total_score,
            regime_consistency,
            trend_structure,
            microstructure,
            fee_adj_expectancy,
            hermes_news_risk,
            threshold_used,
            1 if passed else 0,
            reason_if_failed,
        ),
    )


def log_ledger_event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    event_type: str,
    symbol: str,
    capital_engine: str,
    amount: float,
    balance_after: float,
    equity_after: float,
    position_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> None:
    """Insert one ledger row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO ledger (
          event_id, event_type, symbol, capital_engine, amount,
          balance_after, equity_after, position_id, metadata_json, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            symbol,
            capital_engine,
            amount,
            balance_after,
            equity_after,
            position_id,
            json.dumps(metadata or {}, ensure_ascii=True),
            timestamp or _now_iso(),
        ),
    )


def log_dynamic_exit(
    conn: sqlite3.Connection,
    *,
    position_id: str,
    symbol: str,
    stage: str,
    current_r: float,
    pct_closed: float,
    partial_pnl_locked: float,
    regime: str,
    trigger_reason: str,
    trade_id: str | None = None,
    trailing_sl: float | None = None,
    trailing_atr_mult: float | None = None,
    timestamp: str | None = None,
) -> None:
    """Insert one dynamic_exit_log row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO dynamic_exit_log (
          timestamp, position_id, trade_id, symbol, stage, current_r,
          pct_closed, partial_pnl_locked, trailing_sl, trailing_atr_mult,
          regime, trigger_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp or _now_iso(),
            position_id,
            trade_id,
            symbol,
            stage,
            current_r,
            pct_closed,
            partial_pnl_locked,
            trailing_sl,
            trailing_atr_mult,
            regime,
            trigger_reason,
        ),
    )


def log_validated_sizing(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    equity: float,
    risk_pct: float,
    risk_usd: float,
    entry_price: float,
    sl_price: float,
    sl_pct: float,
    notional_usd: float,
    quantity: float,
    leverage_derived: float,
    breakeven_r: float,
    fee_reserved: float,
    net_risk_usd: float,
    passed_breakeven_gate: bool,
    leverage_capped: bool = False,
    timestamp: str | None = None,
) -> None:
    """Insert one validated_sizing_log row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO validated_sizing_log (
          timestamp, symbol, equity, risk_pct, risk_usd, entry_price,
          sl_price, sl_pct, notional_usd, quantity, leverage_derived,
          leverage_capped, breakeven_r, fee_reserved, net_risk_usd,
          passed_breakeven_gate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp or _now_iso(),
            symbol,
            equity,
            risk_pct,
            risk_usd,
            entry_price,
            sl_price,
            sl_pct,
            notional_usd,
            quantity,
            leverage_derived,
            1 if leverage_capped else 0,
            breakeven_r,
            fee_reserved,
            net_risk_usd,
            1 if passed_breakeven_gate else 0,
        ),
    )


def log_whale_momentum(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    net_flow_usd_24h: float,
    exchange_reserve_change_pct: float,
    is_bullish_flow: bool,
    is_bearish_flow: bool,
    momentum_score: float,
    sqs_boost: float,
    size_modifier: float,
    stablecoin_mint_usd_24h: float = 0.0,
    timestamp: str | None = None,
) -> None:
    """Insert one whale_momentum_log row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO whale_momentum_log (
          timestamp, symbol, net_flow_usd_24h, exchange_reserve_change_pct,
          stablecoin_mint_usd_24h, is_bullish_flow, is_bearish_flow,
          momentum_score, sqs_boost, size_modifier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp or _now_iso(),
            symbol,
            net_flow_usd_24h,
            exchange_reserve_change_pct,
            stablecoin_mint_usd_24h,
            1 if is_bullish_flow else 0,
            1 if is_bearish_flow else 0,
            momentum_score,
            sqs_boost,
            size_modifier,
        ),
    )


def log_correlation(
    conn: sqlite3.Connection,
    *,
    pair_id: str,
    symbol_a: str,
    symbol_b: str,
    correlation: float,
    spread_zscore: float,
    half_life_bars: float | None = None,
    is_cointegrated: bool = False,
    regime: str = "STABLE",
    timestamp: str | None = None,
) -> None:
    """Insert one correlation_logs row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO correlation_logs (
          timestamp, pair_id, symbol_a, symbol_b, correlation,
          spread_zscore, half_life_bars, is_cointegrated, regime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp or _now_iso(),
            pair_id,
            symbol_a,
            symbol_b,
            correlation,
            spread_zscore,
            half_life_bars,
            1 if is_cointegrated else 0,
            regime,
        ),
    )


def log_precision_entry(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    direction: str,
    order_type: str,
    precision_price: float | None = None,
    obi: float | None = None,
    spread_pct: float,
    vwap_dev_pct: float,
    timeout_bars: int,
    reason: str,
    timestamp: str | None = None,
) -> None:
    """Insert one precision_entries row. Never mutates existing rows."""

    conn.execute(
        """
        INSERT INTO precision_entries (
          timestamp, symbol, direction, order_type, precision_price,
          obi, spread_pct, vwap_dev_pct, timeout_bars, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp or _now_iso(),
            symbol,
            direction,
            order_type,
            precision_price,
            obi,
            spread_pct,
            vwap_dev_pct,
            timeout_bars,
            reason,
        ),
    )
