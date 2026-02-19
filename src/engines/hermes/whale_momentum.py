"""Pure whale-momentum boost helpers (no engine wiring).

Contains:
  - Simplified scoring: ``compute_whale_boost`` / ``build_whale_momentum_signal``
    (operates on pre-aggregated netflow_score).
  - Blueprint Pivot 4 aggregation: ``compute_whale_momentum``
    (aggregates raw ``WhaleAlert`` list into ``WhaleMomentumSignal``).
  - SQS boost application: ``apply_whale_boost_to_sqs``
    (applies whale boost to SQS.C5 component with defensive override).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from src.v25.contracts.intelligence import WhaleAlert, WhaleDirection, WhaleMomentumSignal as FullWhaleMomentumSignal
from src.v25.contracts.whale_momentum import WhaleMomentumSignal


_ZERO = Decimal("0")
_ONE = Decimal("1")
_MIN_CONFIDENCE = Decimal("0.60")
_DEFAULT_MAX_BOOST = Decimal("0.10")

# Thresholds for momentum-to-boost mapping (Blueprint Pivot 4)
_MOMENTUM_TIER1 = Decimal("0.5")   # momentum > 0.5 → sqs_boost = 0.05
_MOMENTUM_TIER2 = Decimal("0.8")   # momentum > 0.8 → sqs_boost = 0.10
_BOOST_TIER1 = Decimal("0.05")
_BOOST_TIER2 = Decimal("0.10")
_SIZE_MOD_BOOSTED = Decimal("1.2")
_SIZE_MOD_DEFAULT = Decimal("1.0")

# Defensive override threshold for apply_whale_boost_to_sqs
_DEFENSIVE_C5_FLOOR = 0.30


# ---------------------------------------------------------------------------
# Simplified scoring (existing API — backward compatible)
# ---------------------------------------------------------------------------


def compute_whale_boost(
    regime: str,
    netflow_score: Decimal,
    confidence: Decimal,
    max_boost: Decimal = _DEFAULT_MAX_BOOST,
) -> tuple[Decimal, bool, str]:
    """Compute C5 boost from whale-flow score under strict gating rules."""
    if regime != "TREND_STRONG":
        return _ZERO, False, "regime_block"
    if confidence < _MIN_CONFIDENCE:
        return _ZERO, False, "low_confidence"
    if netflow_score <= _ZERO:
        return _ZERO, False, "no_accumulation"

    boost = netflow_score * confidence * max_boost
    if boost > max_boost:
        boost = max_boost
    return boost, True, "boost_applied"


def build_whale_momentum_signal(
    *,
    symbol: str,
    ts: datetime,
    regime: str,
    netflow_score: Decimal,
    confidence: Decimal,
    max_boost: Decimal = _DEFAULT_MAX_BOOST,
) -> WhaleMomentumSignal:
    """Build validated WhaleMomentumSignal from pure boost computation."""
    boost, allowed, reason = compute_whale_boost(
        regime=regime,
        netflow_score=netflow_score,
        confidence=confidence,
        max_boost=max_boost,
    )
    return WhaleMomentumSignal(
        symbol=symbol,
        ts=ts,
        regime=regime,
        netflow_score=netflow_score,
        confidence=confidence,
        boost_c5=boost,
        allowed=allowed,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Blueprint Pivot 4: Aggregate WhaleAlert list → WhaleMomentumSignal
# ---------------------------------------------------------------------------


def compute_whale_momentum(
    whale_alerts: list[WhaleAlert],
    timeframe_hours: int = 24,
    median_net_flow_30d: Decimal | None = None,
) -> FullWhaleMomentumSignal:
    """Aggregate whale alerts into a directional momentum signal.

    Logic (per Blueprint Pivot 4):
      1. Sum all OUTFLOW amounts → exchange_drain
      2. Sum all INFLOW amounts → sell_pressure
      3. net_flow = inflow - outflow (negative = bullish/drain)
      4. Check for ACCUMULATION pattern (repeated outflows)
      5. Score: normalize net_flow against 30-day median
      6. Map momentum_score to sqs_boost tier
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=timeframe_hours)

    recent = [a for a in whale_alerts if a.timestamp >= cutoff]
    if not recent:
        return FullWhaleMomentumSignal(
            symbol="AGGREGATE",
            net_flow_usd_24h=_ZERO,
            exchange_reserve_change_pct=_ZERO,
            stablecoin_mint_usd_24h=_ZERO,
            accumulation_addresses=0,
            is_bullish_flow=False,
            is_bearish_flow=False,
            momentum_score=_ZERO,
            sqs_boost=_ZERO,
            size_modifier=_SIZE_MOD_DEFAULT,
            confidence=_ZERO,
        )

    # Aggregate flows
    inflow = sum(
        (a.amount_usd for a in recent if a.direction in (WhaleDirection.INFLOW, WhaleDirection.DISTRIBUTION)),
        _ZERO,
    )
    outflow = sum(
        (a.amount_usd for a in recent if a.direction in (WhaleDirection.OUTFLOW, WhaleDirection.ACCUMULATION)),
        _ZERO,
    )
    net_flow = inflow - outflow  # negative = bullish (drain)

    # Accumulation detection: count unique ACCUMULATION/OUTFLOW addresses
    accum_addrs: set[str] = set()
    for a in recent:
        if a.direction in (WhaleDirection.OUTFLOW, WhaleDirection.ACCUMULATION):
            if a.wallet_address:
                accum_addrs.add(a.wallet_address)

    # Normalize against 30-day median
    if median_net_flow_30d is not None and median_net_flow_30d != _ZERO:
        raw_score = -net_flow / abs(median_net_flow_30d)  # negative net_flow → positive score
    elif (inflow + outflow) > _ZERO:
        raw_score = -net_flow / (inflow + outflow)
    else:
        raw_score = _ZERO

    # Clamp to [-1, 1] and quantize to 10 decimal places (SignedUnitDecimal constraint)
    momentum_score = max(Decimal("-1"), min(Decimal("1"), raw_score))
    momentum_score = momentum_score.quantize(Decimal("0.0000000001"))

    is_bullish = net_flow < _ZERO and len(accum_addrs) > 0
    is_bearish = net_flow > _ZERO

    # Map to SQS boost tier
    if momentum_score >= _MOMENTUM_TIER2 and is_bullish:
        sqs_boost = _BOOST_TIER2
        size_modifier = _SIZE_MOD_BOOSTED
    elif momentum_score >= _MOMENTUM_TIER1 and is_bullish:
        sqs_boost = _BOOST_TIER1
        size_modifier = _SIZE_MOD_DEFAULT
    else:
        sqs_boost = _ZERO
        size_modifier = _SIZE_MOD_DEFAULT

    # Confidence: average of individual alert confidences
    conf_values = [a.confidence for a in recent]
    avg_confidence = sum(conf_values, _ZERO) / Decimal(str(len(conf_values)))
    avg_confidence = max(_ZERO, min(_ONE, avg_confidence))
    avg_confidence = avg_confidence.quantize(Decimal("0.0000000001"))

    # Derive symbol from most common alert symbol
    symbol_counts: dict[str, int] = {}
    for a in recent:
        symbol_counts[a.symbol] = symbol_counts.get(a.symbol, 0) + 1
    top_symbol = max(symbol_counts, key=symbol_counts.get)  # type: ignore[arg-type]

    return FullWhaleMomentumSignal(
        symbol=top_symbol,
        net_flow_usd_24h=net_flow,
        exchange_reserve_change_pct=_ZERO,  # Requires external exchange data
        stablecoin_mint_usd_24h=_ZERO,      # Requires external stablecoin data
        accumulation_addresses=len(accum_addrs),
        is_bullish_flow=is_bullish,
        is_bearish_flow=is_bearish,
        momentum_score=momentum_score,
        sqs_boost=sqs_boost,
        size_modifier=size_modifier,
        confidence=avg_confidence,
    )


# ---------------------------------------------------------------------------
# SQS C5 boost application (Blueprint Pivot 4)
# ---------------------------------------------------------------------------

# Thresholds for determining "trend strong" from TRENDING regime
_TREND_STRONG_CONFIDENCE = 0.70
_TREND_STRONG_STABILITY = 0.60


def is_trend_strong(regime: str, confidence: float = 0.0, stability: float = 0.0) -> bool:
    """Check if regime qualifies as TREND_STRONG.

    The codebase uses TRENDING as the regime string, but Blueprint Pivot 4
    requires TREND_STRONG gating.  We map TRENDING + high confidence + high
    stability to TREND_STRONG semantics.  The literal string "TREND_STRONG"
    is also accepted for backward compatibility with tests.
    """
    if regime == "TREND_STRONG":
        return True
    if regime == "TRENDING" and confidence >= _TREND_STRONG_CONFIDENCE and stability >= _TREND_STRONG_STABILITY:
        return True
    return False


def apply_whale_boost_to_sqs(
    base_c5: float,
    whale: FullWhaleMomentumSignal,
    regime: str,
) -> float:
    """Apply whale momentum boost to SQS component C5.

    Rules (per Blueprint):
      - Only boost in TREND_STRONG regime
      - base_c5 must be >= 0.30 (defensive override: don't boost garbage)
      - Max output: 1.0
      - Defensive override: if base_c5 < 0.30, whale boost is ZERO

    Note: This function accepts the literal "TREND_STRONG" string.
    For pipeline usage with real RegimeState, use ``apply_whale_boost_to_signal``.
    """
    if regime != "TREND_STRONG":
        return base_c5
    if base_c5 < _DEFENSIVE_C5_FLOOR:
        return base_c5  # Defensive overrides offensive (GR-14)
    boosted = min(base_c5 + float(whale.sqs_boost), 1.0)
    return boosted


def apply_whale_boost_to_signal(
    base_confidence: float,
    whale: FullWhaleMomentumSignal,
    regime: str,
    regime_confidence: float = 0.0,
    regime_stability: float = 0.0,
) -> tuple[float, bool, str]:
    """Apply whale momentum boost to signal confidence (pipeline API).

    This is the production-facing wrapper around ``apply_whale_boost_to_sqs``
    that works with the real regime taxonomy (TRENDING, RANGING, etc.)
    instead of the blueprint's TREND_STRONG literal.

    Returns:
        (boosted_confidence, was_applied, reason)
    """
    if not is_trend_strong(regime, regime_confidence, regime_stability):
        return base_confidence, False, "regime_not_trend_strong"
    if base_confidence < _DEFENSIVE_C5_FLOOR:
        return base_confidence, False, "defensive_override"
    boost = float(whale.sqs_boost)
    if boost <= 0.0:
        return base_confidence, False, "no_whale_boost"
    boosted = min(base_confidence + boost, 1.0)
    return boosted, True, "whale_boost_applied"
