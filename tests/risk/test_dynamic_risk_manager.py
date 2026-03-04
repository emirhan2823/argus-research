from __future__ import annotations

import pytest

from src.risk.dynamic_risk_manager import (
    RiskConfig,
    TrailingRules,
    apply_trailing_stop,
    base_profile_for_asset,
    compute_side_aware_leverage,
    compute_risk_decision,
)


def _base_kwargs() -> dict[str, object]:
    return {
        "asset": "BTCUSDT",
        "asset_class": "crypto",
        "regime": "RANGING",
        "regime_probability_vector": None,
        "engine_name": "Titan",
        "engine_confidence": 1.0,
        "atr_pct": 0.02,
        "adx": 25.0,
        "rolling_drawdown_pct": 0.0,
        "account_equity": 10_000.0,
        "risk_mode": "normal",
        "entry_price": 100.0,
        "side": "long",
        "config": RiskConfig(),
    }


def test_base_profile_btc() -> None:
    lev, risk = base_profile_for_asset("BTCUSDT")
    assert lev == pytest.approx(2.0)
    assert risk == pytest.approx(0.02)


def test_base_profile_eth() -> None:
    lev, risk = base_profile_for_asset("eth-usdt")
    assert lev == pytest.approx(2.0)
    assert risk == pytest.approx(0.02)


def test_base_profile_sol_xrp() -> None:
    lev_sol, risk_sol = base_profile_for_asset("SOLUSDT")
    lev_xrp, risk_xrp = base_profile_for_asset("xrp/usdt")
    assert lev_sol == pytest.approx(1.5)
    assert risk_sol == pytest.approx(0.015)
    assert lev_xrp == pytest.approx(1.5)
    assert risk_xrp == pytest.approx(0.015)


def test_base_profile_other() -> None:
    lev, risk = base_profile_for_asset("AAPL")
    assert lev == pytest.approx(1.0)
    assert risk == pytest.approx(0.01)


def test_regime_multiplier_trending_increases_risk() -> None:
    kw = _base_kwargs()
    baseline = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["regime"] = "TRENDING"
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.leverage > baseline.leverage
    assert out.sl_price < 100.0
    assert out.tp_price > 100.0


def test_regime_probability_vector_weighted() -> None:
    kw = _base_kwargs()
    kw["regime"] = "TRENDING"
    kw["regime_probability_vector"] = {"TRENDING": 0.5, "RANGING": 0.5}
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.leverage > 0.0


def test_volatility_dampener_high_atr_reduces_leverage() -> None:
    kw = _base_kwargs()
    kw["regime"] = "TRENDING"
    kw["atr_pct"] = 0.02
    normal = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["atr_pct"] = 0.04
    high_vol = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert high_vol.leverage < normal.leverage


def test_volatility_low_atr_increases_leverage() -> None:
    kw = _base_kwargs()
    kw["regime"] = "RANGING"
    kw["atr_pct"] = 0.02
    normal = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["atr_pct"] = 0.005
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.leverage > normal.leverage


def test_confidence_clamped_min_0_5() -> None:
    kw = _base_kwargs()
    kw["engine_confidence"] = 1.0
    high = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["engine_confidence"] = 0.1
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.leverage < high.leverage


def test_drawdown_reduction_10pct_and_20pct() -> None:
    kw = _base_kwargs()
    kw["rolling_drawdown_pct"] = 0.11
    dd10 = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["rolling_drawdown_pct"] = 0.21
    dd20 = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert dd20.position_size_usd < dd10.position_size_usd


def test_growth_mode_increases_risk_but_is_capped() -> None:
    kw = _base_kwargs()
    kw["regime"] = "TRENDING"
    kw["risk_mode"] = "normal"
    normal = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["risk_mode"] = "growth"
    growth = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert growth.leverage >= normal.leverage
    assert growth.leverage <= 8.0


def test_leverage_never_exceeds_config_cap() -> None:
    kw = _base_kwargs()
    kw["risk_mode"] = "growth"
    kw["config"] = RiskConfig(leverage_cap_long=3.0, leverage_cap_short=2.5)
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.leverage <= 3.0


def test_tp_sl_long_calculations() -> None:
    kw = _base_kwargs()
    kw["atr_pct"] = 0.02  # ATR = 2.0 at entry 100
    kw["config"] = RiskConfig(atr_multiplier=1.5, rr_ratio=2.0)
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    # RANGING regime applies a 1.10 stop multiplier.
    assert out.sl_price == pytest.approx(96.7)
    assert out.tp_price == pytest.approx(106.6)


def test_tp_sl_short_calculations() -> None:
    kw = _base_kwargs()
    kw["side"] = "short"
    kw["atr_pct"] = 0.02
    kw["config"] = RiskConfig(atr_multiplier=1.5, rr_ratio=2.0)
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    # Short side uses a slightly wider RANGING stop multiplier.
    assert out.sl_price == pytest.approx(103.45)
    assert out.tp_price == pytest.approx(93.1)


def test_side_specific_tp_sl_params_apply() -> None:
    kw = _base_kwargs()
    kw["side"] = "short"
    kw["atr_pct"] = 0.02
    kw["config"] = RiskConfig(
        atr_multiplier=1.5,
        rr_ratio=2.0,
        atr_multiplier_short=2.0,
        rr_ratio_short=3.0,
    )
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    # ATR=2, short sl distance=2*2.0*1.15=4.6 -> SL=104.6, TP=86.2
    assert out.sl_price == pytest.approx(104.6)
    assert out.tp_price == pytest.approx(86.2)


def test_compute_side_aware_leverage_short_constraints() -> None:
    lev = compute_side_aware_leverage(
        base_leverage=3.0,
        base_leverage_reference=2.0,
        score=90.0,
        volatility=0.01,
        drawdown_pct=0.0,
        side="short",
        regime="TRENDING",
        leverage_cap_long=5.0,
        leverage_cap_short=3.0,
    )
    assert lev <= 1.7  # base_leverage_reference * 0.85


def test_compute_side_aware_leverage_crisis_forces_one() -> None:
    lev = compute_side_aware_leverage(
        base_leverage=3.0,
        base_leverage_reference=2.0,
        score=100.0,
        volatility=0.0,
        drawdown_pct=0.0,
        side="long",
        regime="CRISIS",
        leverage_cap_long=5.0,
        leverage_cap_short=3.0,
    )
    assert lev == pytest.approx(1.0)


def test_dynamic_leverage_symmetry_long_short() -> None:
    common = {
        "base_leverage": 2.5,
        "base_leverage_reference": 2.0,
        "score": 80.0,
        "volatility": 0.02,
        "drawdown_pct": 0.05,
        "regime": "TRENDING",
        "leverage_cap_long": 5.0,
        "leverage_cap_short": 3.0,
    }
    long_lev = compute_side_aware_leverage(side="long", **common)
    short_lev = compute_side_aware_leverage(side="short", **common)
    assert short_lev <= long_lev
    assert long_lev >= 1.0
    assert short_lev >= 1.0


def test_crisis_force_1x() -> None:
    kw = _base_kwargs()
    kw["regime"] = "CRISIS"
    kw["side"] = "short"
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.leverage == pytest.approx(1.0)


def test_volatility_penalty() -> None:
    kw = _base_kwargs()
    kw["regime"] = "TRENDING"
    kw["atr_pct"] = 0.015
    lo = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["atr_pct"] = 0.05
    hi = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert hi.leverage < lo.leverage


def test_drawdown_penalty() -> None:
    kw = _base_kwargs()
    kw["rolling_drawdown_pct"] = 0.02
    base = compute_risk_decision(**kw)  # type: ignore[arg-type]
    kw["rolling_drawdown_pct"] = 0.22
    stressed = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert stressed.leverage < base.leverage


def test_position_size_respects_leverage_cap() -> None:
    kw = _base_kwargs()
    kw["account_equity"] = 1_000.0
    kw["atr_pct"] = 0.0  # triggers min stop distance, but also low-vol boost for leverage
    out = compute_risk_decision(**kw)  # type: ignore[arg-type]
    assert out.position_size_usd <= (out.leverage * 1_000.0 + 1e-9)


def test_risk_score_in_range() -> None:
    out = compute_risk_decision(**_base_kwargs())  # type: ignore[arg-type]
    assert 0.0 <= out.risk_score <= 1.0


def test_trailing_rule_activates_at_correct_r_levels() -> None:
    rules = TrailingRules()

    # Long: entry 100, initial SL 97 => R=3
    sl0 = 97.0
    sl1 = apply_trailing_stop(
        side="long",
        entry_price=100.0,
        initial_sl_price=sl0,
        current_sl_price=sl0,
        current_price=103.0,
        rules=rules,
    )
    assert sl1 == pytest.approx(100.0)
    sl2 = apply_trailing_stop(
        side="long",
        entry_price=100.0,
        initial_sl_price=sl0,
        current_sl_price=sl1,
        current_price=106.0,
        rules=rules,
    )
    assert sl2 == pytest.approx(103.0)

    # Short: entry 100, initial SL 103 => R=3
    sl0s = 103.0
    sl1s = apply_trailing_stop(
        side="short",
        entry_price=100.0,
        initial_sl_price=sl0s,
        current_sl_price=sl0s,
        current_price=97.0,
        rules=rules,
    )
    assert sl1s == pytest.approx(100.0)
    sl2s = apply_trailing_stop(
        side="short",
        entry_price=100.0,
        initial_sl_price=sl0s,
        current_sl_price=sl1s,
        current_price=94.0,
        rules=rules,
    )
    assert sl2s == pytest.approx(97.0)
