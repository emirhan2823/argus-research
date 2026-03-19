"""Tests for GeminiEngine (B-03, B-04)."""

from __future__ import annotations

from src.core.constants import ENGINE_GEMINI, REGIME_CRISIS, REGIME_RANGING
from src.correlation.signals import CorrelationSignalGenerator
from src.correlation.tracker import CorrelationTracker
from src.engines.gemini.engine import GeminiEngine
from tests.unit._v2_helpers import make_feature_vector, make_regime_state


def _make_engine(
    pairs_config: list[dict] | None = None,
    **tracker_overrides,
) -> GeminiEngine:
    """Build a GeminiEngine with a tracker pre-loaded with pair state."""
    if pairs_config is None:
        pairs_config = [
            {"symbol_a": "BTCUSDT", "symbol_b": "ETHUSDT"},
        ]
    tracker = CorrelationTracker(pairs_config)
    signal_gen = CorrelationSignalGenerator()
    return GeminiEngine(tracker=tracker, signal_generator=signal_gen)


def _set_pair_state(
    engine: GeminiEngine,
    pair_id: str,
    *,
    correlation: float = 0.85,
    spread_zscore: float = 2.5,
    is_cointegrated: bool = True,
    half_life: float | None = 12.0,
) -> None:
    """Directly inject pair state into the tracker for testing."""
    pair = engine.tracker._pairs.get(pair_id)
    if pair is None:
        raise KeyError(f"Pair {pair_id!r} not in tracker")
    pair["correlation"] = correlation
    pair["spread_zscore"] = spread_zscore
    pair["is_cointegrated"] = is_cointegrated
    pair["half_life"] = half_life


# ── Test: generate signal with an active pair ────────────────────


def test_generate_signal_with_active_pair() -> None:
    engine = _make_engine()
    _set_pair_state(
        engine,
        "BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=2.5,
        is_cointegrated=True,
        half_life=12.0,
    )

    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(symbol="BTCUSDT"),
    )

    assert sig is not None
    assert sig.engine == ENGINE_GEMINI
    assert sig.sub_strategy == "corr_mean_reversion"
    assert sig.symbol == "BTCUSDT"
    # Positive z-score → SHORT A → bias "short" for symbol_a
    assert sig.bias == "short"
    assert 0.0 < sig.confidence <= 1.0
    assert sig.stop_distance > 0
    assert sig.expected_return > 0


# ── Test: generate signal for symbol_b side ──────────────────────


def test_generate_signal_symbol_b_side() -> None:
    engine = _make_engine()
    _set_pair_state(
        engine,
        "BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=2.5,
        is_cointegrated=True,
    )

    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(symbol="ETHUSDT"),
    )

    assert sig is not None
    assert sig.symbol == "ETHUSDT"
    # Positive z-score → LONG B → bias "long" for symbol_b
    assert sig.bias == "long"


# ── Test: no signal when symbol has no pair ──────────────────────


def test_generate_signal_no_pair() -> None:
    engine = _make_engine()

    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(symbol="SOLUSDT"),
    )

    assert sig is None


# ── Test: no signal in CRISIS regime ─────────────────────────────


def test_generate_signal_crisis_blocked() -> None:
    engine = _make_engine()
    _set_pair_state(
        engine,
        "BTCUSDT_ETHUSDT",
        correlation=0.90,
        spread_zscore=2.5,
        is_cointegrated=True,
    )

    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_CRISIS),
        features=make_feature_vector(symbol="BTCUSDT"),
    )

    assert sig is None


# ── Test: engine name constant ───────────────────────────────────


def test_engine_name_is_gemini() -> None:
    assert ENGINE_GEMINI == "GEMINI"

    engine = _make_engine()
    _set_pair_state(
        engine,
        "BTCUSDT_ETHUSDT",
        correlation=0.85,
        spread_zscore=2.5,
        is_cointegrated=True,
    )

    sig = engine.generate_signal(
        regime=make_regime_state(REGIME_RANGING),
        features=make_feature_vector(symbol="BTCUSDT"),
    )

    assert sig is not None
    assert sig.engine == "GEMINI"
