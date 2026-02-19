"""Tests for v2.5 correlation contracts (Phase A)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest

from src.v25.contracts.correlation import (
    CorrelationHealth,
    CorrelationPair,
    CorrelationSignal,
)


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------


class TestFrozen:
    """All v2.5 contracts must be frozen (immutable)."""

    def test_correlation_pair_is_frozen(self):
        pair = CorrelationPair(
            pair_id="BTCUSDT_ETHUSDT",
            symbol_a="BTCUSDT",
            symbol_b="ETHUSDT",
            correlation=Decimal("0.85"),
            spread_zscore=Decimal("1.2"),
        )
        with pytest.raises(Exception):
            pair.pair_id = "CHANGED"  # type: ignore[misc]

    def test_correlation_signal_is_frozen(self):
        sig = CorrelationSignal(
            pair_id="BTCUSDT_ETHUSDT",
            signal_type="MEAN_REVERSION",
            direction_a="LONG",
            direction_b="SHORT",
            confidence=Decimal("0.75"),
            spread_zscore_at_signal=Decimal("2.1"),
            target_zscore=Decimal("0.0"),
            stop_zscore=Decimal("3.0"),
            reason="Spread exceeds 2σ",
        )
        with pytest.raises(Exception):
            sig.confidence = Decimal("0.5")  # type: ignore[misc]

    def test_correlation_health_is_frozen(self):
        health = CorrelationHealth(
            total_pairs=10,
            active_pairs=8,
            cointegrated_count=3,
            avg_correlation=Decimal("0.72"),
            last_update_age_seconds=Decimal("5.0"),
        )
        with pytest.raises(Exception):
            health.total_pairs = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NaN / Infinity rejection
# ---------------------------------------------------------------------------


class TestNaNRejection:
    """Decimal fields must reject NaN and Infinity (via ArgusModel validator)."""

    def test_pair_rejects_nan_correlation(self):
        with pytest.raises(Exception):
            CorrelationPair(
                pair_id="X_Y",
                symbol_a="X",
                symbol_b="Y",
                correlation=Decimal("NaN"),
                spread_zscore=Decimal("0"),
            )

    def test_pair_rejects_inf_spread_zscore(self):
        with pytest.raises(Exception):
            CorrelationPair(
                pair_id="X_Y",
                symbol_a="X",
                symbol_b="Y",
                correlation=Decimal("0.5"),
                spread_zscore=Decimal("Infinity"),
            )

    def test_signal_rejects_nan_confidence(self):
        with pytest.raises(Exception):
            CorrelationSignal(
                pair_id="X_Y",
                signal_type="MEAN_REVERSION",
                direction_a="LONG",
                direction_b="SHORT",
                confidence=Decimal("NaN"),
                spread_zscore_at_signal=Decimal("2.0"),
                target_zscore=Decimal("0.0"),
                stop_zscore=Decimal("3.0"),
                reason="test",
            )

    def test_health_rejects_nan_avg_correlation(self):
        with pytest.raises(Exception):
            CorrelationHealth(
                total_pairs=1,
                active_pairs=1,
                cointegrated_count=0,
                avg_correlation=Decimal("NaN"),
                last_update_age_seconds=Decimal("0"),
            )


# ---------------------------------------------------------------------------
# Bounds validation
# ---------------------------------------------------------------------------


class TestBoundsValidation:
    """Field constraints must be enforced."""

    def test_correlation_out_of_range_high(self):
        with pytest.raises(Exception):
            CorrelationPair(
                pair_id="X_Y",
                symbol_a="X",
                symbol_b="Y",
                correlation=Decimal("1.5"),
                spread_zscore=Decimal("0"),
            )

    def test_correlation_out_of_range_low(self):
        with pytest.raises(Exception):
            CorrelationPair(
                pair_id="X_Y",
                symbol_a="X",
                symbol_b="Y",
                correlation=Decimal("-1.5"),
                spread_zscore=Decimal("0"),
            )

    def test_correlation_boundary_values_accepted(self):
        """Exact -1 and +1 should be accepted."""
        p1 = CorrelationPair(
            pair_id="A_B",
            symbol_a="A",
            symbol_b="B",
            correlation=Decimal("1"),
            spread_zscore=Decimal("0"),
        )
        assert p1.correlation == Decimal("1")

        p2 = CorrelationPair(
            pair_id="A_B",
            symbol_a="A",
            symbol_b="B",
            correlation=Decimal("-1"),
            spread_zscore=Decimal("0"),
        )
        assert p2.correlation == Decimal("-1")

    def test_confidence_out_of_range(self):
        with pytest.raises(Exception):
            CorrelationSignal(
                pair_id="X_Y",
                signal_type="MEAN_REVERSION",
                direction_a="LONG",
                direction_b="SHORT",
                confidence=Decimal("1.5"),
                spread_zscore_at_signal=Decimal("2.0"),
                target_zscore=Decimal("0.0"),
                stop_zscore=Decimal("3.0"),
                reason="test",
            )

    def test_health_negative_total_pairs_rejected(self):
        with pytest.raises(Exception):
            CorrelationHealth(
                total_pairs=-1,
                active_pairs=0,
                cointegrated_count=0,
                avg_correlation=Decimal("0"),
                last_update_age_seconds=Decimal("0"),
            )

    def test_health_negative_update_age_rejected(self):
        with pytest.raises(Exception):
            CorrelationHealth(
                total_pairs=0,
                active_pairs=0,
                cointegrated_count=0,
                avg_correlation=Decimal("0"),
                last_update_age_seconds=Decimal("-1"),
            )


# ---------------------------------------------------------------------------
# Extra fields forbidden
# ---------------------------------------------------------------------------


class TestExtraFieldsForbidden:
    """extra='forbid' must reject unknown fields."""

    def test_pair_rejects_extra(self):
        with pytest.raises(Exception):
            CorrelationPair(
                pair_id="X_Y",
                symbol_a="X",
                symbol_b="Y",
                correlation=Decimal("0.5"),
                spread_zscore=Decimal("0"),
                unknown_field="boom",  # type: ignore[call-arg]
            )

    def test_signal_rejects_extra(self):
        with pytest.raises(Exception):
            CorrelationSignal(
                pair_id="X_Y",
                signal_type="MEAN_REVERSION",
                direction_a="LONG",
                direction_b="SHORT",
                confidence=Decimal("0.75"),
                spread_zscore_at_signal=Decimal("2.0"),
                target_zscore=Decimal("0.0"),
                stop_zscore=Decimal("3.0"),
                reason="test",
                extra_field=42,  # type: ignore[call-arg]
            )

    def test_health_rejects_extra(self):
        with pytest.raises(Exception):
            CorrelationHealth(
                total_pairs=1,
                active_pairs=1,
                cointegrated_count=0,
                avg_correlation=Decimal("0.5"),
                last_update_age_seconds=Decimal("1"),
                bogus="nope",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# Happy-path construction
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Valid data should construct without error."""

    def test_correlation_pair_happy(self):
        pair = CorrelationPair(
            pair_id="BTCUSDT_ETHUSDT",
            symbol_a="BTCUSDT",
            symbol_b="ETHUSDT",
            correlation=Decimal("0.85"),
            spread_zscore=Decimal("1.2"),
            half_life_bars=Decimal("42"),
            is_cointegrated=True,
            cointegration_pvalue=Decimal("0.02"),
            regime="CONVERGING",
        )
        assert pair.pair_id == "BTCUSDT_ETHUSDT"
        assert pair.is_cointegrated is True
        assert pair.regime == "CONVERGING"

    def test_correlation_signal_happy(self):
        sig = CorrelationSignal(
            pair_id="BTCUSDT_ETHUSDT",
            signal_type="MEAN_REVERSION",
            direction_a="LONG",
            direction_b="SHORT",
            confidence=Decimal("0.9"),
            spread_zscore_at_signal=Decimal("2.5"),
            target_zscore=Decimal("0.0"),
            stop_zscore=Decimal("3.5"),
            reason="Spread > 2.5σ with confirmed cointegration",
        )
        assert sig.signal_type == "MEAN_REVERSION"

    def test_correlation_health_happy(self):
        health = CorrelationHealth(
            total_pairs=10,
            active_pairs=8,
            cointegrated_count=3,
            avg_correlation=Decimal("0.72"),
            min_half_life=Decimal("15.5"),
            last_update_age_seconds=Decimal("2.3"),
        )
        assert health.total_pairs == 10
        assert health.min_half_life == Decimal("15.5")

    def test_correlation_pair_defaults(self):
        """Optional fields default correctly."""
        pair = CorrelationPair(
            pair_id="A_B",
            symbol_a="A",
            symbol_b="B",
            correlation=Decimal("0"),
            spread_zscore=Decimal("0"),
        )
        assert pair.half_life_bars is None
        assert pair.is_cointegrated is False
        assert pair.cointegration_pvalue is None
        assert pair.regime == "STABLE"
