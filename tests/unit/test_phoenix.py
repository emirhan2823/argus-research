from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.phoenix.phoenix import PhoenixEngine


def _series(n=120, trend=0.1, noise=0.3):
    closes = []
    highs = []
    lows = []
    p = 100.0
    for i in range(n):
        p += trend + np.sin(i / 5.0) * noise
        closes.append(float(p))
        highs.append(float(p + 0.8))
        lows.append(float(p - 0.8))
    return closes, highs, lows


def test_channel_calculation_validity():
    closes, _, _ = _series(80, trend=0.2, noise=0.2)
    engine = PhoenixEngine(lookback=60)
    channel = engine._calculate_channel(closes[-60:])

    assert channel.upper > channel.middle > channel.lower
    assert 0.0 <= channel.r_squared <= 1.0


def test_r_squared_filter_rejects_weak_channel():
    np.random.seed(42)
    closes = list(100 + np.random.randn(100) * 5)
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]

    engine = PhoenixEngine(lookback=60)
    advice = engine.analyze(closes, highs, lows)

    assert advice is not None
    if advice.r_squared < 0.25:
        assert advice.score == 0
        assert "Channel weak" in advice.reason


def test_rsi_divergence_detection():
    engine = PhoenixEngine()
    closes = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85]
    rsi = [20, 22, 24, 26, 28]
    assert engine._check_divergence(closes, rsi) is True


def test_scoring_logic_matches_components():
    engine = PhoenixEngine()
    from argus_py.models.phoenix.phoenix import ChannelLevels, PhoenixSignals

    signals = PhoenixSignals(True, True, True, True)
    channel = ChannelLevels(110, 100, 90, 0.01, 0.8)
    score = engine._calculate_score(signals, rsi=30, channel=channel)
    assert score >= 90


def test_stop_loss_and_targets_calculated():
    closes, highs, lows = _series(120, trend=0.15, noise=0.1)
    engine = PhoenixEngine(lookback=60)
    advice = engine.analyze(closes, highs, lows)

    assert advice is not None
    if advice.score > 0:
        assert advice.target_1 != 0
        assert advice.stop_loss != 0
        assert advice.target_2 >= advice.target_1


def test_analyze_returns_none_for_short_history():
    closes, highs, lows = _series(20)
    engine = PhoenixEngine(lookback=60)
    assert engine.analyze(closes, highs, lows) is None


def test_atr_positive():
    closes, highs, lows = _series(120)
    engine = PhoenixEngine()
    atr = engine._calculate_atr(highs, lows, closes, 14)
    assert atr > 0


def test_reason_contains_signal_tags():
    from argus_py.models.phoenix.phoenix import PhoenixSignals

    engine = PhoenixEngine()
    reason = engine._generate_reason(70.0, PhoenixSignals(True, False, True, True), slope=0.001)
    assert "lower_band_touch" in reason
    assert "bullish_divergence" in reason
