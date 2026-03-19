"""ARGUS v2.5 — Adaptive Growth Sizer: Kelly/Optimal-f Compounding Engine.

Mathematical Framework for 3-digit -> 7-digit Growth
=====================================================

The core problem: given starting capital C_0 ~ $500, reach C_target ~ $1M
while maintaining a Hard Floor that prevents account ruin.

Growth Equation:
    C_n = C_0 * prod(1 + f_i * R_i)  for trades i=1..n

Where:
    f_i = fraction of capital risked on trade i (the sizing decision)
    R_i = return of trade i (positive or negative)

Kelly Criterion gives the growth-optimal f*:
    f* = (p * b - q) / b

Where:
    p = probability of winning (estimated from Chiron confidence + historical win rate)
    b = win/loss ratio (estimated from expected_return / stop_distance)
    q = 1 - p

However, full Kelly is volatile. We use Fractional Kelly:
    f_actual = kelly_fraction * f*

The kelly_fraction ramps up as:
    1. Account grows (more runway = can tolerate more variance)
    2. Conviction aligns (Oracle + Hermes + Engine all agree)
    3. Regime is favorable (trending + high stability)

And ramps down as:
    1. Drawdown increases (Hard Floor protection)
    2. Consecutive losses increase (cold streak dampening)
    3. Correlation with existing positions is high

Hard Floor Mechanism:
    floor_equity = C_0 * hard_floor_pct  (default: never drop below 60% of initial)
    As equity approaches the floor, sizing drops to zero via exponential decay:
        floor_mult = max(0, 1 - exp(-k * (equity - floor_equity) / equity))

Conviction Amplifier (the "Singularity" multiplier):
    When Chronos forecast, Hermes sentiment, and engine signal ALL align
    with >90% agreement, the system is allowed to size above base Kelly
    up to a capped maximum (e.g., 1.5x Kelly).

    This is the mechanism that accelerates growth during high-certainty periods
    while the base system remains conservative during uncertainty.

Growth Phases:
    Phase 1 (Survival): C < $2,000  -> 0.3x Kelly, no leverage
    Phase 2 (Foundation): $2K < C < $10K -> 0.5x Kelly, 1.5x max leverage
    Phase 3 (Growth): $10K < C < $50K -> 0.75x Kelly, 2x max leverage
    Phase 4 (Acceleration): $50K < C < $200K -> 1.0x Kelly, 2.5x max leverage
    Phase 5 (Compounding): C > $200K -> 0.85x Kelly (reduce variance), 2x max leverage
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Growth Phase Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GrowthPhase:
    """Parameters for a specific equity phase."""

    name: str
    equity_floor: float  # Min equity for this phase
    equity_ceiling: float  # Max equity for this phase
    kelly_fraction: float  # Fraction of full Kelly to use
    max_leverage: float
    max_risk_pct: float  # Hard cap on risk per trade
    conviction_amplifier_cap: float  # Max multiplier when conviction is extreme


GROWTH_PHASES = [
    GrowthPhase("SURVIVAL", 0, 2_000, 0.30, 1.0, 0.015, 1.0),
    GrowthPhase("FOUNDATION", 2_000, 10_000, 0.50, 1.5, 0.025, 1.15),
    GrowthPhase("GROWTH", 10_000, 50_000, 0.75, 2.0, 0.035, 1.30),
    GrowthPhase("ACCELERATION", 50_000, 200_000, 1.00, 2.5, 0.045, 1.50),
    GrowthPhase("COMPOUNDING", 200_000, float("inf"), 0.85, 2.0, 0.035, 1.20),
]


def get_growth_phase(equity: float) -> GrowthPhase:
    """Determine current growth phase based on account equity."""
    for phase in GROWTH_PHASES:
        if phase.equity_floor <= equity < phase.equity_ceiling:
            return phase
    return GROWTH_PHASES[-1]


# ---------------------------------------------------------------------------
# Data contracts (backward-compatible with existing SizingInput)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SizingInput:
    """Original sizing input — preserved for backward compatibility."""

    stop_distance: float
    atlas_mult: float
    sentinel_mult: float
    regime_conf: float
    dd_mult: float
    rsl_mult: float
    hermes_mult: float
    leverage_mult: float = 1.0
    base_risk_pct: float = 0.02
    min_risk_pct: float = 0.005
    max_risk_pct: float = 0.03
    max_position_size: float = 0.15


@dataclass(frozen=True)
class SizingResult:
    """Original sizing result — preserved for backward compatibility."""

    risk_per_trade: float
    position_size: float


@dataclass(frozen=True)
class GrowthSizingInput:
    """Extended sizing input for the Adaptive Growth Sizer."""

    # --- Required fields ---
    stop_distance: float  # Fraction (e.g., 0.02 = 2%)
    expected_return: float  # Fraction (e.g., 0.04 = 4%)
    confidence: float  # Engine confidence (0.0 to 1.0)
    equity: float  # Current account equity in USD
    peak_equity: float  # All-time high equity

    # --- Risk multipliers (from pipeline) ---
    atlas_mult: float  # 0.0 to 1.5
    sentinel_mult: float  # 0.0 to 1.0
    regime_conf: float  # 0.0 to 1.0
    rsl_mult: float  # Kill switch multiplier

    # --- Conviction alignment ---
    chronos_alignment: float = 0.0  # -1.0 to 1.0 (how aligned oracle is with trade direction)
    hermes_alignment: float = 0.0  # -1.0 to 1.0 (sentiment alignment)
    engine_alignment: float = 0.0  # 0.0 to 1.0 (sub-strategy strength)

    # --- Account state ---
    consecutive_losses: int = 0
    trades_today: int = 0
    correlation_with_book: float = 0.0  # 0.0 to 1.0
    drawdown: float = 0.0  # Current drawdown as fraction

    # --- Historical performance estimates ---
    historical_win_rate: float = 0.55  # Estimated win rate for this setup
    historical_payoff_ratio: float = 1.5  # Avg win / avg loss

    # --- Safety ---
    hard_floor_pct: float = 0.60  # Never let equity drop below this % of peak
    initial_capital: float = 500.0  # Starting capital

    # --- Leverage ---
    leverage: float = 1.0  # Requested leverage


@dataclass(frozen=True)
class GrowthSizingResult:
    """Output of the Adaptive Growth Sizer."""

    # Core sizing
    risk_per_trade: float  # Fraction of equity to risk
    position_size: float  # Fraction of equity for position
    leverage: float  # Actual leverage to use

    # Kelly decomposition
    kelly_raw: float  # Raw Kelly fraction
    kelly_fraction_used: float  # Phase-adjusted Kelly fraction
    kelly_adjusted: float  # kelly_raw * kelly_fraction_used

    # Multipliers applied
    conviction_multiplier: float
    hard_floor_multiplier: float
    drawdown_multiplier: float
    cold_streak_multiplier: float
    correlation_multiplier: float

    # Metadata
    growth_phase: str
    effective_max_risk: float  # The max risk allowed in this phase
    position_size_usd: float  # Absolute dollar position size


# ---------------------------------------------------------------------------
# Original sizing function (backward-compatible)
# ---------------------------------------------------------------------------


def compute_size(inp: SizingInput) -> SizingResult:
    """Original ARGUS v2.0 sizing — simple multiplicative risk model."""
    risk = (
        inp.base_risk_pct
        * inp.atlas_mult
        * inp.sentinel_mult
        * inp.regime_conf
        * inp.dd_mult
        * inp.rsl_mult
        * inp.hermes_mult
        * inp.leverage_mult
    )
    risk = _clamp(risk, inp.min_risk_pct, inp.max_risk_pct)
    position_size = _clamp(risk / max(inp.stop_distance, 1e-9), 0.0, inp.max_position_size)
    return SizingResult(risk_per_trade=risk, position_size=position_size)


# ---------------------------------------------------------------------------
# Kelly Criterion
# ---------------------------------------------------------------------------


def kelly_criterion(win_rate: float, payoff_ratio: float) -> float:
    """Compute optimal Kelly fraction.

    f* = (p * b - q) / b

    Where p = win probability, b = win/loss ratio, q = 1 - p.

    Returns 0 if the edge is non-positive (no bet).
    """
    p = _clamp(win_rate, 0.01, 0.99)
    b = max(payoff_ratio, 0.01)
    q = 1.0 - p

    f_star = (p * b - q) / b

    # Never return negative (would mean the edge is negative)
    return max(0.0, f_star)


def optimal_f(
    trade_returns: list[float],
    resolution: float = 0.01,
) -> float:
    """Compute Optimal f by brute-force search over trade history.

    Optimal f maximizes the Terminal Wealth Relative (TWR):
        TWR(f) = prod(1 + f * R_i / |worst_loss|)

    This is more robust than Kelly for non-normal return distributions.

    Parameters
    ----------
    trade_returns : List of per-trade returns (fractions, e.g., 0.02 for +2%)
    resolution : Step size for f search

    Returns
    -------
    The fraction f that maximizes TWR (0.0 to 1.0)
    """
    if not trade_returns:
        return 0.0

    worst_loss = min(trade_returns)
    if worst_loss >= 0:
        return 1.0  # All wins — technically unbounded, cap at 1.0

    worst_loss_abs = abs(worst_loss)
    best_f = 0.0
    best_twr = 0.0

    f = resolution
    while f <= 1.0:
        twr = 1.0
        valid = True
        for r in trade_returns:
            hpp = f * r / worst_loss_abs
            twr *= (1.0 + hpp)
            if twr <= 0:
                valid = False
                break

        if valid and twr > best_twr:
            best_twr = twr
            best_f = f

        f += resolution

    return best_f


# ---------------------------------------------------------------------------
# Hard Floor Protection
# ---------------------------------------------------------------------------


def hard_floor_multiplier(
    equity: float,
    peak_equity: float,
    hard_floor_pct: float = 0.60,
    decay_steepness: float = 8.0,
) -> float:
    """Exponential decay multiplier as equity approaches the hard floor.

    Returns a value in [0.0, 1.0] where:
        1.0 = full sizing (equity well above floor)
        0.0 = zero sizing (equity at or below floor)

    The decay is exponential, not linear, so sizing drops sharply near the floor
    to create a "cushion zone" that makes ruin nearly impossible.

    Math:
        floor_equity = peak_equity * hard_floor_pct
        distance = (equity - floor_equity) / equity
        multiplier = max(0, 1 - exp(-k * distance))
    """
    floor_equity = peak_equity * hard_floor_pct
    if equity <= floor_equity:
        return 0.0

    distance = (equity - floor_equity) / max(equity, 1e-9)
    return max(0.0, 1.0 - math.exp(-decay_steepness * distance))


# ---------------------------------------------------------------------------
# Conviction Amplifier
# ---------------------------------------------------------------------------


def conviction_multiplier(
    chronos_alignment: float,
    hermes_alignment: float,
    engine_alignment: float,
    phase_cap: float = 1.3,
) -> float:
    """Compute the conviction amplifier when multiple signals align.

    All three inputs should be in [0.0, 1.0] representing how strongly
    each system agrees with the proposed trade direction.

    The multiplier only activates when ALL three are >0.7 (strong agreement).
    It scales linearly from 1.0 to phase_cap.

    This is the "Singularity" mechanism: when the oracle, news, and technicals
    are in lockstep, the system is allowed to bet bigger.
    """
    # Minimum alignment to activate amplifier
    min_alignment = 0.7

    if (
        chronos_alignment < min_alignment
        or hermes_alignment < min_alignment
        or engine_alignment < min_alignment
    ):
        return 1.0  # No amplification

    # Average alignment (all >= 0.7)
    avg = (chronos_alignment + hermes_alignment + engine_alignment) / 3.0

    # Scale from 1.0 at avg=0.7 to phase_cap at avg=1.0
    scale = (avg - min_alignment) / (1.0 - min_alignment)
    return 1.0 + scale * (phase_cap - 1.0)


# ---------------------------------------------------------------------------
# Cold Streak Dampening
# ---------------------------------------------------------------------------


def cold_streak_multiplier(consecutive_losses: int, decay_rate: float = 0.15) -> float:
    """Reduce sizing after consecutive losses.

    mult = exp(-decay_rate * consecutive_losses)

    0 losses: 1.0
    3 losses: ~0.64
    5 losses: ~0.47
    7 losses: ~0.35
    """
    return math.exp(-decay_rate * max(0, consecutive_losses))


# ---------------------------------------------------------------------------
# Correlation Dampening
# ---------------------------------------------------------------------------


def correlation_dampening(correlation_with_book: float, max_correlation: float = 0.6) -> float:
    """Reduce sizing when new position is correlated with existing book.

    Linear reduction from 1.0 at corr=0 to 0.3 at corr=max_correlation.
    """
    if correlation_with_book <= 0:
        return 1.0
    if correlation_with_book >= max_correlation:
        return 0.3
    return 1.0 - 0.7 * (correlation_with_book / max_correlation)


# ---------------------------------------------------------------------------
# Drawdown-Adaptive Multiplier (enhanced from v2.0)
# ---------------------------------------------------------------------------


def drawdown_multiplier(drawdown: float) -> float:
    """Smooth drawdown scaling (replaces the step-function from v2.0).

    Uses a sigmoid-like curve for gradual reduction:
        mult = 1 / (1 + exp(k * (dd - dd_mid)))

    This avoids the cliff-edge behavior of the old DD_MULTIPLIERS table.
    """
    if drawdown <= 0.005:
        return 1.0

    # Sigmoid centered at 4% drawdown, steepness 80
    k = 80.0
    dd_mid = 0.04
    return 1.0 / (1.0 + math.exp(k * (drawdown - dd_mid)))


# ---------------------------------------------------------------------------
# The Growth Sizer — Main entry point
# ---------------------------------------------------------------------------


def compute_growth_size(inp: GrowthSizingInput) -> GrowthSizingResult:
    """Adaptive Growth Sizer — the core algorithm for exponential compounding.

    Algorithm:
    1. Determine growth phase from equity level
    2. Compute raw Kelly fraction from win rate and payoff ratio
    3. Apply phase-specific Kelly scaling
    4. Compute all safety multipliers (floor, DD, cold streak, correlation)
    5. Compute conviction amplifier
    6. Combine everything into final risk-per-trade
    7. Convert to position size with leverage

    The key insight: this function is ADAPTIVE. It automatically sizes up
    as the account grows (more aggressive Kelly fraction, higher leverage cap)
    and sizes down when risk indicators fire (drawdown, losses, low conviction).
    """
    # 1. Growth phase
    phase = get_growth_phase(inp.equity)

    # 2. Raw Kelly
    # Blend historical win rate with current confidence for better estimation
    effective_win_rate = 0.6 * inp.historical_win_rate + 0.4 * inp.confidence
    effective_payoff = inp.expected_return / max(inp.stop_distance, 1e-9)
    effective_payoff = _clamp(effective_payoff, 0.5, 5.0)

    kelly_raw = kelly_criterion(effective_win_rate, effective_payoff)

    # 3. Phase-adjusted Kelly
    kelly_adjusted = kelly_raw * phase.kelly_fraction

    # 4. Safety multipliers
    hf_mult = hard_floor_multiplier(
        equity=inp.equity,
        peak_equity=inp.peak_equity,
        hard_floor_pct=inp.hard_floor_pct,
    )
    dd_mult = drawdown_multiplier(inp.drawdown)
    cs_mult = cold_streak_multiplier(inp.consecutive_losses)
    corr_mult = correlation_dampening(inp.correlation_with_book)

    # 5. Conviction amplifier
    conv_mult = conviction_multiplier(
        chronos_alignment=inp.chronos_alignment,
        hermes_alignment=inp.hermes_alignment,
        engine_alignment=inp.engine_alignment,
        phase_cap=phase.conviction_amplifier_cap,
    )

    # 6. Pipeline multipliers
    pipeline_mult = (
        inp.atlas_mult
        * inp.sentinel_mult
        * inp.regime_conf
        * inp.rsl_mult
    )

    # 7. Combine into risk per trade
    risk = (
        kelly_adjusted
        * hf_mult
        * dd_mult
        * cs_mult
        * corr_mult
        * conv_mult
        * pipeline_mult
    )

    # Clamp to phase limits
    risk = _clamp(risk, 0.002, phase.max_risk_pct)

    # 8. Leverage determination
    leverage = _clamp(inp.leverage, 1.0, phase.max_leverage)

    # 9. Position size
    # risk_per_trade = position_size * stop_distance / leverage
    # => position_size = risk_per_trade * leverage / stop_distance
    position_size = risk * leverage / max(inp.stop_distance, 1e-9)
    position_size = _clamp(position_size, 0.0, 0.20)  # Never more than 20% of equity

    # Absolute dollar size
    position_size_usd = position_size * inp.equity

    return GrowthSizingResult(
        risk_per_trade=risk,
        position_size=position_size,
        leverage=leverage,
        kelly_raw=kelly_raw,
        kelly_fraction_used=phase.kelly_fraction,
        kelly_adjusted=kelly_adjusted,
        conviction_multiplier=conv_mult,
        hard_floor_multiplier=hf_mult,
        drawdown_multiplier=dd_mult,
        cold_streak_multiplier=cs_mult,
        correlation_multiplier=corr_mult,
        growth_phase=phase.name,
        effective_max_risk=phase.max_risk_pct,
        position_size_usd=position_size_usd,
    )


# ---------------------------------------------------------------------------
# Growth Projection Utility
# ---------------------------------------------------------------------------


def project_growth(
    *,
    initial_capital: float = 500.0,
    target_capital: float = 1_000_000.0,
    avg_risk_per_trade: float = 0.02,
    avg_win_rate: float = 0.58,
    avg_payoff_ratio: float = 1.8,
    trades_per_week: float = 10.0,
) -> dict[str, float]:
    """Project how many trades/weeks/months to reach target.

    This uses the Kelly growth formula:
        G = p * ln(1 + f*b) + q * ln(1 - f)

    Where G is the expected log-growth per trade.

    Returns dict with trades_needed, weeks_needed, months_needed, and
    the implied CAGR.
    """
    p = avg_win_rate
    q = 1.0 - p
    b = avg_payoff_ratio
    f = avg_risk_per_trade

    # Expected log-growth per trade
    g = p * math.log(1.0 + f * b) + q * math.log(max(1e-12, 1.0 - f))

    if g <= 0:
        return {
            "trades_needed": float("inf"),
            "weeks_needed": float("inf"),
            "months_needed": float("inf"),
            "cagr": 0.0,
            "expected_log_growth_per_trade": g,
        }

    # Trades needed: C_0 * exp(n * g) = C_target => n = ln(C_target/C_0) / g
    log_multiple = math.log(target_capital / initial_capital)
    trades_needed = log_multiple / g
    weeks_needed = trades_needed / trades_per_week
    months_needed = weeks_needed / 4.33
    years_needed = months_needed / 12.0

    # CAGR
    trades_per_year = trades_per_week * 52
    cagr = math.exp(g * trades_per_year) - 1.0

    return {
        "trades_needed": trades_needed,
        "weeks_needed": weeks_needed,
        "months_needed": months_needed,
        "years_needed": years_needed,
        "cagr": cagr,
        "expected_log_growth_per_trade": g,
        "doubling_trades": math.log(2.0) / g,
    }
