"""Capital Rotator unit tests."""

from __future__ import annotations

import pytest

from src.rotation.capital_rotator import AssetTrendScore, CapitalRotator, RotationDecision
from tests.unit._v2_helpers import make_feature_vector


def _fv(symbol: str, adx: float = 30.0, ema_spread: float = 0.02, vol_ratio: float = 1.5):
    return make_feature_vector(symbol=symbol, adx_14=adx, ema_21_vs_55=ema_spread, volume_ratio=vol_ratio)


class TestTrendScoreComputation:
    def test_strong_trend_high_score(self) -> None:
        rotator = CapitalRotator()
        fv = _fv("BTCUSDT", adx=50.0, ema_spread=0.04, vol_ratio=2.5)
        score = rotator.compute_trend_score(fv)
        assert score.trend_score > 0.5
        assert score.symbol == "BTCUSDT"

    def test_weak_trend_low_score(self) -> None:
        rotator = CapitalRotator()
        fv = _fv("ETHUSDT", adx=12.0, ema_spread=0.001, vol_ratio=0.6)
        score = rotator.compute_trend_score(fv)
        assert score.trend_score < 0.3

    def test_normalization_bounds(self) -> None:
        rotator = CapitalRotator()
        fv = _fv("SOLUSDT", adx=100.0, ema_spread=0.10, vol_ratio=10.0)
        score = rotator.compute_trend_score(fv)
        # All components clamped to 1.0
        assert score.adx_norm <= 1.0
        assert score.ema_slope_norm <= 1.0
        assert score.volume_score <= 1.0
        assert score.trend_score <= 1.0

    def test_structure_score_included(self) -> None:
        rotator = CapitalRotator()
        fv = _fv("BTCUSDT", adx=30.0)
        without = rotator.compute_trend_score(fv, structure_score=0.0)
        with_struct = rotator.compute_trend_score(fv, structure_score=1.0)
        assert with_struct.trend_score > without.trend_score


_DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


class TestRotation:
    def test_top_2_selection(self) -> None:
        rotator = CapitalRotator(assets=list(_DEFAULT_ASSETS), top_n=2)
        features = {
            "BTCUSDT": _fv("BTCUSDT", adx=50.0, vol_ratio=2.0),
            "ETHUSDT": _fv("ETHUSDT", adx=40.0, vol_ratio=1.5),
            "SOLUSDT": _fv("SOLUSDT", adx=15.0, vol_ratio=0.8),
        }
        decision = rotator.rotate(features)
        assert decision.allocations["BTCUSDT"] > 0
        assert decision.allocations["ETHUSDT"] > 0
        assert decision.allocations["SOLUSDT"] == 0.0
        assert decision.flat_reason is None

    def test_all_below_threshold_goes_flat(self) -> None:
        rotator = CapitalRotator(assets=list(_DEFAULT_ASSETS), min_trend_score=0.90)
        features = {
            "BTCUSDT": _fv("BTCUSDT", adx=15.0, vol_ratio=0.6),
            "ETHUSDT": _fv("ETHUSDT", adx=12.0, vol_ratio=0.5),
            "SOLUSDT": _fv("SOLUSDT", adx=10.0, vol_ratio=0.5),
        }
        decision = rotator.rotate(features)
        assert all(v == 0.0 for v in decision.allocations.values())
        assert decision.flat_reason == "all_below_threshold"

    def test_risk_off_halves_allocation(self) -> None:
        rotator = CapitalRotator(assets=list(_DEFAULT_ASSETS), top_n=2)
        features = {
            "BTCUSDT": _fv("BTCUSDT", adx=50.0, vol_ratio=2.0),
            "ETHUSDT": _fv("ETHUSDT", adx=40.0, vol_ratio=1.5),
            "SOLUSDT": _fv("SOLUSDT", adx=15.0, vol_ratio=0.8),
        }
        normal = rotator.rotate(features, risk_off=False)
        risk_off = rotator.rotate(features, risk_off=True)

        assert risk_off.risk_off is True
        assert risk_off.allocations["BTCUSDT"] == pytest.approx(
            normal.allocations["BTCUSDT"] * 0.5, abs=0.01,
        )

    def test_proportional_weight(self) -> None:
        rotator = CapitalRotator(assets=list(_DEFAULT_ASSETS), top_n=2)
        features = {
            "BTCUSDT": _fv("BTCUSDT", adx=50.0, vol_ratio=2.0),
            "ETHUSDT": _fv("ETHUSDT", adx=40.0, vol_ratio=1.5),
            "SOLUSDT": _fv("SOLUSDT", adx=15.0, vol_ratio=0.8),
        }
        decision = rotator.rotate(features)
        # BTC should get more weight than ETH
        assert decision.allocations["BTCUSDT"] > decision.allocations["ETHUSDT"]
        # Weights of top 2 should sum close to 1.0
        total = decision.allocations["BTCUSDT"] + decision.allocations["ETHUSDT"]
        assert total == pytest.approx(1.0, abs=0.01)

    def test_single_asset_gets_full_weight(self) -> None:
        rotator = CapitalRotator(assets=["BTCUSDT"], top_n=2)
        features = {"BTCUSDT": _fv("BTCUSDT", adx=50.0, vol_ratio=2.0)}
        decision = rotator.rotate(features)
        assert decision.allocations["BTCUSDT"] == pytest.approx(1.0, abs=0.01)

    def test_ranks_assigned_correctly(self) -> None:
        rotator = CapitalRotator(assets=list(_DEFAULT_ASSETS))
        features = {
            "BTCUSDT": _fv("BTCUSDT", adx=50.0, vol_ratio=2.0),
            "ETHUSDT": _fv("ETHUSDT", adx=40.0, vol_ratio=1.5),
            "SOLUSDT": _fv("SOLUSDT", adx=15.0, vol_ratio=0.8),
        }
        decision = rotator.rotate(features)
        assert decision.scores[0].rank == 1  # Highest
        assert decision.scores[1].rank == 2
        assert decision.scores[2].rank == 3

    def test_missing_assets_ignored(self) -> None:
        rotator = CapitalRotator(assets=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        features = {"BTCUSDT": _fv("BTCUSDT", adx=50.0, vol_ratio=2.0)}
        decision = rotator.rotate(features)
        assert "BTCUSDT" in decision.allocations
        assert len(decision.scores) == 1

    def test_update_universe(self) -> None:
        rotator = CapitalRotator()
        assert rotator.assets == []
        rotator.update_universe(["BTCUSDT", "ETHUSDT"])
        assert rotator.assets == ["BTCUSDT", "ETHUSDT"]

    def test_empty_assets_default(self) -> None:
        rotator = CapitalRotator()
        assert rotator.assets == []
        decision = rotator.rotate({})
        assert decision.flat_reason == "all_below_threshold"
