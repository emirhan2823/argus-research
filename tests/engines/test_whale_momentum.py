from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.engines.hermes.whale_momentum import build_whale_momentum_signal, compute_whale_boost


def _ts() -> datetime:
    return datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)


def test_regime_block() -> None:
    boost, allowed, reason = compute_whale_boost(
        regime="CHOP",
        netflow_score=Decimal("0.80"),
        confidence=Decimal("0.90"),
    )
    assert boost == Decimal("0")
    assert allowed is False
    assert reason == "regime_block"


def test_low_confidence() -> None:
    boost, allowed, reason = compute_whale_boost(
        regime="TREND_STRONG",
        netflow_score=Decimal("0.80"),
        confidence=Decimal("0.59"),
    )
    assert boost == Decimal("0")
    assert allowed is False
    assert reason == "low_confidence"


def test_no_accumulation() -> None:
    boost, allowed, reason = compute_whale_boost(
        regime="TREND_STRONG",
        netflow_score=Decimal("0"),
        confidence=Decimal("0.90"),
    )
    assert boost == Decimal("0")
    assert allowed is False
    assert reason == "no_accumulation"


def test_positive_accumulation_boost_range() -> None:
    signal = build_whale_momentum_signal(
        symbol="BTCUSDT",
        ts=_ts(),
        regime="TREND_STRONG",
        netflow_score=Decimal("0.80"),
        confidence=Decimal("0.75"),
    )
    assert signal.allowed is True
    assert signal.reason == "boost_applied"
    assert signal.boost_c5 > Decimal("0")
    assert signal.boost_c5 <= Decimal("0.10")
