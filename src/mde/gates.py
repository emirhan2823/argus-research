"""MDE sequential gate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from src.core.constants import (
    ENGINE_TITAN,
    MIN_CONFIDENCE,
    MIN_NET_EXPECTED_RETURN,
    MIN_REWARD_RISK_RATIO,
    REGIME_CRISIS,
)
from src.core.types import EngineSignal, FeatureVector, RegimeState


@dataclass(frozen=True)
class GateResult:
    approved: bool
    gate_number: int
    action: str  # hold|close_all|proceed
    reason: str
    features_snapshot: dict[str, Any]


@dataclass(frozen=True)
class GateInput:
    sentinel_score: float
    regime: RegimeState
    rsl_level: int
    signal: Optional[EngineSignal]
    features: FeatureVector
    hermes_block_active: bool = False
    min_confidence: float = MIN_CONFIDENCE
    min_net_expected_return: float = MIN_NET_EXPECTED_RETURN
    min_reward_risk: float = MIN_REWARD_RISK_RATIO
    allow_crisis_override: bool = False
    crypto_fee_mode: bool = False
    crypto_taker_fee_bps: float = 3.0
    crypto_min_rr: float = 2.0
    crypto_min_tp_pct: float = 0.01
    crypto_titan_min_edge: float = 0.15


def gate_breakeven_r_fee(
    risk_usd: Decimal,
    notional_usd: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    threshold: Decimal = Decimal("0.30"),
    epsilon: Decimal = Decimal("0.000001"),
) -> tuple[bool, Decimal, Decimal, str]:
    """Gate 9: reject trades where fee burden exceeds 30% of risk."""
    if risk_usd <= Decimal("0"):
        raise ValueError("risk_usd must be > 0")
    if notional_usd <= Decimal("0"):
        raise ValueError("notional_usd must be > 0")
    if fee_bps < Decimal("0") or slippage_bps < Decimal("0"):
        raise ValueError("fee_bps and slippage_bps must be >= 0")

    fee_est_usd = notional_usd * (fee_bps + slippage_bps) / Decimal("10000")
    fee_risk_ratio = fee_est_usd / risk_usd
    passed = fee_risk_ratio <= (threshold + epsilon)
    if passed:
        reason = "gate9_pass"
    else:
        reason = (
            "gate9_fail "
            f"fee_est_usd={fee_est_usd} risk_usd={risk_usd} "
            f"fee_risk_ratio={fee_risk_ratio} threshold={threshold}"
        )
    return passed, fee_est_usd, fee_risk_ratio, reason


def evaluate_gates(inp: GateInput) -> GateResult:
    snapshot = {
        "symbol": inp.features.symbol,
        "asset_class": inp.features.asset_class,
        "regime": inp.regime.regime,
        "sentinel_score": inp.sentinel_score,
        "rsl_level": inp.rsl_level,
    }

    # Gate 0: sentinel hard block
    if inp.sentinel_score < 0.4:
        return GateResult(False, 0, "hold", "sentinel_below_halt_threshold", snapshot)

    # Gate 1: crisis regime
    if inp.regime.regime == REGIME_CRISIS:
        if not inp.allow_crisis_override:
            return GateResult(False, 1, "close_all", "crisis_regime", snapshot)
        snapshot["crisis_override"] = True

    # Gate 2: HERMES block
    if inp.hermes_block_active:
        return GateResult(False, 2, "hold", "hermes_block_active", snapshot)

    # Gate 3: risk-switch level
    if inp.rsl_level >= 3:
        return GateResult(False, 3, "hold", "rsl_halt", snapshot)
    # RSL2 defensive mode: only TITAN allowed (lowest MaxDD, non-negative across scenarios).
    # All other engines blocked to reduce fragility during elevated risk.
    if inp.rsl_level >= 2 and (inp.signal is not None and inp.signal.engine != ENGINE_TITAN):
        return GateResult(False, 3, "hold", "rsl2_defensive_only_titan", snapshot)

    # Gate 4: signal must exist
    if inp.signal is None:
        return GateResult(False, 4, "hold", "no_signal", snapshot)

    # Gate 5: confidence
    if inp.signal.confidence < inp.min_confidence:
        return GateResult(False, 5, "hold", "confidence_below_threshold", snapshot)

    # Gate 6: net expected return
    if inp.signal.expected_return < inp.min_net_expected_return:
        return GateResult(False, 6, "hold", "net_expected_return_too_low", snapshot)

    # Gate 7: reward/risk
    reward_risk_ratio = inp.signal.expected_return / max(inp.signal.stop_distance, 1e-9)
    if reward_risk_ratio < inp.min_reward_risk:
        return GateResult(False, 7, "hold", "reward_risk_below_threshold", snapshot)

    # Gate 7.5: crypto fee-adjusted expectancy
    if inp.crypto_fee_mode and inp.signal is not None:
        sl_pct = max(inp.signal.stop_distance, 1e-9)
        tp_pct = inp.signal.expected_return
        taker_fee_pct = inp.crypto_taker_fee_bps / 10_000.0
        win_prob = max(0.0, min(1.0, inp.signal.confidence))

        fee_adjusted_edge = (
            reward_risk_ratio * win_prob
            - (1.0 - win_prob)
            - (2.0 * taker_fee_pct / sl_pct)
        )

        if fee_adjusted_edge <= 0:
            return GateResult(
                False, 7, "hold",
                f"crypto_fee_edge_negative edge={fee_adjusted_edge:.4f}", snapshot,
            )
        if reward_risk_ratio < inp.crypto_min_rr:
            return GateResult(
                False, 7, "hold",
                f"crypto_min_rr_fail rr={reward_risk_ratio:.2f}<{inp.crypto_min_rr}",
                snapshot,
            )
        if tp_pct < inp.crypto_min_tp_pct:
            return GateResult(
                False, 7, "hold",
                f"crypto_min_tp_fail tp={tp_pct:.4f}<{inp.crypto_min_tp_pct}",
                snapshot,
            )

        # TITAN-specific: higher edge threshold for trend trades (unlimited hold)
        if inp.signal.engine == "TITAN" and fee_adjusted_edge < inp.crypto_titan_min_edge:
            return GateResult(
                False, 7, "hold",
                f"titan_edge_insufficient edge={fee_adjusted_edge:.4f}<{inp.crypto_titan_min_edge}",
                snapshot,
            )

    # Gate 9 (Breakeven-R fee burden) is enforced in pre_trade.py via
    # compute_validated_size(). It requires sizing output (notional_usd)
    # which is only available after the sizing step. See GR-12 in
    # PROJECT_STATE_MEMORY_MAP.md. The gate_breakeven_r_fee() utility
    # function above remains available for standalone use.

    return GateResult(True, 8, "proceed", "all_gates_passed", snapshot)
