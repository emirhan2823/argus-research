from __future__ import annotations

from src.mde.liquidity_policy import resolve_liquidity_policy


def _cfg() -> dict:
    return {
        "enabled": True,
        "target_symbols": ["BTCUSDT", "ETHUSDT"],
        "policies": {
            "15m": {
                "defaults": {
                    "precision": {"min_grade": "C", "min_score": 0.50},
                    "confluence": {"min_factors": 4, "min_score": 0.55},
                    "risk": {"min_rr": 2.2, "crypto_min_rr": 2.3, "min_tp_pct": 0.012},
                    "trade_quality": {"grade_c_min_confidence": 0.85},
                },
                "engines": {
                    "HYDRA": {"mode": "off"},
                    "AEGEAN": {"mode": "strict"},
                },
            }
        },
    }


def test_resolve_liquidity_policy_off_engine() -> None:
    res = resolve_liquidity_policy(
        config=_cfg(),
        symbol="BTCUSDT",
        timeframe="15m",
        engine="HYDRA",
        side="long",
    )
    assert res is not None
    assert res.engine_allowed is False
    assert res.precision_min_grade == "C"
    assert res.min_rr == 2.2


def test_resolve_liquidity_policy_ignores_non_target_symbol() -> None:
    res = resolve_liquidity_policy(
        config=_cfg(),
        symbol="SOLUSDT",
        timeframe="15m",
        engine="HYDRA",
        side="long",
    )
    assert res is None


def test_resolve_liquidity_policy_strict_engine() -> None:
    res = resolve_liquidity_policy(
        config=_cfg(),
        symbol="ETHUSDT",
        timeframe="15m",
        engine="AEGEAN",
        side="short",
    )
    assert res is not None
    assert res.engine_allowed is True
    assert res.engine_mode == "strict"
    assert res.confluence_min_factors == 4
    assert res.tq_grade_c_min_confidence == 0.85

