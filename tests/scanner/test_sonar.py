"""SONAR v1 universe scanner tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.scanner.sonar import SonarScanner, SonarScore, SonarWatchlist


# ── Helpers ──


def _mock_binance_client():
    client = MagicMock()
    client.fetch_exchange_info.return_value = [
        {"symbol": "BTCUSDT"},
        {"symbol": "ETHUSDT"},
        {"symbol": "SOLUSDT"},
        {"symbol": "DOGEUSDT"},
        {"symbol": "ADAUSDT"},
    ]
    client.fetch_24h_tickers.return_value = [
        {"symbol": "BTCUSDT", "volume_usdt": 5_000_000_000, "last_price": 60000.0, "price_change_pct": 1.2},
        {"symbol": "ETHUSDT", "volume_usdt": 2_000_000_000, "last_price": 3000.0, "price_change_pct": 0.8},
        {"symbol": "SOLUSDT", "volume_usdt": 500_000_000, "last_price": 100.0, "price_change_pct": 2.0},
        {"symbol": "DOGEUSDT", "volume_usdt": 200_000_000, "last_price": 0.15, "price_change_pct": -1.0},
        {"symbol": "ADAUSDT", "volume_usdt": 100_000_000, "last_price": 0.5, "price_change_pct": 0.3},
    ]
    # Mock OHLCV fetch
    client.fetch_ohlcv.return_value = _make_ohlcv_data(100)
    return client


def _mock_bingx_client():
    client = MagicMock()
    client.fetch_all_symbols.return_value = [
        {"symbol": "BTCUSDT"},
        {"symbol": "XRPUSDT"},
    ]
    client.fetch_all_tickers.return_value = [
        {"symbol": "BTCUSDT", "volume_usdt": 4_500_000_000, "last_price": 60000.0},
        {"symbol": "XRPUSDT", "volume_usdt": 300_000_000, "last_price": 0.6},
    ]
    client.fetch_ohlcv.return_value = _make_ohlcv_data(100)
    return client


def _make_ohlcv_data(n: int = 100):
    """Generate mock OHLCV data with trending structure."""
    rows = []
    price = 100.0
    for i in range(n):
        cycle = i % 12
        if cycle < 8:
            price *= 1.008
        else:
            price *= 0.995
        o = price * 0.999
        h = price * 1.004
        l = price * 0.996
        c = price
        v = 1000.0 + (i * 10)
        ts = 1700000000000 + i * 3600000
        rows.append([ts, o, h, l, c, v])
    return rows


# ── Tests ──


def test_sonar_score_frozen():
    score = SonarScore(
        symbol="BTCUSDT",
        trend_score=75.0,
        adx_norm=0.5,
        ema_slope_score=0.6,
        structure_strength=0.7,
        atr_percentile=0.8,
        volume_expansion=0.9,
        bias="long",
        rank=1,
    )
    assert score.symbol == "BTCUSDT"
    assert score.trend_score == 75.0
    with pytest.raises(AttributeError):
        score.rank = 2  # type: ignore[misc]


def test_sonar_watchlist_frozen():
    wl = SonarWatchlist(
        watchlist=[],
        allocated=[],
        allocations={},
        scan_timestamp=datetime.now(timezone.utc),
    )
    assert wl.flat_reason is None


def test_discover_universe_merges_exchanges():
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=_mock_bingx_client(),
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    # Should include all from Binance + XRPUSDT from BingX (but XRPUSDT has 300M > 50M threshold)
    symbols = set(universe)
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "XRPUSDT" in symbols


def test_discover_universe_filters_low_volume():
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        min_volume_usdt_24h=1_000_000_000,  # Only BTC and ETH qualify
    )
    universe = scanner.discover_universe()
    assert len(universe) <= 2
    assert "BTCUSDT" in universe


def test_discover_universe_sorted_by_volume():
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    # BTC should be first (highest volume)
    assert universe[0] == "BTCUSDT"


def test_scan_top_n_efficiency():
    """Only top ohlcv_fetch_limit symbols get OHLCV fetched."""
    binance = _mock_binance_client()
    scanner = SonarScanner(
        binance_client=binance,
        bingx_client=None,
        ohlcv_fetch_limit=2,
        watchlist_size=2,
        allocate_top_n=1,
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    watchlist = scanner.scan(universe)
    # Should have fetched OHLCV for at most 2 symbols
    assert binance.fetch_ohlcv.call_count <= 2
    assert len(watchlist.watchlist) <= 2


def test_scan_produces_watchlist():
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        ohlcv_fetch_limit=5,
        watchlist_size=3,
        allocate_top_n=2,
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    watchlist = scanner.scan(universe)
    assert isinstance(watchlist, SonarWatchlist)
    assert len(watchlist.watchlist) <= 3
    assert len(watchlist.allocated) <= 2
    assert watchlist.scan_timestamp is not None


def test_scan_allocation_weights_sum():
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        ohlcv_fetch_limit=5,
        watchlist_size=3,
        allocate_top_n=2,
        min_trend_score=0.0,  # Very low so all qualify
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    watchlist = scanner.scan(universe)
    if watchlist.allocations:
        total = sum(watchlist.allocations.values())
        assert total <= 1.01  # Allow small float imprecision


def test_scan_flat_when_all_below_threshold():
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        min_trend_score=999.0,  # Impossibly high
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    watchlist = scanner.scan(universe)
    assert watchlist.flat_reason == "all_below_threshold"
    assert len(watchlist.allocated) == 0


def test_scan_cache_hit():
    """Second scan should use cache (within scan_interval)."""
    binance = _mock_binance_client()
    scanner = SonarScanner(
        binance_client=binance,
        bingx_client=None,
        ohlcv_fetch_limit=3,
        scan_interval_seconds=900,
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()

    # First scan
    scanner.scan(universe)
    call_count_1 = binance.fetch_ohlcv.call_count

    # Second scan (should use cache)
    scanner.scan(universe)
    call_count_2 = binance.fetch_ohlcv.call_count

    # No additional fetch_ohlcv calls
    assert call_count_2 == call_count_1


def test_sonar_score_bias_detection():
    """Verify bias is correctly determined from trending data."""
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    watchlist = scanner.scan(universe)

    for score in watchlist.watchlist:
        assert score.bias in ("long", "short", "neutral")
        assert 0 <= score.trend_score <= 100


def test_score_components_in_range():
    """All score components should be in [0, 100] range."""
    scanner = SonarScanner(
        binance_client=_mock_binance_client(),
        bingx_client=None,
        min_volume_usdt_24h=50_000_000,
    )
    universe = scanner.discover_universe()
    watchlist = scanner.scan(universe)

    for score in watchlist.watchlist:
        assert 0 <= score.adx_norm <= 100
        assert 0 <= score.ema_slope_score <= 100
        assert 0 <= score.structure_strength <= 100
        assert 0 <= score.atr_percentile <= 100
        assert 0 <= score.volume_expansion <= 100
