from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.data.market_state import Bar
from argus_py.models.orion.indicators import IndicatorService
from argus_py.models.orion.orion import OrionEngine


def _bars(n=260, trend=0.2):
    bars = []
    price = 100.0
    for i in range(n):
        price += trend + np.sin(i / 7.0) * 0.2
        bars.append(
            Bar(
                timestamp=1700000000 + i * 60,
                open=price - 0.3,
                high=price + 0.8,
                low=price - 0.9,
                close=price,
                volume=1000 + i,
            )
        )
    return bars


def test_rsi_length_and_bounds():
    closes = [100 + i * 0.2 for i in range(120)]
    rsi = IndicatorService.rsi(closes)
    assert len(rsi) == len(closes)
    valid = [v for v in rsi if v is not None]
    assert valid
    assert min(valid) >= 0.0
    assert max(valid) <= 100.0


def test_rsi_reflects_selloff():
    closes = [100 - i * 0.5 for i in range(120)]
    rsi = IndicatorService.rsi(closes)
    last = [v for v in rsi if v is not None][-1]
    assert last < 40


def test_macd_lengths_and_histogram_sign():
    closes = [100 + i * 0.3 for i in range(120)]
    macd, signal, hist = IndicatorService.macd(closes)
    assert len(macd) == len(closes)
    assert len(signal) == len(closes)
    assert len(hist) == len(closes)
    assert hist[-1] > -1.0


def test_macd_crossover_bullish():
    assert IndicatorService.macd_crossover([0.1, 0.5], [0.2, 0.3]) == "BULLISH"


def test_macd_crossover_bearish():
    assert IndicatorService.macd_crossover([0.3, 0.1], [0.2, 0.2]) == "BEARISH"


def test_bollinger_ordering():
    closes = [100 + np.sin(i / 5.0) for i in range(120)]
    upper, middle, lower = IndicatorService.bollinger(closes)
    for u, m, l in zip(upper[-20:], middle[-20:], lower[-20:]):
        if np.isnan(u) or np.isnan(m) or np.isnan(l):
            continue
        assert u >= m >= l


def test_bollinger_squeeze_detection():
    closes = [100 + np.sin(i / 3.0) * 3.0 for i in range(100)]
    closes.extend([100 + np.sin(i / 20.0) * 0.02 for i in range(20)])
    upper, middle, lower = IndicatorService.bollinger(closes)
    assert IndicatorService.bollinger_squeeze(upper, middle, lower, window=20)


def test_stochastic_range():
    bars = _bars(140)
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    closes = [b.close for b in bars]
    k, d = IndicatorService.stochastic(highs, lows, closes)
    assert len(k) == len(closes)
    assert len(d) == len(closes)
    assert 0.0 <= k[-1] <= 100.0
    assert 0.0 <= d[-1] <= 100.0


def test_atr_positive_after_warmup():
    bars = _bars(140)
    atr = IndicatorService.atr([b.high for b in bars], [b.low for b in bars], [b.close for b in bars])
    last = [v for v in atr if v is not None][-1]
    assert last > 0.0


def test_cci_returns_values():
    bars = _bars(140)
    cci = IndicatorService.cci([b.high for b in bars], [b.low for b in bars], [b.close for b in bars])
    assert len(cci) == 140
    assert any(v is not None for v in cci)


def test_adx_non_negative():
    bars = _bars(180)
    adx = IndicatorService.adx([b.high for b in bars], [b.low for b in bars], [b.close for b in bars])
    last = [v for v in adx if v is not None][-1]
    assert last >= 0.0


def test_orion_returns_vote_with_components():
    engine = OrionEngine()
    vote = engine.calculate(_bars(320, trend=0.25))
    assert vote is not None
    assert vote.module == "Orion"
    assert 0.0 <= vote.score <= 100.0
    assert "structure" in vote.metadata
    assert "trend" in vote.metadata
    assert "momentum" in vote.metadata
    assert "pattern" in vote.metadata


def test_orion_backward_compatibility_metadata():
    engine = OrionEngine()
    vote = engine.calculate(_bars(320))
    assert "adx" in vote.metadata
    assert "atr" in vote.metadata
    assert "trend_active" in vote.metadata


def test_orion_insufficient_data_returns_warmup_vote():
    engine = OrionEngine()
    vote = engine.calculate(_bars(80))
    assert vote.direction == "FLAT"
    assert vote.metadata.get("orion_valid") is False


def test_orion_total_score_range_with_components():
    engine = OrionEngine()
    vote = engine.calculate(_bars(350, trend=-0.15))
    assert 0.0 <= vote.score <= 100.0
    comp_total = (
        vote.metadata.get("structure", 0.0)
        + vote.metadata.get("trend", 0.0)
        + vote.metadata.get("momentum", 0.0)
        + vote.metadata.get("pattern", 0.0)
    )
    assert abs(comp_total - vote.score) < 1e-9
