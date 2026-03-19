from __future__ import annotations

from src.mde.sizing import SizingInput, compute_size


def test_sizing_formula_and_position_clamp() -> None:
    out = compute_size(
        SizingInput(
            stop_distance=0.02,
            atlas_mult=1.1,
            sentinel_mult=1.0,
            regime_conf=0.8,
            dd_mult=1.0,
            rsl_mult=1.0,
            hermes_mult=1.0,
        )
    )
    assert out.risk_per_trade >= 0.005
    assert out.risk_per_trade <= 0.03
    assert out.position_size <= 0.15


def test_sizing_min_risk_floor_applied() -> None:
    out = compute_size(
        SizingInput(
            stop_distance=0.02,
            atlas_mult=0.1,
            sentinel_mult=0.2,
            regime_conf=0.2,
            dd_mult=0.25,
            rsl_mult=0.0,
            hermes_mult=0.0,
        )
    )
    assert out.risk_per_trade == 0.005


def test_sizing_max_risk_cap_applied() -> None:
    out = compute_size(
        SizingInput(
            stop_distance=0.005,
            atlas_mult=2.0,
            sentinel_mult=2.0,
            regime_conf=1.0,
            dd_mult=1.0,
            rsl_mult=1.0,
            hermes_mult=1.0,
        )
    )
    assert out.risk_per_trade == 0.03
    assert out.position_size == 0.15


def test_sizing_applies_leverage_multiplier_slot() -> None:
    out = compute_size(
        SizingInput(
            stop_distance=0.10,
            atlas_mult=1.0,
            sentinel_mult=1.0,
            regime_conf=1.0,
            dd_mult=1.0,
            rsl_mult=1.0,
            hermes_mult=1.0,
            leverage_mult=1.5,
            base_risk_pct=0.01,
            max_risk_pct=0.03,
        )
    )
    assert out.risk_per_trade == 0.015
