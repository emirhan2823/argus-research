from __future__ import annotations

from argus_py.risk.regime_policy_packs import RegimePolicyResolver, normalize_regime


def test_normalize_regime_variants() -> None:
    assert normalize_regime("bull_trend") == "TREND"
    assert normalize_regime("HIGH_VOL_CHOP") == "CHOP"
    assert normalize_regime("low_vol_calm") == "RANGE"


def test_regime_policy_resolver_returns_pack_values() -> None:
    resolver = RegimePolicyResolver("strict")
    trend = resolver.resolve("TREND")
    chop = resolver.resolve("HIGH_VOL_CHOP")
    assert trend.risk_multiplier > chop.risk_multiplier
    assert chop.min_adx_bonus >= trend.min_adx_bonus


def test_regime_policy_resolver_falls_back_to_legacy() -> None:
    resolver = RegimePolicyResolver("missing_pack")
    p = resolver.resolve("UNKNOWN")
    assert resolver.name == "legacy"
    assert p.risk_multiplier == 1.0
