from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.constants import AC_CRYPTO, AC_US_EQUITY
from src.data.sentinel.validator import SentinelInput, SentinelValidator


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _base_input(asset_class: str = AC_CRYPTO) -> SentinelInput:
    return SentinelInput(
        symbol="BTCUSDT" if asset_class == AC_CRYPTO else "AAPL",
        asset_class=asset_class,
        last_candle_time=NOW - timedelta(minutes=30),
        expected_interval=timedelta(hours=1),
        current_price=101.0,
        previous_prices=[99.8, 100.0, 100.2, 99.9, 100.1],
        current_volume=200.0,
        avg_volume=100.0,
        spread_pct=0.001,
        normal_spread_pct=0.001,
        exchange_latency_ms=250.0,
        orderbook_depth_pct=0.80 if asset_class == AC_CRYPTO else None,
        funding_rate=0.0002 if asset_class == AC_CRYPTO else None,
        normal_funding_rate=0.0001 if asset_class == AC_CRYPTO else None,
        now=NOW,
    )


def test_sentinel_crypto_all_checks_pass() -> None:
    validator = SentinelValidator()
    report = validator.validate(_base_input(AC_CRYPTO))

    assert len(report.checks) == 6
    assert report.score == 1.0
    assert report.action == "PROCEED"
    assert report.confidence_penalty == 0.0


def test_sentinel_non_crypto_skips_crypto_checks() -> None:
    validator = SentinelValidator()
    report = validator.validate(_base_input(AC_US_EQUITY))

    assert len(report.checks) == 4
    assert report.score == 1.0
    assert report.action == "PROCEED"


def test_sentinel_degraded_band() -> None:
    validator = SentinelValidator()
    inp = _base_input(AC_US_EQUITY)
    inp.current_price = 140.0  # Price anomaly fail
    inp.current_volume = 80.0  # no volume confirmation
    inp.exchange_latency_ms = 3500.0  # latency fail

    report = validator.validate(inp)
    assert report.score == 0.5  # 2/4 checks pass
    assert report.action == "DEGRADED"
    assert report.confidence_penalty == 0.30


def test_sentinel_halt_band() -> None:
    validator = SentinelValidator()
    inp = _base_input(AC_CRYPTO)
    inp.last_candle_time = NOW - timedelta(hours=3)  # staleness fail
    inp.current_price = 140.0  # anomaly fail
    inp.current_volume = 50.0
    inp.spread_pct = 0.01  # 10x spread fail
    inp.exchange_latency_ms = 3500.0  # latency fail

    report = validator.validate(inp)
    assert report.score == 2 / 6
    assert report.action == "HALT"
    assert report.confidence_penalty == 1.0


def test_sentinel_emergency_band() -> None:
    validator = SentinelValidator()
    inp = _base_input(AC_CRYPTO)
    inp.last_candle_time = NOW - timedelta(hours=4)
    inp.current_price = 160.0
    inp.current_volume = 40.0
    inp.spread_pct = 0.02
    inp.exchange_latency_ms = 5000.0
    inp.orderbook_depth_pct = 0.10
    inp.funding_rate = 0.005
    inp.normal_funding_rate = 0.0001

    report = validator.validate(inp)
    assert report.score == 0.0
    assert report.action == "EMERGENCY"


def test_price_anomaly_passes_with_volume_confirmation() -> None:
    validator = SentinelValidator()
    inp = _base_input(AC_US_EQUITY)
    inp.current_price = 150.0  # huge move
    inp.current_volume = 1000.0  # enough to confirm move

    report = validator.validate(inp)
    anomaly = [c for c in report.checks if c.check_name == "price_anomaly"][0]
    assert anomaly.passed is True
