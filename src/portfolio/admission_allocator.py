"""Admission Allocator — explicit slot management for the hybrid snowball.

Problem:
    The original ARGUS pipeline had no explicit slot allocator. Slot blocking
    was accidental — the max_concurrent_positions cap in BacktestSimulator would
    reject signals once full, without considering which signal was higher quality.

    This caused two failure modes:
        1. A weaker signal opened early and blocked a premium signal arriving later
        2. No reserve was kept for exceptional setups

Solution:
    Explicit slot registry that:
        - Tracks open slots by engine TYPE (trend vs MR), not just total count
        - Rejects new admissions when the relevant engine type is full
        - Maintains a reserve slot for high-score premium setups
        - Considers portfolio heat as a hard gate before slot check
        - Logs every decision for diagnostics

Design:
    SlotConfig — configurable limits per engine type
    SlotRegistry — mutable state: current open positions per type
    AdmissionAllocator — stateless evaluator (takes SlotRegistry snapshot)

Thread safety:
    Not required for backtest mode. For live use, callers should lock externally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EngineType(str, Enum):
    TREND = "TREND"   # TITAN and trend-style engines
    MR = "MR"         # POSEIDON, NAUTILUS and mean-reversion engines
    HYBRID = "HYBRID" # AEGEAN and hybrid engines (limited allocation)


class AdmissionStatus(str, Enum):
    ADMIT = "ADMIT"
    REJECT_HEAT = "REJECT_HEAT"       # portfolio heat too high
    REJECT_TREND_FULL = "REJECT_TREND_FULL"
    REJECT_MR_FULL = "REJECT_MR_FULL"
    REJECT_TOTAL_FULL = "REJECT_TOTAL_FULL"
    REJECT_SCORE = "REJECT_SCORE"     # below minimum score threshold
    REJECT_REGIME = "REJECT_REGIME"   # engine not compatible with regime


@dataclass(frozen=True)
class AdmissionResult:
    status: AdmissionStatus
    admitted: bool
    reason: str
    suggested_size_mult: float = 1.0  # admission can downsize borderline signals


@dataclass
class SlotConfig:
    """Configurable slot limits per engine type."""

    max_trend_slots: int = 2        # max simultaneous TITAN/trend positions
    max_mr_slots: int = 3           # max simultaneous POSEIDON/MR positions
    max_hybrid_slots: int = 1       # max AEGEAN-type positions
    max_total_slots: int = 4        # global hard cap
    reserve_premium_slots: int = 1  # slots reserved for high-score signals only

    # Score thresholds
    premium_score_threshold: float = 0.72  # score to use reserved slot
    min_score_for_admission: float = 0.50  # below this: always reject

    # Portfolio heat gates — calibrated to max_total_slots=4
    # heat = open_positions / max_total_slots (1/4=0.25, 2/4=0.50, 3/4=0.75)
    max_heat_for_trend: float = 0.50   # deny trend when 2+ slots occupied
    max_heat_for_mr: float = 0.75      # deny MR when 3+ slots occupied
    max_heat_global: float = 0.75      # deny all when 3+ slots occupied


@dataclass
class SlotRegistry:
    """Mutable state: tracks open slots per engine type."""

    trend_open: int = 0
    mr_open: int = 0
    hybrid_open: int = 0
    # Per-trade records: trade_id → engine_type (for close tracking)
    _open_trades: dict[str, EngineType] = field(default_factory=dict)

    @property
    def total_open(self) -> int:
        return self.trend_open + self.mr_open + self.hybrid_open

    def open_trade(self, trade_id: str, engine_type: EngineType) -> None:
        """Register a new open trade."""
        self._open_trades[trade_id] = engine_type
        if engine_type == EngineType.TREND:
            self.trend_open += 1
        elif engine_type == EngineType.MR:
            self.mr_open += 1
        elif engine_type == EngineType.HYBRID:
            self.hybrid_open += 1

    def close_trade(self, trade_id: str) -> None:
        """Deregister a closed trade."""
        engine_type = self._open_trades.pop(trade_id, None)
        if engine_type == EngineType.TREND:
            self.trend_open = max(0, self.trend_open - 1)
        elif engine_type == EngineType.MR:
            self.mr_open = max(0, self.mr_open - 1)
        elif engine_type == EngineType.HYBRID:
            self.hybrid_open = max(0, self.hybrid_open - 1)

    def reset(self) -> None:
        self.trend_open = 0
        self.mr_open = 0
        self.hybrid_open = 0
        self._open_trades.clear()


# ── Engine name → type mapping ───────────────────────────────────────────────

ENGINE_TYPE_MAP: dict[str, EngineType] = {
    "TITAN": EngineType.TREND,
    "POSEIDON": EngineType.MR,
    "NAUTILUS": EngineType.MR,
    "HYDRA": EngineType.MR,
    "AEGEAN": EngineType.HYBRID,
}


def engine_to_type(engine_name: str) -> EngineType:
    return ENGINE_TYPE_MAP.get(engine_name.upper(), EngineType.HYBRID)


# ── Admission Evaluator ──────────────────────────────────────────────────────

@dataclass
class AdmissionAllocator:
    """Stateless admission evaluator.

    Evaluates whether a new signal should be admitted given:
        - Current slot registry state
        - Signal score and engine type
        - Current portfolio heat
        - Regime compatibility

    The caller is responsible for updating the registry after admission.
    """

    config: SlotConfig = field(default_factory=SlotConfig)

    def evaluate(
        self,
        *,
        engine: str,
        signal_score: float,
        regime: str,
        pair_class: str,
        portfolio_heat: float,
        registry: SlotRegistry,
        hybrid_regime_result: Optional[object] = None,
    ) -> AdmissionResult:
        """Evaluate admission for one signal.

        Args:
            engine: engine name ("TITAN", "POSEIDON", etc.)
            signal_score: normalized signal quality (0.0–1.0)
            regime: current hybrid regime label
            pair_class: "CORE" or "MOVER"
            portfolio_heat: current portfolio heat (0.0–1.0)
            registry: current slot state
            hybrid_regime_result: optional HybridRegimeResult for routing hints
        """
        cfg = self.config
        engine_type = engine_to_type(engine)

        # ── Hard gates ──────────────────────────────────────────────────────

        # Minimum score gate
        if signal_score < cfg.min_score_for_admission:
            return AdmissionResult(
                status=AdmissionStatus.REJECT_SCORE,
                admitted=False,
                reason=f"score={signal_score:.2f}_below_min={cfg.min_score_for_admission:.2f}",
            )

        # Global heat gate
        if portfolio_heat >= cfg.max_heat_global:
            return AdmissionResult(
                status=AdmissionStatus.REJECT_HEAT,
                admitted=False,
                reason=f"global_heat={portfolio_heat:.2%}_above_{cfg.max_heat_global:.2%}",
            )

        # Engine-type heat gate
        if engine_type == EngineType.TREND and portfolio_heat >= cfg.max_heat_for_trend:
            return AdmissionResult(
                status=AdmissionStatus.REJECT_HEAT,
                admitted=False,
                reason=f"trend_heat={portfolio_heat:.2%}_above_{cfg.max_heat_for_trend:.2%}",
            )
        if engine_type == EngineType.MR and portfolio_heat >= cfg.max_heat_for_mr:
            return AdmissionResult(
                status=AdmissionStatus.REJECT_HEAT,
                admitted=False,
                reason=f"mr_heat={portfolio_heat:.2%}_above_{cfg.max_heat_for_mr:.2%}",
            )

        # ── Regime compatibility ─────────────────────────────────────────────

        regime_compat, regime_reason = self._check_regime_compatibility(
            engine_type=engine_type,
            regime=regime,
            pair_class=pair_class,
        )
        if not regime_compat:
            return AdmissionResult(
                status=AdmissionStatus.REJECT_REGIME,
                admitted=False,
                reason=regime_reason,
            )

        # ── Slot capacity ────────────────────────────────────────────────────

        # Total cap (with reserve logic)
        effective_max_total = cfg.max_total_slots
        total_used = registry.total_open

        # Reserve slot: only premium signals can use the last slot
        if total_used >= effective_max_total - cfg.reserve_premium_slots:
            if signal_score < cfg.premium_score_threshold:
                return AdmissionResult(
                    status=AdmissionStatus.REJECT_TOTAL_FULL,
                    admitted=False,
                    reason=(
                        f"total_slots={total_used}/{effective_max_total} "
                        f"score={signal_score:.2f}<premium={cfg.premium_score_threshold:.2f}"
                    ),
                )

        if total_used >= effective_max_total:
            return AdmissionResult(
                status=AdmissionStatus.REJECT_TOTAL_FULL,
                admitted=False,
                reason=f"total_slots_full={total_used}/{effective_max_total}",
            )

        # Per-type cap
        if engine_type == EngineType.TREND:
            if registry.trend_open >= cfg.max_trend_slots:
                return AdmissionResult(
                    status=AdmissionStatus.REJECT_TREND_FULL,
                    admitted=False,
                    reason=f"trend_slots_full={registry.trend_open}/{cfg.max_trend_slots}",
                )
        elif engine_type == EngineType.MR:
            if registry.mr_open >= cfg.max_mr_slots:
                return AdmissionResult(
                    status=AdmissionStatus.REJECT_MR_FULL,
                    admitted=False,
                    reason=f"mr_slots_full={registry.mr_open}/{cfg.max_mr_slots}",
                )
        elif engine_type == EngineType.HYBRID:
            if registry.hybrid_open >= cfg.max_hybrid_slots:
                return AdmissionResult(
                    status=AdmissionStatus.REJECT_TOTAL_FULL,
                    admitted=False,
                    reason=f"hybrid_slots_full={registry.hybrid_open}/{cfg.max_hybrid_slots}",
                )

        # ── Admitted ─────────────────────────────────────────────────────────

        # Borderline signals get reduced size
        size_mult = 1.0
        if signal_score < cfg.premium_score_threshold:
            # Linearly scale: 0.8x at min_score, 1.0x at premium_threshold
            score_range = cfg.premium_score_threshold - cfg.min_score_for_admission
            score_above_min = signal_score - cfg.min_score_for_admission
            size_mult = round(0.8 + 0.2 * (score_above_min / max(score_range, 0.01)), 3)

        return AdmissionResult(
            status=AdmissionStatus.ADMIT,
            admitted=True,
            reason=f"admitted_engine={engine}_score={signal_score:.2f}_heat={portfolio_heat:.2%}",
            suggested_size_mult=size_mult,
        )

    def _check_regime_compatibility(
        self,
        *,
        engine_type: EngineType,
        regime: str,
        pair_class: str,
    ) -> tuple[bool, str]:
        """Check if engine type is compatible with the current regime."""
        r = regime.upper()

        # Trend engines: suitable in trending/expansion regimes
        if engine_type == EngineType.TREND:
            compatible = r in {"BULLISH_TREND", "BEARISH_TREND", "EXPANSION", "TRENDING"}
            if not compatible:
                return False, f"trend_engine_incompatible_with_{r}"
            return True, "ok"

        # MR engines: suitable in range/volatile regimes
        if engine_type == EngineType.MR:
            compatible = r in {"RANGE_MR", "RANGING", "VOLATILE"}
            if not compatible:
                return False, f"mr_engine_incompatible_with_{r}"
            return True, "ok"

        # Hybrid: compatible with most regimes except crisis/chop
        incompatible_regimes = {"CRISIS", "CRISIS_DEFENSIVE", "CHOP"}
        if r in incompatible_regimes:
            return False, f"hybrid_engine_incompatible_with_{r}"
        return True, "ok"
