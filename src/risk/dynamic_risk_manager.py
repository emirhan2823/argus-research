"""Argus v2.5 — Dynamic Risk Matrix + Adaptive Leverage (backtest-safe).

This module is intentionally self-contained:
- Fully typed, deterministic, and unit-testable.
- NOT wired into live/paper execution paths by default (no behavior change).

It computes dynamic leverage, position sizing, ATR-based TP/SL, and trailing rules
from a small set of high-signal inputs (regime, confidence, volatility, drawdown).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal, Mapping


RiskMode = Literal["normal", "growth"]
Side = Literal["long", "short"]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _norm_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(symbol).strip().upper())


@dataclass(frozen=True)
class TrailingRules:
    """Trailing specification in R-multiples (1R = initial stop distance)."""

    breakeven_at_r: float = 1.0
    lock_in_at_r: float = 2.0
    lock_in_profit_r: float = 1.0


@dataclass(frozen=True)
class RiskConfig:
    """Tunable risk parameters (optimized in backtests; safe defaults provided)."""

    atr_multiplier: float = 1.5
    rr_ratio: float = 2.0
    leverage_cap: float = 5.0
    atr_multiplier_long: float | None = None
    atr_multiplier_short: float | None = None
    rr_ratio_long: float | None = None
    rr_ratio_short: float | None = None
    leverage_cap_long: float | None = None
    leverage_cap_short: float | None = None
    trailing_activation_long: float = 1.0
    trailing_activation_short: float = 1.0
    volatility_threshold: float = 0.03  # atr_pct trigger
    low_volatility_threshold: float = 0.01  # atr_pct trigger
    vol_k: float = 15.0
    drawdown_sensitivity: float = 1.0
    confidence_floor: float = 0.60


@dataclass(frozen=True)
class RiskDecision:
    leverage: float
    position_size_usd: float
    sl_price: float
    tp_price: float
    trailing_rules: TrailingRules
    risk_score: float


def _side_param(*, side: Side, long_value: float | None, short_value: float | None, fallback: float) -> float:
    if side == "long":
        if long_value is not None:
            return float(long_value)
    else:
        if short_value is not None:
            return float(short_value)
    return float(fallback)


def compute_side_aware_leverage(
    *,
    base_leverage: float,
    base_leverage_reference: float,
    score: float,
    volatility: float,
    drawdown_pct: float,
    side: Side,
    regime: str,
    leverage_cap_long: float,
    leverage_cap_short: float,
    volatility_k: float = 8.0,
    drawdown_sensitivity: float = 1.0,
    confidence_floor: float = 0.55,
) -> float:
    """Deterministic side-aware leverage function used by backtest optimizers."""

    if str(regime).upper() == "CRISIS":
        return 1.0

    score_norm = _clamp(float(score) / 100.0, max(0.0, float(confidence_floor)), 1.0)
    vol_penalty = 1.0 / (1.0 + max(0.0, float(volatility)) * float(volatility_k))
    dd_penalty = 1.0 / (
        1.0 + max(0.0, float(drawdown_pct)) * 4.0 * max(0.1, float(drawdown_sensitivity))
    )
    leverage = max(0.0, float(base_leverage)) * score_norm * vol_penalty * dd_penalty

    cap_long = max(1.0, float(leverage_cap_long))
    cap_short = max(1.0, float(leverage_cap_short))
    if side == "short":
        leverage = min(float(leverage), cap_short, float(base_leverage_reference) * 0.85)
    else:
        leverage = min(float(leverage), cap_long)
    return max(1.0, float(leverage))


def base_profile_for_asset(asset: str) -> tuple[float, float]:
    """Return (base_leverage, base_risk_pct) from the asset symbol."""

    sym = _norm_symbol(asset)
    if sym.startswith("BTC"):
        return 2.0, 0.02
    if sym.startswith("ETH"):
        return 2.0, 0.02
    if sym.startswith("SOL") or sym.startswith("XRP"):
        return 1.5, 0.015
    return 1.0, 0.01


def _weighted_regime_multiplier(
    *,
    regime: str,
    regime_probability_vector: Mapping[str, float] | None,
    multipliers: Mapping[str, float],
) -> float:
    if not regime_probability_vector:
        return float(multipliers.get(str(regime).upper(), 1.0))
    total = float(sum(float(v) for v in regime_probability_vector.values()))
    if total <= 0.0:
        return float(multipliers.get(str(regime).upper(), 1.0))
    acc = 0.0
    for key, prob in regime_probability_vector.items():
        acc += (float(prob) / total) * float(multipliers.get(str(key).upper(), 1.0))
    return float(acc)


def apply_trailing_stop(
    *,
    side: Side,
    entry_price: float,
    initial_sl_price: float,
    current_sl_price: float,
    current_price: float,
    rules: TrailingRules,
) -> float:
    """Return updated stop price based on current price and trailing rules.

    Deterministic, single-step update using current_price (no intrabar path dependence).
    """

    entry = float(entry_price)
    initial_sl = float(initial_sl_price)
    cur_sl = float(current_sl_price)
    px = float(current_price)
    r = abs(entry - initial_sl)
    if r <= 0.0:
        return cur_sl

    if side == "long":
        if px >= entry + rules.lock_in_at_r * r:
            return max(cur_sl, entry + rules.lock_in_profit_r * r)
        if px >= entry + rules.breakeven_at_r * r:
            return max(cur_sl, entry)
        return cur_sl

    if px <= entry - rules.lock_in_at_r * r:
        return min(cur_sl, entry - rules.lock_in_profit_r * r)
    if px <= entry - rules.breakeven_at_r * r:
        return min(cur_sl, entry)
    return cur_sl


def compute_risk_decision(
    *,
    asset: str,
    asset_class: str,
    regime: str,
    regime_probability_vector: Mapping[str, float] | None,
    engine_name: str,
    engine_confidence: float,
    atr_pct: float,
    adx: float,
    rolling_drawdown_pct: float,
    account_equity: float,
    risk_mode: RiskMode,
    entry_price: float,
    side: Side,
    config: RiskConfig | None = None,
) -> RiskDecision:
    """Compute a dynamic risk decision (leverage, sizing, TP/SL, trailing rules).

    Notes:
    - The returned position_size_usd is notional in USD.
    - Deterministic: no randomness, no external state.
    """

    _ = (asset_class, engine_name, adx)  # kept for forward-compat; currently unused in rules
    cfg = config or RiskConfig()

    entry = float(entry_price)
    if not math.isfinite(entry) or entry <= 0.0:
        raise ValueError("entry_price must be positive and finite")

    equity = float(account_equity)
    if not math.isfinite(equity) or equity <= 0.0:
        return RiskDecision(
            leverage=0.0,
            position_size_usd=0.0,
            sl_price=entry,
            tp_price=entry,
            trailing_rules=TrailingRules(),
            risk_score=0.0,
        )

    base_leverage, base_risk_pct = base_profile_for_asset(asset)
    leverage_base = float(base_leverage)
    risk_pct = float(base_risk_pct)

    # --- Regime multipliers (regime-aware; uses probability vector if provided) ---
    lev_mult = _weighted_regime_multiplier(
        regime=regime,
        regime_probability_vector=regime_probability_vector,
        multipliers={"TRENDING": 1.2, "RANGING": 0.8, "CRISIS": 0.5},
    )
    risk_mult = _weighted_regime_multiplier(
        regime=regime,
        regime_probability_vector=regime_probability_vector,
        multipliers={"TRENDING": 1.1, "RANGING": 0.9, "CRISIS": 0.5},
    )
    leverage_base *= lev_mult
    risk_pct *= risk_mult

    # --- Volatility dampener ---
    atrp = float(atr_pct)
    vol_leverage_scale = 1.0
    if math.isfinite(atrp):
        if atrp > float(cfg.volatility_threshold):
            vol_leverage_scale *= 0.7
            risk_pct *= 0.7
        if atrp < float(cfg.low_volatility_threshold):
            vol_leverage_scale *= 1.1

    # --- Confidence scaling ---
    confidence_factor = _clamp(engine_confidence, 0.5, 1.0)
    risk_pct *= confidence_factor

    # --- Drawdown protection ---
    dd = float(rolling_drawdown_pct)
    drawdown_leverage_scale = 1.0
    if math.isfinite(dd):
        if dd > 0.20:
            drawdown_leverage_scale *= 0.25
            risk_pct *= 0.25
        elif dd > 0.10:
            drawdown_leverage_scale *= 0.5
            risk_pct *= 0.5

    # --- Growth mode ---
    if risk_mode == "growth":
        leverage_base *= 1.2
        risk_pct *= 1.2

    leverage_cap_long = max(
        0.0,
        _side_param(
            side="long",
            long_value=cfg.leverage_cap_long,
            short_value=cfg.leverage_cap_short,
            fallback=cfg.leverage_cap,
        ),
    )
    leverage_cap_short = max(
        0.0,
        _side_param(
            side="short",
            long_value=cfg.leverage_cap_long,
            short_value=cfg.leverage_cap_short,
            fallback=cfg.leverage_cap,
        ),
    )
    leverage = compute_side_aware_leverage(
        base_leverage=float(leverage_base),
        base_leverage_reference=float(base_leverage),
        score=float(confidence_factor * 100.0),
        volatility=float(atrp if math.isfinite(atrp) else 0.0),
        drawdown_pct=float(dd if math.isfinite(dd) else 0.0),
        side=side,
        regime=regime,
        leverage_cap_long=float(leverage_cap_long),
        leverage_cap_short=float(leverage_cap_short),
        volatility_k=float(cfg.vol_k),
        drawdown_sensitivity=float(cfg.drawdown_sensitivity),
        confidence_floor=float(cfg.confidence_floor),
    )
    leverage *= float(vol_leverage_scale)
    leverage *= float(drawdown_leverage_scale)
    if str(regime).upper() == "CRISIS":
        leverage = 1.0

    mode_cap = 8.0 if risk_mode == "growth" else 5.0
    side_cap = max(1.0, leverage_cap_short if side == "short" else leverage_cap_long)
    leverage = _clamp(leverage, 1.0, min(mode_cap, float(side_cap)))
    risk_pct = max(0.0, float(risk_pct))

    # --- ATR-based SL/TP ---
    atr = max(0.0, float(atrp)) * entry
    atr_multiplier = _side_param(
        side=side,
        long_value=cfg.atr_multiplier_long,
        short_value=cfg.atr_multiplier_short,
        fallback=cfg.atr_multiplier,
    )
    regime_key = str(regime).upper()
    if side == "short":
        regime_sl_mult = {"TRENDING": 1.05, "RANGING": 1.15, "CRISIS": 1.35}.get(regime_key, 1.10)
    else:
        regime_sl_mult = {"TRENDING": 1.00, "RANGING": 1.10, "CRISIS": 1.30}.get(regime_key, 1.05)
    atr_multiplier = float(atr_multiplier) * float(regime_sl_mult)
    rr_ratio = _side_param(
        side=side,
        long_value=cfg.rr_ratio_long,
        short_value=cfg.rr_ratio_short,
        fallback=cfg.rr_ratio,
    )
    trailing_activation = _side_param(
        side=side,
        long_value=cfg.trailing_activation_long,
        short_value=cfg.trailing_activation_short,
        fallback=1.0,
    )
    sl_dist = max(atr * max(float(atr_multiplier), 0.0), 0.0)
    sl_dist = max(sl_dist, entry * 1e-6)  # avoid zero-distance stops

    if side == "long":
        sl_price = entry - sl_dist
        tp_price = entry + max(float(rr_ratio), 0.0) * sl_dist
    else:
        sl_price = entry + sl_dist
        tp_price = entry - max(float(rr_ratio), 0.0) * sl_dist

    # --- Risk-based position sizing (notional USD) ---
    stop_distance_pct = abs(entry - sl_price) / entry
    risk_capital = equity * risk_pct
    desired_notional = risk_capital / max(stop_distance_pct, 1e-9)
    max_notional = equity * leverage
    position_size_usd = max(0.0, min(float(desired_notional), float(max_notional)))

    # --- Risk score (0..1): normalized aggressiveness proxy ---
    risk_score = _clamp((risk_pct * leverage) / (0.03 * 8.0), 0.0, 1.0)
    trailing_rules = TrailingRules(
        breakeven_at_r=max(0.1, float(trailing_activation)),
        lock_in_at_r=max(0.2, float(trailing_activation) * 2.0),
        lock_in_profit_r=1.0,
    )

    return RiskDecision(
        leverage=float(leverage),
        position_size_usd=float(position_size_usd),
        sl_price=float(sl_price),
        tp_price=float(tp_price),
        trailing_rules=trailing_rules,
        risk_score=float(risk_score),
    )
