"""ORION v1 Meta-Orchestrator — Acceptance Tests.

Tests:
1. Weight normalization (sums to ~1.0)
2. Transition boost activates Titan
3. Probe floor enforced
4. Crisis clamps risk
5. PAF state transitions
6. Risk posture small capital mode
7. Multiple signal selection uses weights
8. Telemetry dict has all fields
9. Demo mode does not exit on single failure (implicit)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from src.core.constants import (
    ENGINE_GEMINI,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_PHOENIX,
    ENGINE_TITAN,
    REGIME_CRISIS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)
from src.core.types import EngineSignal, FeatureVector, RegimeState
from src.orchestration.orion import (
    ALL_ENGINES,
    CRISIS_CLAMP_THRESHOLD,
    ENGINE_AFFINITY,
    PROBE_FLOOR,
    EngineWeightEntry,
    OrionDecision,
    OrionOrchestrator,
    RegimeProbabilities,
    RiskPosture,
    _sigmoid,
    _softmax,
)


# ── Helpers ──────────────────────────────────────────────────────

def _make_feature_vector(**overrides: float) -> FeatureVector:
    """Create a FeatureVector with sane defaults, overriding as needed."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        timestamp=now,
        symbol="BTCUSDT",
        asset_class="crypto",
        atr_14=500.0,
        atr_14_pct=0.02,
        atr_ratio_5_20=1.0,
        realized_vol_20d=0.03,
        parkinson_vol=0.025,
        bb_width=0.04,
        adx_14=20.0,
        price_vs_ma200=0.05,
        ema_21_vs_55=0.005,
        lr_slope_20=0.001,
        supertrend_dir=1,
        aroon_osc=20.0,
        rsi_14=50.0,
        bb_pct_b=0.5,
        roc_10=0.01,
        willr_14=-50.0,
        cci_20=0.0,
        volume_ratio=1.0,
        obv_slope_10=100.0,
        vwap_dev_pct=0.001,
        cmf_20=0.05,
        volume_delta=0.0,
        spread_pct=0.001,
        return_autocorr_20=0.0,
        hurst_exponent=0.50,
        entropy_50=3.0,
        frac_diff_price=0.001,
    )
    defaults.update(overrides)  # type: ignore[arg-type]
    return FeatureVector(**defaults)  # type: ignore[arg-type]


def _make_regime_state(regime: str = REGIME_RANGING, confidence: float = 0.7) -> RegimeState:
    """Create a RegimeState with defaults."""
    return RegimeState(
        regime=regime,
        confidence=confidence,
        stability=0.6,
        direction=1,
        candles_in_regime=20,
        rule_regime=regime,
        ml_regime=regime,
        timestamp=datetime.now(timezone.utc),
    )


def _make_engine_signal(engine: str, confidence: float = 0.65) -> EngineSignal:
    """Create a valid EngineSignal."""
    return EngineSignal(
        engine=engine,
        sub_strategy="test",
        asset_class="crypto",
        symbol="BTCUSDT",
        bias="long",
        confidence=confidence,
        stop_distance=0.02,
        expected_return=0.03,
        atr=500.0,
    )


def _make_orion(**kwargs) -> OrionOrchestrator:
    """Create an OrionOrchestrator with defaults."""
    return OrionOrchestrator(
        probe_floor=PROBE_FLOOR,
        account_equity_usd=kwargs.get("account_equity_usd", 500.0),
        enabled=True,
    )


# ── Test 1: Weight normalization ─────────────────────────────────

class TestWeightNormalization:
    """Weights must sum to approximately 1.0 and be non-negative."""

    def test_weights_sum_to_one(self):
        orion = _make_orion()
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        total = sum(decision.engine_weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"

    def test_all_weights_non_negative(self):
        orion = _make_orion()
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_TRENDING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        for eng, w in decision.engine_weights.items():
            assert w >= 0.0, f"Engine {eng} has negative weight {w}"


# ── Test 2: Transition boost activates Titan ─────────────────────

class TestTransitionBoost:
    """When trend transition indicators fire, Titan's weight should increase."""

    def test_titan_weight_increases_with_trend_preconditions(self):
        orion = _make_orion()
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        # First: baseline in calm chop
        fv_chop = _make_feature_vector(
            adx_14=15.0,
            bb_width=0.02,
            ema_21_vs_55=0.001,
            volume_ratio=0.8,
            hurst_exponent=0.40,
        )
        regime_chop = _make_regime_state(REGIME_RANGING)
        decision_chop = orion.step(
            features=fv_chop,
            regime_state=regime_chop,
            candidate_signals=signals,
        )
        titan_chop = decision_chop.engine_weights.get(ENGINE_TITAN, 0.0)

        # Then: trend preconditions fire
        fv_trend = _make_feature_vector(
            adx_14=28.0,
            bb_width=0.06,
            ema_21_vs_55=0.02,
            volume_ratio=2.0,
            hurst_exponent=0.60,
        )
        regime_trend = _make_regime_state(REGIME_TRENDING)
        decision_trend = orion.step(
            features=fv_trend,
            regime_state=regime_trend,
            candidate_signals=signals,
        )
        titan_trend = decision_trend.engine_weights.get(ENGINE_TITAN, 0.0)

        assert titan_trend > titan_chop, (
            f"Titan should have higher weight in trend ({titan_trend:.4f}) "
            f"than chop ({titan_chop:.4f})"
        )


# ── Test 3: Probe floor enforced ─────────────────────────────────

class TestProbeFloor:
    """No engine should drop below probe_floor in non-crisis."""

    def test_minimum_weight_enforced(self):
        orion = _make_orion()
        # Deep chop: Titan should be at or above probe floor
        fv = _make_feature_vector(
            adx_14=12.0,
            bb_width=0.02,
            ema_21_vs_55=0.001,
            hurst_exponent=0.35,
        )
        regime = _make_regime_state(REGIME_RANGING, confidence=0.9)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        for eng, w in decision.engine_weights.items():
            assert w >= PROBE_FLOOR or w == 0.0, (
                f"Engine {eng} weight {w:.4f} below probe floor {PROBE_FLOOR}"
            )

    def test_titan_never_zero_in_chop(self):
        orion = _make_orion()
        fv = _make_feature_vector(
            adx_14=10.0,
            bb_width=0.015,
            ema_21_vs_55=0.0005,
            hurst_exponent=0.30,
        )
        regime = _make_regime_state(REGIME_RANGING, confidence=0.95)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        assert decision.engine_weights[ENGINE_TITAN] > 0.0, (
            "Titan weight must be > 0 in non-crisis (probe floor)"
        )


# ── Test 4: Crisis clamps risk ───────────────────────────────────

class TestCrisisClamp:
    """In crisis, risk posture should block new entries."""

    def test_crisis_blocks_entries(self):
        orion = _make_orion()
        fv = _make_feature_vector(
            adx_14=15.0,
            atr_ratio_5_20=4.0,
            volume_ratio=4.0,
        )
        regime = _make_regime_state(REGIME_CRISIS)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        assert decision.risk_posture.growth_mode == "SURVIVAL"
        assert decision.risk_posture.allow_new_entries is False
        assert decision.risk_posture.risk_multiplier == 0.0

    def test_crisis_weights_go_to_zero(self):
        orion = _make_orion()
        fv = _make_feature_vector(
            adx_14=15.0,
            atr_ratio_5_20=4.0,
            volume_ratio=4.0,
        )
        regime = _make_regime_state(REGIME_CRISIS)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        for eng, w in decision.engine_weights.items():
            assert w == 0.0, f"Engine {eng} should have weight 0 in crisis, got {w}"


# ── Test 5: PAF state transitions ────────────────────────────────

class TestPAFTransitions:
    """PAF state machine should progress PROBE → ARM → FIRE."""

    def test_titan_promotes_to_arm_then_fire(self):
        orion = _make_orion()
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        # Initial: all engines in PROBE
        assert orion._paf_states[ENGINE_TITAN] == "PROBE"

        # Run multiple cycles with strong trend features
        trend_fv = _make_feature_vector(
            adx_14=30.0,
            bb_width=0.07,
            ema_21_vs_55=0.025,
            volume_ratio=2.5,
            hurst_exponent=0.65,
        )
        trend_regime = _make_regime_state(REGIME_TRENDING, confidence=0.85)

        # After enough cycles, TITAN should promote
        for _ in range(10):
            orion.step(
                features=trend_fv,
                regime_state=trend_regime,
                candidate_signals=signals,
            )

        # TITAN should have been promoted to at least ARM
        assert orion._paf_states[ENGINE_TITAN] in ("ARM", "FIRE"), (
            f"TITAN should be ARM or FIRE after 10 trend cycles, got {orion._paf_states[ENGINE_TITAN]}"
        )


# ── Test 6: Risk posture small capital ───────────────────────────

class TestRiskPostureSmallCapital:
    """Small capital should trigger aggressive-but-bounded mode."""

    def test_small_capital_growth_mode(self):
        orion = _make_orion(account_equity_usd=300.0)
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
            account_equity_usd=300.0,
        )

        assert decision.risk_posture.growth_mode == "AGGRESSIVE"
        assert decision.risk_posture.max_trades == 1
        assert decision.risk_posture.risk_multiplier <= 1.0

    def test_micro_capital_defensive(self):
        orion = _make_orion(account_equity_usd=100.0)
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
            account_equity_usd=100.0,
        )

        assert decision.risk_posture.growth_mode == "DEFENSIVE"
        assert decision.risk_posture.max_trades == 1

    def test_large_capital_normal_mode(self):
        orion = _make_orion(account_equity_usd=10000.0)
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
            account_equity_usd=10000.0,
        )

        assert decision.risk_posture.growth_mode == "NORMAL"
        assert decision.risk_posture.risk_multiplier == 1.0

    def test_drawdown_triggers_defensive(self):
        orion = _make_orion(account_equity_usd=5000.0)
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
            account_equity_usd=5000.0,
            drawdown_pct=0.05,
        )

        assert decision.risk_posture.growth_mode == "DEFENSIVE"
        assert decision.risk_posture.risk_multiplier <= 0.25


# ── Test 7: Weighted engine selection ────────────────────────────

class TestEngineSelection:
    """ORION should select the engine with highest composite score."""

    def test_highest_weighted_signal_wins(self):
        orion = _make_orion()

        # Trending regime: Titan should dominate
        fv = _make_feature_vector(
            adx_14=35.0,
            ema_21_vs_55=0.03,
            hurst_exponent=0.65,
            bb_width=0.08,
        )
        regime = _make_regime_state(REGIME_TRENDING, confidence=0.9)

        # All engines have equal confidence
        signals = {e: _make_engine_signal(e, confidence=0.70) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        # In trending, TITAN should have highest compat and thus be chosen
        # (or at least have highest weight)
        titan_w = decision.engine_weights.get(ENGINE_TITAN, 0)
        naut_w = decision.engine_weights.get(ENGINE_NAUTILUS, 0)
        assert titan_w > naut_w, (
            f"TITAN weight ({titan_w:.4f}) should exceed NAUTILUS ({naut_w:.4f}) in trend"
        )

    def test_no_signal_returns_none(self):
        orion = _make_orion()
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)

        # No engines produce signals
        signals: dict[str, EngineSignal | None] = {e: None for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        assert decision.chosen_engine == "NONE"
        assert decision.chosen_engine_weight == 0.0


# ── Test 8: Telemetry fields ─────────────────────────────────────

class TestTelemetryFields:
    """OrionDecision.to_telemetry_dict() must contain all required fields."""

    def test_telemetry_dict_has_required_keys(self):
        orion = _make_orion()
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        telem = decision.to_telemetry_dict()
        required_keys = {
            "regime_probabilities_json",
            "engine_weight_vector_json",
            "chosen_engine",
            "chosen_engine_weight",
            "transition_score",
            "risk_posture_snapshot",
        }
        for key in required_keys:
            assert key in telem, f"Missing telemetry key: {key}"

    def test_telemetry_json_parseable(self):
        import json

        orion = _make_orion()
        fv = _make_feature_vector()
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e) for e in ALL_ENGINES}

        decision = orion.step(
            features=fv,
            regime_state=regime,
            candidate_signals=signals,
        )

        telem = decision.to_telemetry_dict()
        # All JSON strings should be parseable
        for key in ("regime_probabilities_json", "engine_weight_vector_json", "risk_posture_snapshot"):
            parsed = json.loads(telem[key])
            assert isinstance(parsed, dict), f"Telemetry key {key} should be a dict"


# ── Test 9: Helper functions ─────────────────────────────────────

class TestHelpers:
    """Sigmoid and softmax helpers."""

    def test_sigmoid_center(self):
        assert abs(_sigmoid(0.0, center=0.0, steepness=1.0) - 0.5) < 0.01

    def test_sigmoid_high(self):
        assert _sigmoid(10.0, center=0.0, steepness=1.0) > 0.99

    def test_sigmoid_low(self):
        assert _sigmoid(-10.0, center=0.0, steepness=1.0) < 0.01

    def test_softmax_uniform(self):
        result = _softmax([1.0, 1.0, 1.0, 1.0])
        for p in result:
            assert abs(p - 0.25) < 0.01

    def test_softmax_sums_to_one(self):
        result = _softmax([0.5, 1.5, 2.0, 0.3])
        assert abs(sum(result) - 1.0) < 0.01


# ── Test 10: Determinism ─────────────────────────────────────────

class TestDeterminism:
    """Same inputs must produce same outputs."""

    def test_deterministic_decision(self):
        fv = _make_feature_vector(adx_14=22.0, bb_width=0.035)
        regime = _make_regime_state(REGIME_RANGING)
        signals = {e: _make_engine_signal(e, confidence=0.60) for e in ALL_ENGINES}

        # Run twice with fresh orchestrators
        orion1 = _make_orion()
        d1 = orion1.step(features=fv, regime_state=regime, candidate_signals=signals)

        orion2 = _make_orion()
        d2 = orion2.step(features=fv, regime_state=regime, candidate_signals=signals)

        assert d1.engine_weights == d2.engine_weights
        assert d1.chosen_engine == d2.chosen_engine
        assert d1.transition_score == d2.transition_score
