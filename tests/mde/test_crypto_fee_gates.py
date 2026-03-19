"""Tests for Gate 7.5: crypto fee-adjusted expectancy filter."""

from __future__ import annotations

import pytest

from tests.unit._v2_helpers import make_feature_vector, make_regime_state
from src.core.types import EngineSignal
from src.mde.gates import GateInput, evaluate_gates


def _make_signal(
    confidence: float = 0.70,
    expected_return: float = 0.03,
    stop_distance: float = 0.015,
    engine: str = "POSEIDON",
    bias: str = "long",
) -> EngineSignal:
    return EngineSignal(
        engine=engine,
        sub_strategy="test",
        asset_class="crypto",
        symbol="BTCUSDT",
        bias=bias,
        confidence=confidence,
        expected_return=expected_return,
        stop_distance=stop_distance,
        atr=200.0,
    )


class TestGate75CryptoFee:
    """Gate 7.5: crypto fee-adjusted expectancy filter."""

    def test_positive_edge_passes(self):
        """High RR, high confidence -> positive edge -> passes."""
        sig = _make_signal(confidence=0.70, expected_return=0.04, stop_distance=0.015)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=3.0,
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.01,
        )
        result = evaluate_gates(inp)
        assert result.approved is True

    def test_negative_edge_rejected(self):
        """Marginal trade with tiny SL -> fee burden dominates -> negative edge."""
        # SL=0.001, TP=0.002, RR=2.0, conf=0.55
        # fee_cost = 2*0.0003/0.001 = 0.6
        # edge = 2.0*0.55 - 0.45 - 0.6 = 1.1 - 0.45 - 0.6 = 0.05 > 0
        # Need higher fee or smaller SL. Use fee=50 bps:
        # fee_cost = 2*0.005/0.001 = 10.0 -> edge = 1.1 - 0.45 - 10.0 = -9.35
        sig = _make_signal(confidence=0.55, expected_return=0.002, stop_distance=0.001)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=50.0,
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.001,
        )
        result = evaluate_gates(inp)
        assert result.approved is False
        assert "crypto_fee_edge_negative" in result.reason

    def test_min_rr_fail(self):
        """RR passes standard Gate 7 (>=1.5) but fails crypto_min_rr (>=2.0)."""
        # RR = 0.025/0.015 = 1.67 -> passes Gate 7 (1.5) but fails crypto (2.0)
        # edge = 1.67*0.70 - 0.30 - 2*0.0003/0.015 = 1.169 - 0.30 - 0.04 = 0.829 > 0
        sig = _make_signal(confidence=0.70, expected_return=0.025, stop_distance=0.015)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=3.0,
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.01,
        )
        result = evaluate_gates(inp)
        assert result.approved is False
        assert "crypto_min_rr_fail" in result.reason

    def test_min_tp_fail(self):
        """TP below crypto_min_tp_pct -> rejected."""
        # RR = 0.005/0.002 = 2.5 (passes RR check)
        # edge > 0 with these numbers
        # But TP = 0.005 < 0.01 threshold
        sig = _make_signal(confidence=0.80, expected_return=0.005, stop_distance=0.002)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=3.0,
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.01,
        )
        result = evaluate_gates(inp)
        assert result.approved is False
        assert "crypto_min_tp_fail" in result.reason

    def test_non_crypto_bypasses_gate75(self):
        """When crypto_fee_mode=False, Gate 7.5 is skipped entirely."""
        # This trade would fail Gate 7.5 if crypto mode were on (low TP)
        sig = _make_signal(confidence=0.70, expected_return=0.005, stop_distance=0.002)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=False,
        )
        result = evaluate_gates(inp)
        # Without crypto mode, this passes all standard gates (RR=2.5, conf=0.70)
        assert result.approved is True

    def test_borderline_positive_edge(self):
        """Edge positive with reasonable params -> passes."""
        sig = _make_signal(confidence=0.65, expected_return=0.05, stop_distance=0.02)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=3.0,
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.01,
        )
        result = evaluate_gates(inp)
        assert result.approved is True

    def test_high_fee_kills_marginal_trade(self):
        """High fee BPS makes a marginal trade unprofitable."""
        sig = _make_signal(confidence=0.55, expected_return=0.02, stop_distance=0.008)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=50.0,  # 0.5% per side -- extreme
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.01,
        )
        result = evaluate_gates(inp)
        assert result.approved is False
        assert "crypto_" in result.reason

    def test_tiny_stop_distance_safe(self):
        """Very small stop distance should not cause division by zero."""
        sig = _make_signal(confidence=0.70, expected_return=0.03, stop_distance=0.0001)
        inp = GateInput(
            sentinel_score=0.8,
            regime=make_regime_state("RANGING"),
            rsl_level=0,
            signal=sig,
            features=make_feature_vector(),
            crypto_fee_mode=True,
            crypto_taker_fee_bps=3.0,
            crypto_min_rr=2.0,
            crypto_min_tp_pct=0.01,
        )
        result = evaluate_gates(inp)
        assert isinstance(result.approved, bool)
