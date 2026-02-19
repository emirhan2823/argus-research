"""Tests for CorrelationSignalGenerator (B-01, B-02)."""

from __future__ import annotations

from src.correlation.signals import CorrelationSignalGenerator


def _make_generator(**overrides) -> CorrelationSignalGenerator:
    defaults = dict(entry_zscore=2.0, exit_zscore=0.5, stop_zscore=3.0)
    defaults.update(overrides)
    return CorrelationSignalGenerator(**defaults)


# ── Test: no signal in CRISIS regime ─────────────────────────────


def test_no_signal_in_crisis() -> None:
    gen = _make_generator()
    result = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.90,
        spread_zscore=2.5,
        half_life=10.0,
        is_cointegrated=True,
        regime="CRISIS",
    )
    assert result is None


# ── Test: mean-reversion signal — positive z-score ───────────────


def test_mean_reversion_signal_positive_zscore() -> None:
    """Positive z-score → SHORT A / LONG B (spread too wide)."""
    gen = _make_generator()
    result = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=2.5,
        half_life=12.0,
        is_cointegrated=True,
        regime="RANGING",
    )
    assert result is not None
    assert result["signal_type"] == "MEAN_REVERSION"
    assert result["direction_a"] == "SHORT"
    assert result["direction_b"] == "LONG"
    assert result["spread_zscore"] == 2.5
    assert result["target_zscore"] == 0.5  # exit_zscore
    assert result["stop_zscore"] == 3.0
    assert 0.0 < result["confidence"] <= 1.0
    assert "mean reversion" in result["reason"].lower()


# ── Test: mean-reversion signal — negative z-score ───────────────


def test_mean_reversion_signal_negative_zscore() -> None:
    """Negative z-score → LONG A / SHORT B."""
    gen = _make_generator()
    result = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=-2.8,
        half_life=15.0,
        is_cointegrated=True,
        regime="TRENDING",
    )
    assert result is not None
    assert result["signal_type"] == "MEAN_REVERSION"
    assert result["direction_a"] == "LONG"
    assert result["direction_b"] == "SHORT"
    assert result["spread_zscore"] == -2.8
    assert result["target_zscore"] == -0.5
    assert result["stop_zscore"] == -3.0
    assert 0.0 < result["confidence"] <= 1.0


# ── Test: no signal below threshold ──────────────────────────────


def test_no_signal_below_threshold() -> None:
    gen = _make_generator()
    result = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=1.5,  # below entry_zscore of 2.0
        half_life=10.0,
        is_cointegrated=True,
        regime="RANGING",
    )
    assert result is None


# ── Test: no signal when not cointegrated and low correlation ────


def test_no_signal_not_cointegrated_low_corr() -> None:
    gen = _make_generator()
    result = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.50,  # below 0.70
        spread_zscore=2.5,
        half_life=None,
        is_cointegrated=False,
        regime="RANGING",
    )
    assert result is None


# ── Extra: high-corr but not cointegrated still generates ────────


def test_signal_high_corr_not_cointegrated() -> None:
    """correlation > 0.70 is sufficient even without cointegration."""
    gen = _make_generator()
    result = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.80,
        spread_zscore=2.5,
        half_life=None,
        is_cointegrated=False,
        regime="RANGING",
    )
    assert result is not None
    assert result["signal_type"] == "MEAN_REVERSION"


# ── Test: confidence boost for cointegrated + short half-life ────


def test_confidence_boost_cointegrated_short_halflife() -> None:
    gen = _make_generator()
    # Cointegrated with short half-life
    result_boosted = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=2.5,
        half_life=10.0,
        is_cointegrated=True,
        regime="RANGING",
    )
    # Not cointegrated, no half-life, but high corr
    result_base = gen.generate(
        pair_id="BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=2.5,
        half_life=None,
        is_cointegrated=False,
        regime="RANGING",
    )
    assert result_boosted is not None
    assert result_base is not None
    assert result_boosted["confidence"] > result_base["confidence"]
