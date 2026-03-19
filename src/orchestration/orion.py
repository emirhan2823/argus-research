"""ORION v1 Meta-Orchestrator — Dynamic engine weighting & risk posture.

ORION sits between regime detection and engine dispatch to:
1. Compute soft regime probabilities (no hard classification)
2. Detect regime transitions (compression → expansion, etc.)
3. Assign per-engine weights via affinity matrix + performance scores
4. Apply Probe → Arm → Fire (PAF) state machine per engine
5. Set dynamic risk posture for small capital growth mode
6. Emit full telemetry for future self-learning

ORION does NOT generate signals, replace HERMES/ATLAS overlays,
or change any existing safety semantics.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.core.constants import (
    ENGINE_AEGEAN,
    ENGINE_GEMINI,
    ENGINE_HYDRA,
    ENGINE_NAUTILUS,
    ENGINE_POSEIDON,
    ENGINE_TITAN,
    REGIME_CRISIS,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_VOLATILE,
)
from src.core.types import EngineSignal, FeatureVector, RegimeState

_LOG = logging.getLogger("argus.orion")

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

ALL_ENGINES = (ENGINE_TITAN, ENGINE_NAUTILUS, ENGINE_HYDRA, ENGINE_GEMINI, ENGINE_AEGEAN, ENGINE_POSEIDON)

# Engine regime affinity matrix — soft compatibility scores [0.0, 1.0]
# These are v1 starting values; Phase 2 learns them from data.
ENGINE_AFFINITY: dict[str, dict[str, float]] = {
    ENGINE_TITAN: {
        REGIME_TRENDING: 1.0,
        REGIME_RANGING: 0.0,   # TITAN v2: fully disabled in ranging
        REGIME_VOLATILE: 0.30,
        REGIME_CRISIS: 0.0,
    },
    ENGINE_NAUTILUS: {
        REGIME_TRENDING: 0.15,
        REGIME_RANGING: 1.0,
        REGIME_VOLATILE: 0.50,
        REGIME_CRISIS: 0.0,
    },
    ENGINE_HYDRA: {
        REGIME_TRENDING: 0.30,
        REGIME_RANGING: 0.80,
        REGIME_VOLATILE: 0.70,
        REGIME_CRISIS: 0.0,
    },
    ENGINE_GEMINI: {
        REGIME_TRENDING: 0.20,
        REGIME_RANGING: 0.90,
        REGIME_VOLATILE: 0.50,
        REGIME_CRISIS: 0.0,
    },
    ENGINE_AEGEAN: {
        REGIME_TRENDING: 0.40,  # Confirmation-only in TRENDING (TITAN is primary)
        REGIME_RANGING: 0.95,
        REGIME_VOLATILE: 0.70,
        REGIME_CRISIS: 0.0,
    },
    ENGINE_POSEIDON: {
        REGIME_TRENDING: 0.50,
        REGIME_RANGING: 1.0,
        REGIME_VOLATILE: 0.80,
        REGIME_CRISIS: 0.0,
    },
}

# Probe floor: minimum weight assigned to any engine (non-crisis)
PROBE_FLOOR = 0.01

# PAF thresholds
PAF_ARM_PRECONDITIONS_NEEDED = 3   # preconditions met → ARM
PAF_FIRE_MOMENTUM_THRESHOLD = 0.6  # transition_to_trend > this → FIRE
PAF_COOLDOWN_CYCLES = 5            # min cycles before downgrading from FIRE

# Regime momentum EMA smoothing
REGIME_MOMENTUM_ALPHA = 0.3

# Crisis risk posture clamp threshold
CRISIS_CLAMP_THRESHOLD = 0.70

# Growth mode equity ceiling (USD)
GROWTH_MODE_EQUITY_CEILING = 5000.0

# ─────────────────────────────────────────────────────────────────
# Data Contracts
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegimeProbabilities:
    """Soft probability distribution over regimes."""
    trend: float
    chop: float
    volatile: float
    crisis: float
    transition_to_trend: float  # Trend transition probability

    def as_dict(self) -> dict[str, float]:
        return {
            REGIME_TRENDING: self.trend,
            REGIME_RANGING: self.chop,
            REGIME_VOLATILE: self.volatile,
            REGIME_CRISIS: self.crisis,
        }


@dataclass(frozen=True)
class RiskPosture:
    """Dynamic risk posture output."""
    risk_multiplier: float
    max_trades: int
    daily_loss_limit: float
    allow_new_entries: bool
    growth_mode: str          # "AGGRESSIVE" | "NORMAL" | "DEFENSIVE" | "SURVIVAL"
    reason: str


@dataclass(frozen=True)
class EngineWeightEntry:
    """Weight detail for a single engine."""
    engine: str
    compat_score: float
    paf_state: str           # "PROBE" | "ARM" | "FIRE"
    transition_boost: float
    raw_weight: float
    final_weight: float


@dataclass(frozen=True)
class OrionDecision:
    """Complete ORION output for a single cycle."""
    regime_probabilities: RegimeProbabilities
    engine_weights: dict[str, float]
    engine_details: dict[str, EngineWeightEntry]
    risk_posture: RiskPosture
    chosen_engine: str
    chosen_engine_weight: float
    transition_score: float
    timestamp: datetime

    def to_telemetry_dict(self) -> dict[str, Any]:
        """Serialize for decision logging."""
        return {
            "regime_probabilities_json": json.dumps({
                "trend": self.regime_probabilities.trend,
                "chop": self.regime_probabilities.chop,
                "volatile": self.regime_probabilities.volatile,
                "crisis": self.regime_probabilities.crisis,
                "transition_to_trend": self.regime_probabilities.transition_to_trend,
            }),
            "engine_weight_vector_json": json.dumps(self.engine_weights),
            "chosen_engine": self.chosen_engine,
            "chosen_engine_weight": self.chosen_engine_weight,
            "transition_score": self.transition_score,
            "risk_posture_snapshot": json.dumps({
                "risk_multiplier": self.risk_posture.risk_multiplier,
                "max_trades": self.risk_posture.max_trades,
                "daily_loss_limit": self.risk_posture.daily_loss_limit,
                "allow_new_entries": self.risk_posture.allow_new_entries,
                "growth_mode": self.risk_posture.growth_mode,
                "reason": self.risk_posture.reason,
            }),
        }


# ─────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────

def _sigmoid(x: float, center: float = 0.0, steepness: float = 1.0) -> float:
    """Sigmoid function mapping x to (0, 1)."""
    z = steepness * (x - center)
    z = max(-500.0, min(500.0, z))  # numerical guard
    return 1.0 / (1.0 + math.exp(-z))


def _softmax(values: list[float]) -> list[float]:
    """Softmax normalization to produce probability distribution."""
    max_v = max(values) if values else 0.0
    exps = [math.exp(v - max_v) for v in values]
    total = sum(exps)
    if total < 1e-12:
        n = len(values)
        return [1.0 / n] * n if n > 0 else []
    return [e / total for e in exps]


# ─────────────────────────────────────────────────────────────────
# ORION Orchestrator
# ─────────────────────────────────────────────────────────────────

class OrionOrchestrator:
    """ORION v1 Meta-Orchestrator.

    Call ``step()`` once per pipeline cycle after regime detection
    and before engine dispatch.
    """

    def __init__(
        self,
        *,
        probe_floor: float = PROBE_FLOOR,
        account_equity_usd: float = 500.0,
        enabled: bool = True,
    ) -> None:
        self.probe_floor = probe_floor
        self.account_equity_usd = account_equity_usd
        self.enabled = enabled

        # PAF state per engine: "PROBE" | "ARM" | "FIRE"
        self._paf_states: dict[str, str] = {e: "PROBE" for e in ALL_ENGINES}
        self._paf_cycles: dict[str, int] = {e: 0 for e in ALL_ENGINES}

        # Regime probability history for momentum computation
        self._prob_history: list[RegimeProbabilities] = []

        # Precondition counters per engine (cycles in a row with preconditions met)
        self._precondition_counters: dict[str, int] = {e: 0 for e in ALL_ENGINES}

        # Cycle counter
        self._cycle: int = 0

    # ─── Public API ──────────────────────────────────────────────

    def step(
        self,
        *,
        features: FeatureVector,
        regime_state: RegimeState,
        candidate_signals: dict[str, Optional[EngineSignal]],
        account_equity_usd: float | None = None,
        drawdown_pct: float = 0.0,
        daily_pnl_pct: float = 0.0,
        trades_today: int = 0,
    ) -> OrionDecision:
        """Run one ORION cycle.

        Args:
            features: Current FeatureVector for the symbol.
            regime_state: Current RegimeState from the regime detector.
            candidate_signals: Signals from ALL engines {engine_name: signal_or_None}.
            account_equity_usd: Current account equity. If None, uses init default.
            drawdown_pct: Current drawdown as fraction (0.0 = no drawdown).
            daily_pnl_pct: Today's PnL as fraction.
            trades_today: Number of trades executed today.

        Returns:
            OrionDecision with weights, risk posture, and chosen engine.
        """
        self._cycle += 1
        now = datetime.now(timezone.utc)
        equity = account_equity_usd if account_equity_usd is not None else self.account_equity_usd

        # 1. Compute regime probabilities
        regime_probs = self._compute_regime_probabilities(features, regime_state)
        self._prob_history.append(regime_probs)
        if len(self._prob_history) > 50:
            self._prob_history = self._prob_history[-50:]

        # 2. Compute transition score
        transition_score = self._compute_transition_to_trend(features, regime_probs)

        # Create final regime probs with transition
        final_probs = RegimeProbabilities(
            trend=regime_probs.trend,
            chop=regime_probs.chop,
            volatile=regime_probs.volatile,
            crisis=regime_probs.crisis,
            transition_to_trend=transition_score,
        )

        # 3. Update PAF states
        self._update_paf_states(final_probs, transition_score)

        # 4. Compute engine weights
        engine_weights, engine_details = self._compute_engine_weights(final_probs, transition_score)

        # 5. Compute risk posture
        risk_posture = self._compute_risk_posture(
            equity=equity,
            drawdown_pct=drawdown_pct,
            daily_pnl_pct=daily_pnl_pct,
            crisis_prob=final_probs.crisis,
            trades_today=trades_today,
        )

        # 6. Select best engine from candidates using weights
        chosen_engine, chosen_weight = self._select_best_engine(
            candidate_signals=candidate_signals,
            engine_weights=engine_weights,
            risk_posture=risk_posture,
        )

        decision = OrionDecision(
            regime_probabilities=final_probs,
            engine_weights=engine_weights,
            engine_details=engine_details,
            risk_posture=risk_posture,
            chosen_engine=chosen_engine,
            chosen_engine_weight=chosen_weight,
            transition_score=transition_score,
            timestamp=now,
        )

        _LOG.info(
            "orion cycle=%d | weights=%s | chosen=%s(%.3f) | risk=%s | transition=%.3f",
            self._cycle,
            {k: round(v, 3) for k, v in engine_weights.items()},
            chosen_engine,
            chosen_weight,
            risk_posture.growth_mode,
            transition_score,
        )

        return decision

    # ─── Regime Probability Computation ──────────────────────────

    def _compute_regime_probabilities(
        self,
        fv: FeatureVector,
        regime_state: RegimeState,
    ) -> RegimeProbabilities:
        """Compute soft regime probabilities using sigmoid-based fuzzy membership."""

        adx = fv.adx_14
        ema_spread = abs(fv.ema_21_vs_55)
        hurst = fv.hurst_exponent
        atr_ratio = fv.atr_ratio_5_20
        vol_ratio = fv.volume_ratio
        bb_width = fv.bb_width

        # Trend membership raw score
        trend_raw = (
            0.35 * _sigmoid(adx, center=25.0, steepness=0.25)
            + 0.25 * _sigmoid(ema_spread, center=0.01, steepness=150.0)
            + 0.20 * _sigmoid(hurst, center=0.55, steepness=12.0)
            + 0.20 * _sigmoid(adx, center=20.0, steepness=0.15)  # softer ADX
        )

        # Chop/Ranging membership
        chop_raw = (
            0.30 * _sigmoid(-adx, center=-20.0, steepness=0.25)
            + 0.25 * _sigmoid(-hurst, center=-0.45, steepness=12.0)
            + 0.25 * _sigmoid(-ema_spread, center=-0.005, steepness=150.0)
            + 0.20 * _sigmoid(-atr_ratio, center=-1.0, steepness=2.0)
        )

        # Volatile membership
        volatile_raw = (
            0.40 * _sigmoid(atr_ratio, center=1.8, steepness=2.0)
            + 0.30 * _sigmoid(vol_ratio, center=2.0, steepness=1.5)
            + 0.30 * _sigmoid(bb_width, center=0.06, steepness=25.0)
        )

        # Crisis membership — from existing regime detection + price action
        crisis_raw = 0.05  # base
        if regime_state.regime == REGIME_CRISIS:
            crisis_raw = 0.80
        elif atr_ratio > 3.0 and vol_ratio > 3.0:
            crisis_raw = 0.40

        # Softmax normalize to sum to 1.0
        raw = [trend_raw, chop_raw, volatile_raw, crisis_raw]
        probs = _softmax(raw)

        # If the hard regime detector says CRISIS, respect it —
        # floor the crisis probability at the raw score so the
        # crisis clamp can activate.
        final_crisis = probs[3]
        if regime_state.regime == REGIME_CRISIS:
            final_crisis = max(final_crisis, crisis_raw)

        # Re-normalize if crisis was boosted
        if final_crisis > probs[3]:
            remaining = 1.0 - final_crisis
            other_sum = probs[0] + probs[1] + probs[2]
            if other_sum > 1e-12:
                scale = remaining / other_sum
                probs = [probs[0] * scale, probs[1] * scale, probs[2] * scale, final_crisis]
            else:
                probs = [0.0, 0.0, 0.0, final_crisis]

        return RegimeProbabilities(
            trend=round(probs[0], 4),
            chop=round(probs[1], 4),
            volatile=round(probs[2], 4),
            crisis=round(probs[3], 4),
            transition_to_trend=0.0,  # filled later
        )

    # ─── Regime Transition Detector ──────────────────────────────

    def _compute_transition_to_trend(
        self,
        fv: FeatureVector,
        current_probs: RegimeProbabilities,
    ) -> float:
        """Detect transition-to-trend probability.

        Uses:
        - ADX rising (inflecting up from low)
        - BB squeeze expanding (compression → expansion)
        - EMA spread widening after tight range
        - Momentum from regime probability history
        """
        signals: list[float] = []

        # 1. ADX rising from low base — trend forming
        # ADX < 25 but positive slope → early trend
        adx = fv.adx_14
        if adx < 30.0:
            adx_score = _sigmoid(adx, center=18.0, steepness=0.20)
            signals.append(adx_score * 0.30)

        # 2. BB squeeze → expansion
        # Narrow BB width (compression) → score rises when width increases
        bb_width = fv.bb_width
        bb_compression_score = _sigmoid(-bb_width, center=-0.03, steepness=60.0)
        bb_expansion_score = _sigmoid(bb_width, center=0.04, steepness=40.0)
        # Transition = was compressed, now expanding
        squeeze_then_expand = min(bb_compression_score * 0.5 + bb_expansion_score * 0.5, 1.0)
        signals.append(squeeze_then_expand * 0.25)

        # 3. EMA spread widening
        ema_spread = abs(fv.ema_21_vs_55)
        spread_score = _sigmoid(ema_spread, center=0.005, steepness=200.0)
        signals.append(spread_score * 0.20)

        # 4. Volume expansion (above normal)
        vol_score = _sigmoid(fv.volume_ratio, center=1.3, steepness=2.0)
        signals.append(vol_score * 0.10)

        # 5. Regime probability momentum (trend prob rising)
        if len(self._prob_history) >= 3:
            recent = [p.trend for p in self._prob_history[-5:]]
            if len(recent) >= 2:
                delta = recent[-1] - recent[0]
                momentum_score = _sigmoid(delta, center=0.05, steepness=15.0)
                signals.append(momentum_score * 0.15)

        total = sum(signals)
        return round(min(max(total, 0.0), 1.0), 4)

    # ─── PAF State Machine ───────────────────────────────────────

    def _update_paf_states(
        self,
        probs: RegimeProbabilities,
        transition_score: float,
    ) -> None:
        """Update Probe → Arm → Fire state for each engine.

        TITAN gets special transition boost handling.
        Other engines follow standard regime-affinity path.
        """
        for engine in ALL_ENGINES:
            current_state = self._paf_states[engine]
            affinity = ENGINE_AFFINITY.get(engine, {})

            # Check if engine's best regime is gaining probability
            best_regime = max(affinity, key=lambda r: affinity.get(r, 0.0))
            regime_dict = probs.as_dict()
            best_regime_prob = regime_dict.get(best_regime, 0.0)

            # TITAN has special transition-based promotion
            if engine == ENGINE_TITAN:
                engine_favorable = transition_score > 0.4 or best_regime_prob > 0.40
            else:
                engine_favorable = best_regime_prob > 0.35

            if engine_favorable:
                self._precondition_counters[engine] += 1
            else:
                self._precondition_counters[engine] = max(0, self._precondition_counters[engine] - 1)

            precond_count = self._precondition_counters[engine]
            self._paf_cycles[engine] += 1

            if current_state == "PROBE":
                if precond_count >= PAF_ARM_PRECONDITIONS_NEEDED:
                    self._paf_states[engine] = "ARM"
                    self._paf_cycles[engine] = 0
                    _LOG.debug("PAF %s: PROBE → ARM (precond=%d)", engine, precond_count)

            elif current_state == "ARM":
                # TITAN fires on transition score, others fire on regime dominance
                if engine == ENGINE_TITAN:
                    fire_condition = transition_score > PAF_FIRE_MOMENTUM_THRESHOLD
                else:
                    fire_condition = best_regime_prob > 0.55

                if fire_condition and self._paf_cycles[engine] >= 2:
                    self._paf_states[engine] = "FIRE"
                    self._paf_cycles[engine] = 0
                    _LOG.debug("PAF %s: ARM → FIRE", engine)

                # Demote back to PROBE if conditions deteriorate
                if not engine_favorable and self._paf_cycles[engine] >= 3:
                    self._paf_states[engine] = "PROBE"
                    self._paf_cycles[engine] = 0
                    self._precondition_counters[engine] = 0
                    _LOG.debug("PAF %s: ARM → PROBE (conditions lost)", engine)

            elif current_state == "FIRE":
                # Only demote after cooldown
                if self._paf_cycles[engine] >= PAF_COOLDOWN_CYCLES:
                    if not engine_favorable:
                        self._paf_states[engine] = "ARM"
                        self._paf_cycles[engine] = 0
                        _LOG.debug("PAF %s: FIRE → ARM (cooldown expired)", engine)

    # ─── Engine Weight Computation ───────────────────────────────

    def _compute_engine_weights(
        self,
        probs: RegimeProbabilities,
        transition_score: float,
    ) -> tuple[dict[str, float], dict[str, EngineWeightEntry]]:
        """Compute normalized engine weight vector."""

        regime_dict = probs.as_dict()
        raw_weights: dict[str, float] = {}
        details: dict[str, EngineWeightEntry] = {}

        paf_multipliers = {"PROBE": 0.3, "ARM": 0.7, "FIRE": 1.0}

        for engine in ALL_ENGINES:
            affinity = ENGINE_AFFINITY.get(engine, {})
            paf = self._paf_states.get(engine, "PROBE")
            paf_mult = paf_multipliers.get(paf, 0.3)

            # Compatibility score: weighted sum across all regimes
            compat_score = sum(
                regime_dict.get(regime, 0.0) * affinity.get(regime, 0.0)
                for regime in regime_dict
            )

            # Transition boost for TITAN only
            transition_boost = 0.0
            if engine == ENGINE_TITAN and transition_score > 0.4:
                transition_boost = transition_score * 0.3

            # Raw weight
            raw = (compat_score + transition_boost) * paf_mult
            raw_weights[engine] = raw

            details[engine] = EngineWeightEntry(
                engine=engine,
                compat_score=round(compat_score, 4),
                paf_state=paf,
                transition_boost=round(transition_boost, 4),
                raw_weight=round(raw, 4),
                final_weight=0.0,  # filled after normalization
            )

        # Apply probe floor + normalize
        normalized = self._normalize_weights(raw_weights, probs.crisis)
        final_details: dict[str, EngineWeightEntry] = {}
        for engine in ALL_ENGINES:
            d = details[engine]
            final_details[engine] = EngineWeightEntry(
                engine=d.engine,
                compat_score=d.compat_score,
                paf_state=d.paf_state,
                transition_boost=d.transition_boost,
                raw_weight=d.raw_weight,
                final_weight=normalized[engine],
            )

        return normalized, final_details

    def _normalize_weights(
        self,
        raw_weights: dict[str, float],
        crisis_prob: float,
    ) -> dict[str, float]:
        """Normalize weights with probe floor enforcement.

        In crisis (crisis_prob > CRISIS_CLAMP_THRESHOLD), all weights go to zero.
        Otherwise, every engine keeps at least probe_floor.
        """
        if crisis_prob > CRISIS_CLAMP_THRESHOLD:
            # Crisis clamp: all weights zero
            return {e: 0.0 for e in raw_weights}

        # Apply floor
        floored: dict[str, float] = {}
        for engine, w in raw_weights.items():
            floored[engine] = max(w, self.probe_floor)

        total = sum(floored.values())
        if total < 1e-12:
            n = len(floored)
            return {e: 1.0 / n for e in floored}

        return {e: round(w / total, 4) for e, w in floored.items()}

    # ─── Risk Posture ────────────────────────────────────────────

    def _compute_risk_posture(
        self,
        *,
        equity: float,
        drawdown_pct: float,
        daily_pnl_pct: float,
        crisis_prob: float,
        trades_today: int,
    ) -> RiskPosture:
        """Compute dynamic risk posture based on capital and drawdown."""

        # Crisis override
        if crisis_prob > CRISIS_CLAMP_THRESHOLD:
            return RiskPosture(
                risk_multiplier=0.0,
                max_trades=0,
                daily_loss_limit=-0.01,
                allow_new_entries=False,
                growth_mode="SURVIVAL",
                reason=f"crisis_prob={crisis_prob:.2f}>threshold",
            )

        # Drawdown-based scaling
        if drawdown_pct > 0.06:
            return RiskPosture(
                risk_multiplier=0.0,
                max_trades=0,
                daily_loss_limit=-0.01,
                allow_new_entries=False,
                growth_mode="SURVIVAL",
                reason=f"drawdown={drawdown_pct:.1%}>6%_halt",
            )

        if drawdown_pct > 0.04:
            return RiskPosture(
                risk_multiplier=0.25,
                max_trades=1,
                daily_loss_limit=-0.015,
                allow_new_entries=True,
                growth_mode="DEFENSIVE",
                reason=f"drawdown={drawdown_pct:.1%}_defensive",
            )

        if drawdown_pct > 0.02:
            return RiskPosture(
                risk_multiplier=0.50,
                max_trades=1,
                daily_loss_limit=-0.02,
                allow_new_entries=True,
                growth_mode="NORMAL",
                reason=f"drawdown={drawdown_pct:.1%}_cautious",
            )

        # Daily loss limit check
        if daily_pnl_pct < -0.025:
            return RiskPosture(
                risk_multiplier=0.0,
                max_trades=0,
                daily_loss_limit=-0.025,
                allow_new_entries=False,
                growth_mode="DEFENSIVE",
                reason=f"daily_loss={daily_pnl_pct:.1%}_exceeded",
            )

        # Small capital growth mode
        if equity < GROWTH_MODE_EQUITY_CEILING:
            max_t = 1
            risk_mult = 0.75
            mode = "AGGRESSIVE"
            reason = f"small_capital=${equity:.0f}<${GROWTH_MODE_EQUITY_CEILING:.0f}"

            # Tighten further if very small
            if equity < 200.0:
                max_t = 1
                risk_mult = 0.50
                mode = "DEFENSIVE"
                reason = f"micro_capital=${equity:.0f}"

            return RiskPosture(
                risk_multiplier=risk_mult,
                max_trades=max_t,
                daily_loss_limit=-0.025,
                allow_new_entries=trades_today < max_t,
                growth_mode=mode,
                reason=reason,
            )

        # Normal mode (equity >= ceiling, minimal drawdown)
        return RiskPosture(
            risk_multiplier=1.0,
            max_trades=3,
            daily_loss_limit=-0.025,
            allow_new_entries=trades_today < 3,
            growth_mode="NORMAL",
            reason="standard_mode",
        )

    # ─── Engine Selection ────────────────────────────────────────

    def _select_best_engine(
        self,
        *,
        candidate_signals: dict[str, Optional[EngineSignal]],
        engine_weights: dict[str, float],
        risk_posture: RiskPosture,
    ) -> tuple[str, float]:
        """Select the best engine from candidates using ORION weights.

        Returns (engine_name, weight). If no valid signals, returns ("NONE", 0.0).
        """
        if not risk_posture.allow_new_entries:
            return ("NONE", 0.0)

        scored: list[tuple[str, float, EngineSignal]] = []
        for engine_name, signal in candidate_signals.items():
            if signal is None:
                continue
            weight = engine_weights.get(engine_name, 0.0)
            if weight <= 0.0:
                continue
            # Composite score: weight * signal confidence
            composite = weight * signal.confidence
            scored.append((engine_name, composite, signal))

        if not scored:
            return ("NONE", 0.0)

        # Pick highest composite score
        scored.sort(key=lambda x: x[1], reverse=True)
        best_name, best_score, _ = scored[0]
        return (best_name, engine_weights.get(best_name, 0.0))

    # ─── State Reset (for testing) ───────────────────────────────

    def reset(self) -> None:
        """Reset all internal state."""
        self._paf_states = {e: "PROBE" for e in ALL_ENGINES}
        self._paf_cycles = {e: 0 for e in ALL_ENGINES}
        self._prob_history = []
        self._precondition_counters = {e: 0 for e in ALL_ENGINES}
        self._cycle = 0
