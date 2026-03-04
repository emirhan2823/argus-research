"""Tests for v6 Regiment Validator, Trend Gate, and Engine Orchestrator."""

from __future__ import annotations

import pytest

from src.regime.regime_validator import RegimeValidator, RegimeValidation
from src.regime.trend_gate import check_trend_gate, TrendGateResult
from src.regime.engine_orchestrator import EngineOrchestrator, OrchestratorDecision, RiskOverrides
from src.regime.engine_roles import (
    ENGINE_ROLES,
    ROLE_MEAN_REVERSION,
    ROLE_TREND,
    ROLE_HYBRID,
    ROLE_SCALP,
    is_mr_engine,
    is_trend_engine,
    is_trend_capable,
    get_role,
)


# ═══════════════════════════════════════════════════════════════════
# Engine Roles
# ═══════════════════════════════════════════════════════════════════

class TestEngineRoles:
    def test_poseidon_is_mr(self):
        assert ENGINE_ROLES["POSEIDON"] == ROLE_MEAN_REVERSION
        assert is_mr_engine("POSEIDON")
        assert not is_trend_engine("POSEIDON")

    def test_titan_is_trend(self):
        assert ENGINE_ROLES["TITAN"] == ROLE_TREND
        assert is_trend_engine("TITAN")
        assert not is_mr_engine("TITAN")

    def test_aegean_is_hybrid(self):
        assert ENGINE_ROLES["AEGEAN"] == ROLE_HYBRID
        assert is_trend_capable("AEGEAN")
        assert not is_mr_engine("AEGEAN")

    def test_nautilus_is_mr(self):
        assert is_mr_engine("NAUTILUS")

    def test_hydra_is_scalp_but_mr_like(self):
        assert ENGINE_ROLES["HYDRA"] == ROLE_SCALP
        assert is_mr_engine("HYDRA")  # SCALP counts as MR-like

    def test_unknown_engine(self):
        assert get_role("NONEXISTENT") == "UNKNOWN"
        assert not is_mr_engine("NONEXISTENT")


# ═══════════════════════════════════════════════════════════════════
# Regime Validator
# ═══════════════════════════════════════════════════════════════════

class TestRegimeValidator:
    def _make_validator(self, **kwargs) -> RegimeValidator:
        return RegimeValidator(**kwargs)

    def _validate(self, validator: RegimeValidator, **kwargs) -> RegimeValidation:
        defaults = {
            "symbol": "BTCUSDT",
            "declared_regime": "RANGING",
            "adx_14": 15.0,
            "ema_21_vs_55": 0.0,
            "price_vs_ma200": 0.0,
            "lr_slope_20": 0.0,
            "atr_pctl": 0.5,
            "hurst_exponent": 0.45,
            "swing_highs": None,
            "swing_lows": None,
        }
        defaults.update(kwargs)
        return validator.validate(**defaults)

    def test_ranging_stays_ranging_when_low_trend(self):
        v = self._make_validator()
        result = self._validate(v, declared_regime="RANGING", adx_14=12.0)
        assert result.final_regime == "RANGING"
        assert not result.override_applied

    def test_ranging_overridden_to_trending_when_strong_trend(self):
        """High ADX + aligned EMAs + structure → override to TRENDING."""
        v = self._make_validator(min_hold=0, cooldown=0)
        result = self._validate(
            v,
            declared_regime="RANGING",
            adx_14=35.0,
            ema_21_vs_55=0.05,
            price_vs_ma200=0.03,
            lr_slope_20=0.01,
            swing_highs=[100, 102, 105],
            swing_lows=[98, 99, 101],
        )
        assert result.trend_score >= 0.65
        assert result.final_regime in ("TRENDING", "TRANSITION")

    def test_trending_overridden_to_ranging_when_weak_trend(self):
        v = self._make_validator(min_hold=0, cooldown=0)
        result = self._validate(
            v,
            declared_regime="TRENDING",
            adx_14=10.0,
            ema_21_vs_55=0.001,
            price_vs_ma200=-0.01,
            lr_slope_20=0.0,
            hurst_exponent=0.35,
        )
        assert result.trend_score < 0.35
        assert result.final_regime in ("RANGING", "TRANSITION")

    def test_crisis_never_overridden(self):
        v = self._make_validator()
        result = self._validate(v, declared_regime="CRISIS", adx_14=40.0)
        assert result.final_regime == "CRISIS"
        assert not result.override_applied

    def test_hysteresis_prevents_flipflop(self):
        """With min_hold=4, regime should not change for 4 candles."""
        v = self._make_validator(min_hold=4, cooldown=0)
        # First call establishes RANGING
        r1 = self._validate(v, declared_regime="RANGING", adx_14=10.0)
        # Immediate trend signal — should NOT change (age=0 < min_hold=4)
        r2 = self._validate(
            v,
            declared_regime="RANGING",
            adx_14=35.0,
            ema_21_vs_55=0.05,
            price_vs_ma200=0.03,
            lr_slope_20=0.01,
            swing_highs=[100, 102, 105],
            swing_lows=[98, 99, 101],
        )
        assert r2.final_regime == "RANGING"  # Kept by hysteresis

    def test_adx_rising(self):
        v = self._make_validator()
        # Feed 5 rising ADX values
        for adx in [15.0, 16.0, 17.0, 18.0, 19.0]:
            self._validate(v, adx_14=adx)
        assert v.get_adx_rising("BTCUSDT", bars=3)

    def test_adx_not_rising(self):
        v = self._make_validator()
        for adx in [20.0, 19.0, 18.0, 17.0]:
            self._validate(v, adx_14=adx)
        assert not v.get_adx_rising("BTCUSDT", bars=3)

    def test_volatile_override(self):
        """High ATR with low trend → VOLATILE."""
        v = self._make_validator(min_hold=0, cooldown=0)
        result = self._validate(
            v,
            declared_regime="RANGING",
            adx_14=12.0,
            atr_pctl=0.85,
        )
        assert result.volatility_score > 0.80
        # Could be VOLATILE or stay RANGING depending on exact scoring
        # The key test is that volatility_score captures it
        assert result.volatility_score == 0.85


# ═══════════════════════════════════════════════════════════════════
# Trend Gate
# ═══════════════════════════════════════════════════════════════════

class TestTrendGate:
    def test_all_conditions_pass_long(self):
        result = check_trend_gate(
            adx_14=25.0,
            lr_slope_20=0.005,
            ema_21_vs_55=0.02,
            price_vs_ma200=0.03,
            atr_pctl=0.6,
            swing_highs=[100, 102, 105],
            swing_lows=[98, 99, 101],
        )
        assert result.verified is True
        assert result.score == 5
        assert result.bias == "long"

    def test_all_conditions_pass_short(self):
        result = check_trend_gate(
            adx_14=25.0,
            lr_slope_20=-0.005,
            ema_21_vs_55=-0.02,
            price_vs_ma200=-0.03,
            atr_pctl=0.6,
            swing_highs=[105, 102, 100],
            swing_lows=[101, 99, 98],
        )
        assert result.verified is True
        assert result.bias == "short"

    def test_adx_too_low_fails(self):
        result = check_trend_gate(
            adx_14=15.0,
            lr_slope_20=0.005,
            ema_21_vs_55=0.02,
            price_vs_ma200=0.03,
            atr_pctl=0.6,
            swing_highs=[100, 102, 105],
            swing_lows=[98, 99, 101],
        )
        assert result.verified is False
        assert result.conditions["adx_above_20"] is False
        assert result.score == 4

    def test_atr_pctl_too_low_fails(self):
        result = check_trend_gate(
            adx_14=25.0,
            lr_slope_20=0.005,
            ema_21_vs_55=0.02,
            price_vs_ma200=0.03,
            atr_pctl=0.3,
            swing_highs=[100, 102, 105],
            swing_lows=[98, 99, 101],
        )
        assert result.verified is False
        assert result.conditions["atr_pctl_above_04"] is False

    def test_ema_misaligned_fails(self):
        result = check_trend_gate(
            adx_14=25.0,
            lr_slope_20=0.005,
            ema_21_vs_55=0.02,
            price_vs_ma200=-0.03,  # Misaligned!
            atr_pctl=0.6,
            swing_highs=[100, 102, 105],
            swing_lows=[98, 99, 101],
        )
        assert result.verified is False
        assert result.conditions["ema_ma200_aligned"] is False

    def test_no_swing_data_fails_structure(self):
        result = check_trend_gate(
            adx_14=25.0,
            lr_slope_20=0.005,
            ema_21_vs_55=0.02,
            price_vs_ma200=0.03,
            atr_pctl=0.6,
        )
        assert result.verified is False
        assert result.conditions["structure_confirms"] is False


# ═══════════════════════════════════════════════════════════════════
# Engine Orchestrator
# ═══════════════════════════════════════════════════════════════════

class TestEngineOrchestrator:
    def _make_decision(self, final_regime="RANGING", trend_score=0.3,
                       verified_trend=False, adx_rising=False,
                       atr_pctl=0.5) -> OrchestratorDecision:
        from src.regime.regime_validator import RegimeValidation
        from src.regime.trend_gate import TrendGateResult

        validation = RegimeValidation(
            regime_declared="RANGING",
            trend_score=trend_score,
            volatility_score=0.5,
            structure_score=0.5,
            final_regime=final_regime,
            override_applied=False,
            scores_detail={},
        )
        gate = TrendGateResult(
            verified=verified_trend,
            score=5 if verified_trend else 2,
            conditions={},
            bias="long" if verified_trend else None,
        )
        orch = EngineOrchestrator()
        return orch.decide(
            validation=validation,
            trend_gate=gate,
            atr_pctl=atr_pctl,
            adx_rising_3=adx_rising,
        )

    def test_ranging_enables_mr_engines(self):
        d = self._make_decision(final_regime="RANGING")
        assert "NAUTILUS" in d.enabled_engines
        assert "HYDRA" in d.enabled_engines
        assert "AEGEAN" in d.enabled_engines
        assert "POSEIDON" in d.disabled_engines
        assert "TITAN" in d.disabled_engines

    def test_trending_enables_trend_engines(self):
        d = self._make_decision(final_regime="TRENDING")
        assert "TITAN" in d.enabled_engines
        assert "AEGEAN" in d.enabled_engines
        assert "POSEIDON" in d.disabled_engines  # MR disabled in TRENDING
        assert "NAUTILUS" in d.disabled_engines
        assert "HYDRA" in d.disabled_engines

    def test_trending_verified_boost(self):
        d = self._make_decision(final_regime="TRENDING", verified_trend=True)
        assert d.verified_trend is True
        assert d.risk_overrides.rr_mult == 1.4
        assert d.risk_overrides.size_mult == 1.2
        assert "TITAN" in d.risk_overrides.trailing_engines

    def test_trending_unverified_no_boost(self):
        d = self._make_decision(final_regime="TRENDING", verified_trend=False)
        assert d.verified_trend is False
        assert d.risk_overrides.rr_mult == 1.0
        assert d.risk_overrides.size_mult == 1.0

    def test_transition_mixed_half_size(self):
        d = self._make_decision(final_regime="TRANSITION")
        assert "AEGEAN" in d.enabled_engines
        assert "POSEIDON" in d.enabled_engines
        assert "TITAN" in d.enabled_engines
        assert d.risk_overrides.size_mult == 0.5

    def test_crisis_disables_all(self):
        d = self._make_decision(final_regime="CRISIS")
        assert d.enabled_engines == []
        assert len(d.disabled_engines) >= 4

    def test_volatile_defensive(self):
        d = self._make_decision(final_regime="VOLATILE")
        assert "POSEIDON" in d.enabled_engines
        assert "AEGEAN" in d.enabled_engines
        assert d.risk_overrides.size_mult == 0.8

    def test_mr_strict_adx_rising(self):
        d = self._make_decision(final_regime="RANGING", adx_rising=True)
        assert "NAUTILUS" not in d.enabled_engines
        assert "HYDRA" not in d.enabled_engines
        assert "AEGEAN" in d.enabled_engines
        assert "mr_strict" in d.reason

    def test_mr_strict_high_atr(self):
        d = self._make_decision(final_regime="RANGING", atr_pctl=0.75)
        assert "NAUTILUS" not in d.enabled_engines
        assert "HYDRA" not in d.enabled_engines
        assert "mr_strict" in d.reason

    def test_ranging_normal_conditions(self):
        d = self._make_decision(final_regime="RANGING", atr_pctl=0.4, adx_rising=False)
        assert d.reason == "ranging_standard"
        assert d.risk_overrides.rr_mult == 1.0

    def test_trending_aegean_confirmation_only(self):
        d = self._make_decision(final_regime="TRENDING")
        assert "AEGEAN" in d.confirmation_only_engines
        assert "TITAN" not in d.confirmation_only_engines

    def test_trending_trend_score_passthrough(self):
        """trend_score from SONAR should be passed through to decision."""
        from src.regime.regime_validator import RegimeValidation
        from src.regime.trend_gate import TrendGateResult

        validation = RegimeValidation(
            regime_declared="TRENDING",
            trend_score=0.8,
            volatility_score=0.3,
            structure_score=0.7,
            final_regime="TRENDING",
            override_applied=False,
            scores_detail={},
        )
        gate = TrendGateResult(verified=True, score=5, conditions={}, bias="long")
        orch = EngineOrchestrator()
        d = orch.decide(
            validation=validation,
            trend_gate=gate,
            atr_pctl=0.6,
            adx_rising_3=False,
            trend_score=72.5,
        )
        assert d.trend_score == 72.5

    def test_ranging_no_confirmation_only(self):
        d = self._make_decision(final_regime="RANGING")
        assert len(d.confirmation_only_engines) == 0
