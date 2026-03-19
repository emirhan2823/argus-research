"""Tests for the Consortium scoring system (profiles, consortium, aggregator)."""
from __future__ import annotations

from src.engines.poseidon.profiles import (
    ALL_CONSORTIUMS,
    CONSORTIUM_MR,
    CONSORTIUM_STRUCTURE,
    CONSORTIUM_TREND,
    CONSORTIUM_VOLUME,
    Condition,
    IndicatorProfile,
    build_default_profiles,
)
from src.engines.poseidon.consortium import (
    ConsortiumResult,
    IndicatorVote,
    compute_consortium_score,
)
from src.engines.poseidon.aggregator import (
    MasterSignal,
    compute_master_signal,
)


# ── Condition tests ─────────────────────────────────────────────


def test_condition_lt() -> None:
    c = Condition("adx_14", "lt", 25.0, 1.5)
    assert c.evaluate({"adx_14": 20.0}, "RANGING")
    assert not c.evaluate({"adx_14": 30.0}, "RANGING")


def test_condition_gt() -> None:
    c = Condition("volume_ratio", "gt", 1.3, 1.6)
    assert c.evaluate({"volume_ratio": 1.5}, "RANGING")
    assert not c.evaluate({"volume_ratio": 0.8}, "RANGING")


def test_condition_eq_regime() -> None:
    c = Condition("regime", "eq", "RANGING", 1.3)
    assert c.evaluate({}, "RANGING")
    assert not c.evaluate({}, "TRENDING")


def test_condition_neq() -> None:
    c = Condition("regime", "neq", "CRISIS", 1.2)
    assert c.evaluate({}, "RANGING")
    assert not c.evaluate({}, "CRISIS")


def test_condition_between() -> None:
    c = Condition("cmf_20", "between", (-0.05, 0.05), 0.6)
    assert c.evaluate({"cmf_20": 0.0}, "RANGING")
    assert not c.evaluate({"cmf_20": 0.15}, "RANGING")


def test_condition_missing_feature() -> None:
    c = Condition("nonexistent", "lt", 10.0, 1.5)
    assert not c.evaluate({}, "RANGING")


# ── IndicatorProfile tests ───────────────────────────────────────


def test_profile_effective_weight_no_conditions() -> None:
    p = IndicatorProfile(name="test", consortium="mr", base_weight=2.0)
    assert p.effective_weight({}, "RANGING") == 2.0


def test_profile_optimal_boost() -> None:
    p = IndicatorProfile(
        name="rsi_14", consortium="mr", base_weight=1.5,
        optimal_conditions=[Condition("adx_14", "lt", 25.0, 1.8)],
    )
    # ADX = 20 → boost 1.8x
    w = p.effective_weight({"adx_14": 20.0}, "RANGING")
    assert abs(w - 1.5 * 1.8) < 0.01

    # ADX = 30 → no boost
    w2 = p.effective_weight({"adx_14": 30.0}, "RANGING")
    assert abs(w2 - 1.5) < 0.01


def test_profile_adverse_penalty() -> None:
    p = IndicatorProfile(
        name="rsi_14", consortium="mr", base_weight=1.5,
        adverse_conditions=[Condition("adx_14", "gt", 40.0, 0.6)],
    )
    # ADX = 50 → penalty 0.6x
    w = p.effective_weight({"adx_14": 50.0}, "RANGING")
    assert abs(w - 1.5 * 0.6) < 0.01


def test_profile_both_conditions() -> None:
    """When both optimal and adverse conditions apply, both multiply."""
    p = IndicatorProfile(
        name="test", consortium="mr", base_weight=2.0,
        optimal_conditions=[Condition("regime", "eq", "RANGING", 1.5)],
        adverse_conditions=[Condition("adx_14", "gt", 40.0, 0.6)],
    )
    # RANGING + ADX=50 → 2.0 * 1.5 * 0.6 = 1.8
    w = p.effective_weight({"adx_14": 50.0}, "RANGING")
    assert abs(w - 2.0 * 1.5 * 0.6) < 0.01


# ── Default profiles tests ──────────────────────────────────────


def test_default_profiles_complete() -> None:
    """All expected indicators have profiles."""
    profiles = build_default_profiles()
    expected = {
        "rsi_14", "cci_20", "willr_14", "harsi", "wave_trend",
        "cmf_20", "obv_slope", "volume_delta", "volume_ratio_ind",
        "adx_14", "ema_cross", "lr_slope", "aroon", "roc_10",
        "bb_pct_b", "vwap_dev", "entropy_st", "supertrend",
    }
    assert expected.issubset(set(profiles.keys()))


def test_default_profiles_consortiums() -> None:
    """All consortium types are covered."""
    profiles = build_default_profiles()
    covered = {p.consortium for p in profiles.values()}
    assert covered == set(ALL_CONSORTIUMS)


# ── Consortium scoring tests ─────────────────────────────────────


def test_consortium_all_long_votes() -> None:
    """All indicators vote long → score near +1.0."""
    p = IndicatorProfile(name="test", consortium="mr", base_weight=1.0)
    votes = [
        IndicatorVote(profile=p, bias="long", strength=0.8),
        IndicatorVote(profile=p, bias="long", strength=0.6),
    ]
    result = compute_consortium_score("mr", votes, {}, "RANGING")
    assert result.score > 0.5
    assert result.bias == "long"
    assert result.active_indicators == 2


def test_consortium_mixed_votes() -> None:
    """Mixed long/short votes → lower confidence."""
    p = IndicatorProfile(name="test", consortium="mr", base_weight=1.0)
    votes = [
        IndicatorVote(profile=p, bias="long", strength=0.8),
        IndicatorVote(profile=p, bias="short", strength=0.6),
    ]
    result = compute_consortium_score("mr", votes, {}, "RANGING")
    assert result.confidence < 0.5  # Mixed = low confidence


def test_consortium_neutral_votes_ignored() -> None:
    """Neutral (None bias) votes don't contribute to score."""
    p = IndicatorProfile(name="test", consortium="mr", base_weight=1.0)
    votes = [
        IndicatorVote(profile=p, bias="long", strength=0.8),
        IndicatorVote(profile=p, bias=None, strength=0.0),
    ]
    result = compute_consortium_score("mr", votes, {}, "RANGING")
    assert result.active_indicators == 1
    assert result.total_indicators == 2
    assert result.bias == "long"


def test_consortium_dynamic_weight_boost() -> None:
    """Optimal conditions boost effective weight in scoring."""
    p_boosted = IndicatorProfile(
        name="rsi", consortium="mr", base_weight=1.0,
        optimal_conditions=[Condition("regime", "eq", "RANGING", 2.0)],
    )
    p_normal = IndicatorProfile(name="cci", consortium="mr", base_weight=1.0)

    # Both vote long but RSI has 2x weight in RANGING
    votes = [
        IndicatorVote(profile=p_boosted, bias="long", strength=0.8),
        IndicatorVote(profile=p_normal, bias="short", strength=0.8),
    ]
    result_ranging = compute_consortium_score("mr", votes, {}, "RANGING")
    result_trending = compute_consortium_score("mr", votes, {}, "TRENDING")

    # In RANGING, boosted RSI dominates → score should be more positive
    assert result_ranging.score > result_trending.score


# ── Master aggregator tests ─────────────────────────────────────


def test_master_signal_all_agree_long() -> None:
    """All consortiums agree long → high confidence with agreement bonus."""
    results = {
        "mr": ConsortiumResult("mr", 0.8, 0.8, "long", 3, 5),
        "volume": ConsortiumResult("volume", 0.6, 0.6, "long", 2, 3),
        "trend": ConsortiumResult("trend", -0.5, 0.5, "short", 2, 3),  # inverted for MR
        "structure": ConsortiumResult("structure", 0.7, 0.7, "long", 2, 3),
    }
    master = compute_master_signal(results, "RANGING")
    assert master.bias == "long"
    assert master.agreement_count >= 3
    assert master.agreement_bonus > 0


def test_master_signal_disagreement_penalty() -> None:
    """Volume disagreeing with signal → penalty applied."""
    results = {
        "mr": ConsortiumResult("mr", 0.8, 0.8, "long", 3, 5),
        "volume": ConsortiumResult("volume", -0.6, 0.6, "short", 2, 3),  # disagrees!
        "structure": ConsortiumResult("structure", 0.5, 0.5, "long", 2, 3),
    }
    master = compute_master_signal(results, "RANGING")
    assert master.disagreement_penalty > 0
    assert master.disagreement_count >= 1


def test_master_signal_trend_inversion() -> None:
    """Trend consortium is inverted for MR: trend long → MR should short."""
    results = {
        "mr": ConsortiumResult("mr", 0.5, 0.5, "long", 3, 5),
        "trend": ConsortiumResult("trend", 0.8, 0.8, "long", 3, 3),  # trending up
    }
    master = compute_master_signal(results, "RANGING")
    # Trend inverted: "long" trend → negative contribution
    # MR "long" + inverted trend "long" (= -0.8) → net may be close to 0 or negative
    # The MR consortium has higher weight (0.40 vs 0.20) so net should still be slightly positive
    # But trend inversion should reduce overall score compared to no trend
    results_no_trend = {
        "mr": ConsortiumResult("mr", 0.5, 0.5, "long", 3, 5),
    }
    master_no_trend = compute_master_signal(results_no_trend, "RANGING")
    # With trend opposing, score should be lower
    assert master.score < master_no_trend.score


def test_master_signal_no_bias() -> None:
    """When consortiums cancel out → None bias."""
    results = {
        "mr": ConsortiumResult("mr", 0.01, 0.01, None, 0, 5),
        "volume": ConsortiumResult("volume", -0.01, 0.01, None, 0, 3),
    }
    master = compute_master_signal(results, "RANGING")
    assert master.bias is None


def test_master_signal_alpha_zero_no_correlation() -> None:
    """Alpha=0 → internal confidence doesn't affect external weight."""
    results = {
        "mr": ConsortiumResult("mr", 0.8, 0.8, "long", 3, 5),
        "volume": ConsortiumResult("volume", 0.2, 0.2, "long", 1, 3),
    }
    m0 = compute_master_signal(results, "RANGING", alpha=0.0)
    m1 = compute_master_signal(results, "RANGING", alpha=1.0)
    # With alpha=0, weights are fixed → score differs from alpha=1
    # The absolute values may be close but should differ
    assert m0.score != m1.score


def test_full_agreement_bonus_25() -> None:
    """4/4 consortiums agreeing → 25% agreement bonus."""
    results = {
        "mr": ConsortiumResult("mr", 0.8, 0.8, "long", 3, 5),
        "volume": ConsortiumResult("volume", 0.6, 0.6, "long", 2, 3),
        "trend": ConsortiumResult("trend", -0.5, 0.5, "short", 2, 3),  # inverted → agrees
        "structure": ConsortiumResult("structure", 0.7, 0.7, "long", 2, 3),
    }
    master = compute_master_signal(results, "RANGING")
    assert master.agreement_bonus == 0.25
