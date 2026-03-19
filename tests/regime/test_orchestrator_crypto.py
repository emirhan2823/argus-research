"""Tests for EngineOrchestrator with crypto_fee_mode."""

from __future__ import annotations

import pytest

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
)
from src.regime.engine_orchestrator import EngineOrchestrator
from src.regime.regime_validator import RegimeValidation
from src.regime.trend_gate import TrendGateResult


def _make_validation(regime: str = "RANGING") -> RegimeValidation:
    return RegimeValidation(
        regime_declared=regime,
        trend_score=0.5,
        volatility_score=0.3,
        structure_score=0.5,
        final_regime=regime,
        override_applied=False,
        scores_detail={},
    )


def _make_trend_gate(verified: bool = False) -> TrendGateResult:
    return TrendGateResult(
        verified=verified,
        score=3 if verified else 1,
        conditions={"adx": True, "lr_slope": True, "ema_aligned": True},
        bias="long" if verified else None,
    )


class TestOrchestratorCrypto:
    """EngineOrchestrator with crypto_fee_mode flag."""

    def test_ranging_crypto_only_nautilus_hydra(self):
        """Crypto fee mode: RANGING enables only NAUTILUS+HYDRA (no AEGEAN)."""
        orch = EngineOrchestrator(crypto_fee_mode=True)
        decision = orch.decide(
            validation=_make_validation("RANGING"),
            trend_gate=_make_trend_gate(),
            atr_pctl=0.3,
            adx_rising_3=False,
            adx=18.0,
        )
        assert ENGINE_NAUTILUS in decision.enabled_engines
        assert ENGINE_HYDRA in decision.enabled_engines
        assert ENGINE_AEGEAN not in decision.enabled_engines
        assert ENGINE_AEGEAN in decision.disabled_engines

    def test_ranging_non_crypto_includes_aegean(self):
        """Without crypto mode: RANGING includes AEGEAN."""
        orch = EngineOrchestrator(crypto_fee_mode=False)
        decision = orch.decide(
            validation=_make_validation("RANGING"),
            trend_gate=_make_trend_gate(),
            atr_pctl=0.3,
            adx_rising_3=False,
        )
        assert ENGINE_AEGEAN in decision.enabled_engines

    def test_crypto_adx_above_threshold_disables_mr(self):
        """ADX > crypto_mr_max_adx disables MR engines."""
        orch = EngineOrchestrator(
            crypto_fee_mode=True,
            crypto_mr_max_adx=22.0,
        )
        decision = orch.decide(
            validation=_make_validation("RANGING"),
            trend_gate=_make_trend_gate(),
            atr_pctl=0.3,
            adx_rising_3=False,
            adx=25.0,  # Above 22.0 threshold
        )
        assert ENGINE_NAUTILUS not in decision.enabled_engines
        assert ENGINE_HYDRA not in decision.enabled_engines
        assert "crypto_adx" in decision.reason

    def test_crypto_atr_above_threshold_disables_mr(self):
        """ATR percentile > crypto_mr_max_atr_pctl disables MR engines."""
        orch = EngineOrchestrator(
            crypto_fee_mode=True,
            crypto_mr_max_atr_pctl=0.60,
        )
        decision = orch.decide(
            validation=_make_validation("RANGING"),
            trend_gate=_make_trend_gate(),
            atr_pctl=0.75,  # Above 0.60 threshold
            adx_rising_3=False,
            adx=18.0,  # Below ADX threshold
        )
        assert ENGINE_NAUTILUS not in decision.enabled_engines
        assert ENGINE_HYDRA not in decision.enabled_engines
        assert "crypto_atr_pctl" in decision.reason

    def test_non_crypto_ignores_absolute_adx(self):
        """Without crypto mode, absolute ADX doesn't trigger MR strict."""
        orch = EngineOrchestrator(crypto_fee_mode=False)
        decision = orch.decide(
            validation=_make_validation("RANGING"),
            trend_gate=_make_trend_gate(),
            atr_pctl=0.3,
            adx_rising_3=False,
            adx=30.0,  # High ADX, but non-crypto so ignored
        )
        # Standard MR strict doesn't use absolute ADX
        assert ENGINE_NAUTILUS in decision.enabled_engines
        assert ENGINE_HYDRA in decision.enabled_engines

    def test_trending_unaffected_by_crypto_mode(self):
        """TRENDING regime routing is not affected by crypto_fee_mode."""
        orch = EngineOrchestrator(crypto_fee_mode=True)
        decision = orch.decide(
            validation=_make_validation("TRENDING"),
            trend_gate=_make_trend_gate(verified=True),
            atr_pctl=0.3,
            adx_rising_3=False,
            adx=35.0,
        )
        assert ENGINE_TITAN in decision.enabled_engines
        assert ENGINE_AEGEAN in decision.enabled_engines
        assert decision.verified_trend is True
