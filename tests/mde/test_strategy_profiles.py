from __future__ import annotations

from src.mde.strategy_profiles import (
    classify_setup,
    classify_vol_bucket,
    resolve_strategy_profile,
)


def test_classify_setup_detects_pump_from_flow_and_move() -> None:
    setup = classify_setup(
        engine="AEGEAN",
        regime="VOLATILE",
        sub_strategy=None,
        volume_ratio=2.5,
        roc_10=0.07,
    )
    assert setup == "pump"


def test_classify_vol_bucket_from_percentile_and_realized_vol() -> None:
    assert classify_vol_bucket(atr_pctl=0.20, realized_vol_20d=0.05) == "low_vol"
    assert classify_vol_bucket(atr_pctl=0.90, realized_vol_20d=0.05) == "high_vol"
    assert classify_vol_bucket(atr_pctl=0.55, realized_vol_20d=0.04) == "normal_vol"


def test_resolve_strategy_profile_returns_none_when_disabled() -> None:
    out = resolve_strategy_profile(
        config={"enabled": False},
        engine="TITAN",
        regime="TRENDING",
        side="long",
        sub_strategy="CONTINUATION",
        atr_pctl=0.6,
        realized_vol_20d=0.05,
        volume_ratio=1.2,
        roc_10=0.01,
    )
    assert out is None


def test_resolve_strategy_profile_trend_long_high_vol() -> None:
    cfg = {
        "enabled": True,
        "defaults": {"tp_mult": 1.0, "sl_mult": 1.0},
        "profiles": {
            "trend": {
                "long": {
                    "high_vol": {
                        "min_confidence": 0.63,
                        "min_rr": 2.2,
                        "crypto_min_rr": 2.3,
                        "confluence_min_factors": 4,
                        "confluence_min_score": 0.56,
                        "tp_mult": 1.25,
                        "sl_mult": 1.08,
                    }
                }
            }
        },
    }
    out = resolve_strategy_profile(
        config=cfg,
        engine="TITAN",
        regime="TRENDING",
        side="long",
        sub_strategy="CONTINUATION",
        atr_pctl=0.82,
        realized_vol_20d=0.09,
        volume_ratio=1.4,
        roc_10=0.02,
    )
    assert out is not None
    assert out.profile_name == "trend.long.high_vol"
    assert out.min_confidence == 0.63
    assert out.min_rr == 2.2
    assert out.crypto_min_rr == 2.3
    assert out.confluence_min_factors == 4
    assert out.confluence_min_score == 0.56
    assert out.tp_mult == 1.25
    assert out.sl_mult == 1.08

