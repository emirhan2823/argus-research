"""Tests for PR-I01: Whale Momentum contract and aggregation functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.v25.contracts.intelligence import (
    WhaleAlert,
    WhaleDirection,
    WhaleMomentumSignal,
)
from src.engines.hermes.whale_momentum import (
    apply_whale_boost_to_sqs,
    compute_whale_momentum,
)


_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    *,
    direction: WhaleDirection = WhaleDirection.OUTFLOW,
    amount_usd: Decimal = Decimal("15000000"),
    symbol: str = "BTC",
    confidence: Decimal = Decimal("0.85"),
    wallet_address: str | None = "0xabc123",
    ts: datetime | None = None,
) -> WhaleAlert:
    return WhaleAlert(
        chain="ethereum",
        symbol=symbol,
        direction=direction,
        amount_asset=Decimal("200"),
        amount_usd=amount_usd,
        wallet_address=wallet_address,
        confidence=confidence,
        source="whale_alert_api",
        timestamp=ts or _NOW,
    )


# ---------------------------------------------------------------------------
# 1. WhaleMomentumSignal contract validation
# ---------------------------------------------------------------------------


def test_whale_momentum_signal_frozen() -> None:
    """WhaleMomentumSignal is frozen (immutable)."""
    signal = WhaleMomentumSignal(
        symbol="BTC",
        net_flow_usd_24h=Decimal("-5000000"),
        exchange_reserve_change_pct=Decimal("-0.02"),
        is_bullish_flow=True,
        is_bearish_flow=False,
        momentum_score=Decimal("0.7"),
        sqs_boost=Decimal("0.05"),
        confidence=Decimal("0.8"),
    )
    with pytest.raises(Exception):
        signal.symbol = "ETH"  # type: ignore[misc]


def test_whale_momentum_signal_rejects_nan() -> None:
    """NaN values are rejected by ArgusModel validator."""
    with pytest.raises(Exception):
        WhaleMomentumSignal(
            symbol="BTC",
            net_flow_usd_24h=Decimal("NaN"),
            exchange_reserve_change_pct=Decimal("0"),
            is_bullish_flow=False,
            is_bearish_flow=False,
            momentum_score=Decimal("0"),
            sqs_boost=Decimal("0"),
            confidence=Decimal("0"),
        )


def test_whale_momentum_signal_bounds() -> None:
    """momentum_score must be in [-1, 1], sqs_boost in [0, 1], confidence in [0, 1]."""
    with pytest.raises(Exception):
        WhaleMomentumSignal(
            symbol="BTC",
            net_flow_usd_24h=Decimal("0"),
            exchange_reserve_change_pct=Decimal("0"),
            is_bullish_flow=False,
            is_bearish_flow=False,
            momentum_score=Decimal("1.5"),  # > 1.0
            sqs_boost=Decimal("0"),
            confidence=Decimal("0"),
        )


def test_whale_momentum_signal_extra_field_rejected() -> None:
    """Extra fields are rejected (extra=forbid)."""
    with pytest.raises(Exception):
        WhaleMomentumSignal(
            symbol="BTC",
            net_flow_usd_24h=Decimal("0"),
            exchange_reserve_change_pct=Decimal("0"),
            is_bullish_flow=False,
            is_bearish_flow=False,
            momentum_score=Decimal("0"),
            sqs_boost=Decimal("0"),
            confidence=Decimal("0"),
            bogus_field="test",  # type: ignore[call-arg]
        )


def test_whale_momentum_signal_valid_construction() -> None:
    """Valid construction with all required fields."""
    signal = WhaleMomentumSignal(
        symbol="BTC",
        net_flow_usd_24h=Decimal("-20000000"),
        exchange_reserve_change_pct=Decimal("-0.03"),
        stablecoin_mint_usd_24h=Decimal("150000000"),
        accumulation_addresses=5,
        is_bullish_flow=True,
        is_bearish_flow=False,
        momentum_score=Decimal("0.85"),
        sqs_boost=Decimal("0.10"),
        size_modifier=Decimal("1.2"),
        confidence=Decimal("0.9"),
    )
    assert signal.net_flow_usd_24h == Decimal("-20000000")
    assert signal.accumulation_addresses == 5
    assert signal.is_bullish_flow is True
    assert signal.sqs_boost == Decimal("0.10")
    assert signal.size_modifier == Decimal("1.2")


# ---------------------------------------------------------------------------
# 2. compute_whale_momentum — aggregation from WhaleAlert list
# ---------------------------------------------------------------------------


def test_compute_empty_alerts() -> None:
    """Empty alert list returns neutral signal."""
    signal = compute_whale_momentum(whale_alerts=[], timeframe_hours=24)
    assert signal.momentum_score == Decimal("0")
    assert signal.sqs_boost == Decimal("0")
    assert signal.is_bullish_flow is False
    assert signal.is_bearish_flow is False
    assert signal.confidence == Decimal("0")


def test_compute_bullish_outflow_dominance() -> None:
    """Large outflows (bullish) produce positive momentum score."""
    alerts = [
        _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("20000000")),
        _make_alert(direction=WhaleDirection.ACCUMULATION, amount_usd=Decimal("10000000")),
        _make_alert(direction=WhaleDirection.INFLOW, amount_usd=Decimal("5000000")),
    ]
    signal = compute_whale_momentum(whale_alerts=alerts, timeframe_hours=24)
    # net_flow = 5M (in) - 30M (out) = -25M → bullish
    assert signal.net_flow_usd_24h < Decimal("0")
    assert signal.is_bullish_flow is True
    assert signal.is_bearish_flow is False
    assert signal.momentum_score > Decimal("0")
    assert signal.accumulation_addresses > 0


def test_compute_bearish_inflow_dominance() -> None:
    """Large inflows (bearish) produce negative momentum score."""
    alerts = [
        _make_alert(direction=WhaleDirection.INFLOW, amount_usd=Decimal("30000000")),
        _make_alert(direction=WhaleDirection.DISTRIBUTION, amount_usd=Decimal("10000000")),
        _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("5000000"), wallet_address="0xdef456"),
    ]
    signal = compute_whale_momentum(whale_alerts=alerts, timeframe_hours=24)
    # net_flow = 40M (in) - 5M (out) = +35M → bearish
    assert signal.net_flow_usd_24h > Decimal("0")
    assert signal.is_bearish_flow is True
    assert signal.momentum_score < Decimal("0")


def test_compute_tier1_boost() -> None:
    """Momentum > 0.5 with bullish flow produces 0.05 sqs_boost."""
    # Create dominated outflows with median normalization
    alerts = [
        _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("80000000")),
        _make_alert(direction=WhaleDirection.INFLOW, amount_usd=Decimal("10000000")),
    ]
    signal = compute_whale_momentum(
        whale_alerts=alerts,
        timeframe_hours=24,
        median_net_flow_30d=Decimal("50000000"),
    )
    # net_flow = 10M - 80M = -70M; raw_score = 70M/50M = 1.4 → clamped to 1.0
    # momentum >= 0.8 and bullish → tier2 boost
    assert signal.momentum_score >= Decimal("0.5")
    assert signal.sqs_boost >= Decimal("0.05")


def test_compute_tier2_boost() -> None:
    """Momentum > 0.8 with bullish flow produces 0.10 sqs_boost and 1.2 size_modifier."""
    alerts = [
        _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("90000000")),
        _make_alert(direction=WhaleDirection.INFLOW, amount_usd=Decimal("5000000")),
    ]
    signal = compute_whale_momentum(
        whale_alerts=alerts,
        timeframe_hours=24,
        median_net_flow_30d=Decimal("50000000"),
    )
    assert signal.momentum_score >= Decimal("0.8")
    assert signal.sqs_boost == Decimal("0.10")
    assert signal.size_modifier == Decimal("1.2")


def test_compute_old_alerts_excluded() -> None:
    """Alerts outside the timeframe window are excluded."""
    old_ts = _NOW - timedelta(hours=48)
    alerts = [
        _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("50000000"), ts=old_ts),
    ]
    signal = compute_whale_momentum(whale_alerts=alerts, timeframe_hours=24)
    assert signal.momentum_score == Decimal("0")
    assert signal.confidence == Decimal("0")


def test_compute_confidence_average() -> None:
    """Confidence is the average of individual alert confidences."""
    alerts = [
        _make_alert(direction=WhaleDirection.OUTFLOW, confidence=Decimal("0.90")),
        _make_alert(direction=WhaleDirection.OUTFLOW, confidence=Decimal("0.70")),
    ]
    signal = compute_whale_momentum(whale_alerts=alerts, timeframe_hours=24)
    assert signal.confidence == Decimal("0.80")


# ---------------------------------------------------------------------------
# 3. apply_whale_boost_to_sqs
# ---------------------------------------------------------------------------


def test_boost_applied_in_trend_strong() -> None:
    """Boost is applied when regime=TREND_STRONG and base_c5 >= 0.30."""
    signal = WhaleMomentumSignal(
        symbol="BTC",
        net_flow_usd_24h=Decimal("-10000000"),
        exchange_reserve_change_pct=Decimal("0"),
        is_bullish_flow=True,
        is_bearish_flow=False,
        momentum_score=Decimal("0.9"),
        sqs_boost=Decimal("0.10"),
        confidence=Decimal("0.8"),
    )
    result = apply_whale_boost_to_sqs(base_c5=0.60, whale=signal, regime="TREND_STRONG")
    assert result == pytest.approx(0.70)


def test_boost_blocked_wrong_regime() -> None:
    """Boost is zero when regime is not TREND_STRONG."""
    signal = WhaleMomentumSignal(
        symbol="BTC",
        net_flow_usd_24h=Decimal("-10000000"),
        exchange_reserve_change_pct=Decimal("0"),
        is_bullish_flow=True,
        is_bearish_flow=False,
        momentum_score=Decimal("0.9"),
        sqs_boost=Decimal("0.10"),
        confidence=Decimal("0.8"),
    )
    result = apply_whale_boost_to_sqs(base_c5=0.60, whale=signal, regime="RANGING")
    assert result == 0.60


def test_defensive_override_low_c5() -> None:
    """When base_c5 < 0.30, whale boost is ZERO (defensive override per GR-14)."""
    signal = WhaleMomentumSignal(
        symbol="BTC",
        net_flow_usd_24h=Decimal("-10000000"),
        exchange_reserve_change_pct=Decimal("0"),
        is_bullish_flow=True,
        is_bearish_flow=False,
        momentum_score=Decimal("0.9"),
        sqs_boost=Decimal("0.10"),
        confidence=Decimal("0.8"),
    )
    result = apply_whale_boost_to_sqs(base_c5=0.20, whale=signal, regime="TREND_STRONG")
    assert result == 0.20  # No boost, defensive override


def test_boost_capped_at_one() -> None:
    """Boosted C5 is capped at 1.0."""
    signal = WhaleMomentumSignal(
        symbol="BTC",
        net_flow_usd_24h=Decimal("-10000000"),
        exchange_reserve_change_pct=Decimal("0"),
        is_bullish_flow=True,
        is_bearish_flow=False,
        momentum_score=Decimal("0.9"),
        sqs_boost=Decimal("0.10"),
        confidence=Decimal("0.8"),
    )
    result = apply_whale_boost_to_sqs(base_c5=0.95, whale=signal, regime="TREND_STRONG")
    assert result == 1.0
