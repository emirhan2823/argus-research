from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.data.market_state import Bar
from argus_py.regime.classifier import MarketRegime, MarketRegimeClassifier



def _bars_from_close(closes: np.ndarray) -> list[Bar]:
    out: list[Bar] = []
    base_ts = 1_700_000_000.0
    prev = float(closes[0])
    for i, c in enumerate(closes):
        c = float(c)
        high = max(c, prev) + 0.3
        low = min(c, prev) - 0.3
        out.append(
            Bar(
                timestamp=base_ts + i * 3600.0,
                open=prev,
                high=high,
                low=low,
                close=c,
                volume=1000.0 + i,
            )
        )
        prev = c
    return out



def test_classifier_detects_bull_trend() -> None:
    closes = np.linspace(100.0, 180.0, 260)
    bars = _bars_from_close(closes)
    clf = MarketRegimeClassifier()
    snap = clf.classify(bars)
    assert snap.regime == MarketRegime.BULL_TREND
    assert snap.confidence >= 0.55



def test_classifier_detects_bear_trend() -> None:
    closes = np.linspace(180.0, 95.0, 260)
    bars = _bars_from_close(closes)
    clf = MarketRegimeClassifier()
    snap = clf.classify(bars)
    assert snap.regime == MarketRegime.BEAR_TREND
    assert snap.confidence >= 0.55



def test_classifier_detects_high_vol_chop() -> None:
    rng = np.random.default_rng(4)
    closes = 120 + np.cumsum(rng.normal(0.0, 3.5, 320))
    bars = _bars_from_close(closes)
    clf = MarketRegimeClassifier(high_vol_threshold=0.03)
    snap = clf.classify(bars)
    assert snap.regime == MarketRegime.HIGH_VOL_CHOP



def test_classifier_detects_low_vol_calm() -> None:
    rng = np.random.default_rng(8)
    closes = 100 + np.cumsum(rng.normal(0.0, 0.08, 320))
    bars = _bars_from_close(closes)
    clf = MarketRegimeClassifier()
    snap = clf.classify(bars)
    assert snap.regime == MarketRegime.LOW_VOL_CALM
