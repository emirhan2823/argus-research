"""ARGUS v6 — Engine Orchestrator.

Replaces static REGIME_TO_ENGINE map with dynamic, context-aware engine
activation policy. Uses validated regime + trend gate to decide which
engines are enabled, disabled, and what risk overrides apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
)
from src.regime.engine_roles import (
    RANGING_ENGINES,
    TREND_ENGINES,
    is_mr_engine,
)
from src.regime.regime_validator import RegimeValidation
from src.regime.trend_gate import TrendGateResult

# ── Regime constants ────────────────────────────────────────────────
_TRENDING = "TRENDING"
_RANGING = "RANGING"
_VOLATILE = "VOLATILE"
_TRANSITION = "TRANSITION"
_CRISIS = "CRISIS"


# ── Output contracts ────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskOverrides:
    """Risk parameter overrides applied by the orchestrator."""

    rr_mult: float = 1.0           # Multiply TP by this (>1 = wider TP)
    size_mult: float = 1.0         # Position size multiplier
    trailing_engines: frozenset[str] = frozenset()  # Engines with trailing enabled


@dataclass(frozen=True)
class OrchestratorDecision:
    """Complete orchestrator output for one pipeline cycle."""

    enabled_engines: list[str]
    disabled_engines: list[str]
    risk_overrides: RiskOverrides
    regime_used: str                # Validated regime actually used
    verified_trend: bool
    reason: str
    confirmation_only_engines: frozenset[str] = frozenset()
    trend_score: float = 0.0


# ── Orchestrator ────────────────────────────────────────────────────

@dataclass
class EngineOrchestrator:
    """Dynamic engine activation based on validated regime + trend gate.

    Policies:
        RANGING:     enable NAUTILUS+HYDRA+AEGEAN, disable POSEIDON+TITAN
        TRENDING:    enable TITAN+AEGEAN (TITAN priority), disable MR engines
        TRANSITION:  enable AEGEAN+POSEIDON+TITAN, half size
        VOLATILE:    enable POSEIDON+AEGEAN, disable NAUTILUS+HYDRA+TITAN
        CRISIS:      disable all

    MR Strict Mode:
        Force-disable NAUTILUS+HYDRA when:
        - ADX rising 3+ consecutive bars
        - ATR percentile > 0.7
        - Regime = TRANSITION

    Trend Boost (when verified_trend=True):
        - RR multiplier: 1.4 (effective 2.5-3.5 RR)
        - Size multiplier: 1.2
        - Trailing: POSEIDON + TITAN
    """

    # Trend boost parameters
    trend_rr_mult: float = 1.4
    trend_size_mult: float = 1.2
    mr_strict_atr_threshold: float = 0.70

    # Crypto fee mode parameters
    crypto_fee_mode: bool = False
    crypto_mr_max_adx: float = 22.0
    crypto_mr_max_atr_pctl: float = 0.60
    crypto_ranging_engines: list[str] = field(
        default_factory=lambda: [ENGINE_NAUTILUS, ENGINE_HYDRA]
    )

    def decide(
        self,
        *,
        validation: RegimeValidation,
        trend_gate: TrendGateResult,
        atr_pctl: float,
        adx_rising_3: bool,
        adx: float = 0.0,
        trend_score: float = 0.0,
    ) -> OrchestratorDecision:
        """Produce an orchestration decision for the current cycle."""

        regime = validation.final_regime

        # ── Base policy by regime ──
        if regime == _CRISIS:
            return OrchestratorDecision(
                enabled_engines=[],
                disabled_engines=[ENGINE_POSEIDON, ENGINE_TITAN, ENGINE_NAUTILUS, ENGINE_HYDRA, ENGINE_AEGEAN],
                risk_overrides=RiskOverrides(),
                regime_used=regime,
                verified_trend=False,
                reason="crisis_all_disabled",
            )

        if regime == _TRANSITION:
            return OrchestratorDecision(
                enabled_engines=[ENGINE_AEGEAN, ENGINE_POSEIDON, ENGINE_TITAN],
                disabled_engines=[ENGINE_NAUTILUS, ENGINE_HYDRA],
                risk_overrides=RiskOverrides(size_mult=0.5),
                regime_used=regime,
                verified_trend=False,
                reason="transition_mixed_half_size",
            )

        if regime == _RANGING:
            if self.crypto_fee_mode:
                enabled = list(self.crypto_ranging_engines)
                _all_engines = [ENGINE_POSEIDON, ENGINE_TITAN, ENGINE_AEGEAN, ENGINE_NAUTILUS, ENGINE_HYDRA]
                disabled = [e for e in _all_engines if e not in enabled]
            else:
                enabled = [ENGINE_NAUTILUS, ENGINE_HYDRA, ENGINE_AEGEAN]
                disabled = [ENGINE_POSEIDON, ENGINE_TITAN]

            # ── MR Strict Mode: disable MR engines in deteriorating conditions ──
            mr_disabled = self._check_mr_strict(
                adx_rising_3=adx_rising_3,
                atr_pctl=atr_pctl,
                adx=adx,
            )
            if mr_disabled:
                enabled = [ENGINE_AEGEAN]  # Fallback to hybrid
                disabled = [ENGINE_POSEIDON, ENGINE_TITAN, ENGINE_NAUTILUS, ENGINE_HYDRA]
                return OrchestratorDecision(
                    enabled_engines=enabled,
                    disabled_engines=disabled,
                    risk_overrides=RiskOverrides(size_mult=0.5),
                    regime_used=regime,
                    verified_trend=False,
                    reason=f"ranging_mr_strict_{mr_disabled}",
                )

            return OrchestratorDecision(
                enabled_engines=enabled,
                disabled_engines=disabled,
                risk_overrides=RiskOverrides(),
                regime_used=regime,
                verified_trend=False,
                reason="ranging_standard",
            )

        if regime == _TRENDING:
            # TITAN v2 primary in TRENDING; AEGEAN confirmation-only (no standalone signals)
            enabled = [ENGINE_TITAN, ENGINE_AEGEAN]
            disabled = [ENGINE_POSEIDON, ENGINE_NAUTILUS, ENGINE_HYDRA]
            confirm_only = frozenset({ENGINE_AEGEAN})

            # ── Trend Boost if verified ──
            if trend_gate.verified:
                return OrchestratorDecision(
                    enabled_engines=enabled,
                    disabled_engines=disabled,
                    risk_overrides=RiskOverrides(
                        rr_mult=self.trend_rr_mult,
                        size_mult=self.trend_size_mult,
                        trailing_engines=frozenset({ENGINE_TITAN}),
                    ),
                    regime_used=regime,
                    verified_trend=True,
                    reason="trending_verified_boost",
                    confirmation_only_engines=confirm_only,
                    trend_score=trend_score,
                )

            return OrchestratorDecision(
                enabled_engines=enabled,
                disabled_engines=disabled,
                risk_overrides=RiskOverrides(
                    trailing_engines=frozenset({ENGINE_TITAN}),
                ),
                regime_used=regime,
                verified_trend=False,
                reason="trending_unverified",
                confirmation_only_engines=confirm_only,
                trend_score=trend_score,
            )

        if regime == _VOLATILE:
            return OrchestratorDecision(
                enabled_engines=[ENGINE_POSEIDON, ENGINE_AEGEAN],
                disabled_engines=[ENGINE_NAUTILUS, ENGINE_HYDRA, ENGINE_TITAN],
                risk_overrides=RiskOverrides(size_mult=0.8),
                regime_used=regime,
                verified_trend=False,
                reason="volatile_defensive",
            )

        # Fallback: treat unknown as TRANSITION
        return OrchestratorDecision(
            enabled_engines=[ENGINE_AEGEAN],
            disabled_engines=[ENGINE_POSEIDON, ENGINE_TITAN, ENGINE_NAUTILUS, ENGINE_HYDRA],
            risk_overrides=RiskOverrides(size_mult=0.5),
            regime_used=regime,
            verified_trend=False,
            reason=f"unknown_regime_{regime}",
        )

    def _check_mr_strict(
        self,
        *,
        adx_rising_3: bool,
        atr_pctl: float,
        adx: float = 0.0,
    ) -> Optional[str]:
        """Check MR strict mode conditions. Returns reason if disabled, None if OK."""

        # Crypto fee mode: absolute ADX and ATR thresholds
        if self.crypto_fee_mode:
            if adx > self.crypto_mr_max_adx:
                return f"crypto_adx_{adx:.1f}_gt_{self.crypto_mr_max_adx}"
            if atr_pctl > self.crypto_mr_max_atr_pctl:
                return f"crypto_atr_pctl_{atr_pctl:.2f}"

        if adx_rising_3:
            return "adx_rising_3bars"

        if atr_pctl > self.mr_strict_atr_threshold:
            return f"atr_pctl_{atr_pctl:.2f}"

        return None
