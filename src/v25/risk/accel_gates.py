"""Acceleration activation safety gates."""

from __future__ import annotations

from src.v25.config.loader import V25Config


def evaluate_accel_gates(
    sub_regime: str,
    alignment_score: float,
    sqs_score: float,
    kill_switch_level: int,
    rolling_vol_24h: float,
    current_drawdown_pct: float,
    recent_slippage_err: float | None,
    filled_order_count: int,
    config: V25Config,
) -> tuple[bool, str]:
    """Evaluate accel gates in strict fail-fast order.

    Ordered gates: S1 -> S2 -> S3 -> R1 -> A -> B -> C -> D.
    Gate C may return NEUTRAL when data is insufficient.
    """

    accel = config.engines.dual_speed.accel

    # S1
    if sub_regime != accel.required_sub_regime:
        return False, (
            f"S1 failed: required_sub_regime={accel.required_sub_regime}, "
            f"got={sub_regime}"
        )

    # S2
    if float(alignment_score) < float(accel.min_alignment):
        return False, (
            f"S2 failed: alignment_score {alignment_score} < min_alignment "
            f"{accel.min_alignment}"
        )

    # S3
    if float(sqs_score) < float(accel.min_sqs):
        return False, f"S3 failed: sqs_score {sqs_score} < min_sqs {accel.min_sqs}"

    # R1
    if int(kill_switch_level) != int(accel.required_kill_switch):
        return False, (
            f"R1 failed: kill_switch_level {kill_switch_level} != "
            f"required_kill_switch {accel.required_kill_switch}"
        )

    # A
    if float(rolling_vol_24h) > float(accel.max_rolling_vol):
        return False, (
            f"A failed: rolling_vol_24h {rolling_vol_24h} > "
            f"max_rolling_vol {accel.max_rolling_vol}"
        )

    # B
    if float(current_drawdown_pct) > float(accel.max_dd_for_activation):
        return False, (
            f"B failed: current_drawdown_pct {current_drawdown_pct} > "
            f"max_dd_for_activation {accel.max_dd_for_activation}"
        )

    # C (NEUTRAL or PASS/FAIL)
    gate_c_neutral = False
    if int(filled_order_count) < int(accel.slippage_lookback_orders) or recent_slippage_err is None:
        gate_c_neutral = True
    elif float(recent_slippage_err) > float(accel.max_slippage_err):
        return False, (
            f"C failed: recent_slippage_err {recent_slippage_err} > "
            f"max_slippage_err {accel.max_slippage_err}"
        )

    # D
    if int(filled_order_count) < int(accel.min_orders_for_accel):
        return False, (
            f"D failed: insufficient order history ({filled_order_count} < "
            f"{accel.min_orders_for_accel})"
        )

    if gate_c_neutral:
        return True, "all non-NEUTRAL gates passed (Gate C NEUTRAL)"
    return True, "all 9 gates passed"

