"""Tests for PR-I02: Whale momentum boost wiring into Hermes/pipeline.

Covers:
  - is_trend_strong() regime mapping
  - apply_whale_boost_to_signal() pipeline API
  - Pipeline._apply_whale_momentum_boost() integration
  - Pipeline._persist_whale_momentum() telemetry
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.v25.contracts.intelligence import (
    WhaleAlert,
    WhaleDirection,
    WhaleMomentumSignal,
)
from src.engines.hermes.whale_momentum import (
    apply_whale_boost_to_signal,
    compute_whale_momentum,
    is_trend_strong,
)
from src.v25.telemetry.log_writer import log_whale_momentum
from src.v25.db.migrations import TABLE_DDL, INDEX_DDL


_NOW = datetime(2026, 2, 17, 12, 0, 0, tzinfo=timezone.utc)


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Apply v2.5 schema to an in-memory connection."""
    for ddl in TABLE_DDL:
        conn.execute(ddl)
    for ddl in INDEX_DDL:
        conn.execute(ddl)
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    *,
    direction: WhaleDirection = WhaleDirection.OUTFLOW,
    amount_usd: Decimal = Decimal("15000000"),
    symbol: str = "BTC",
    confidence: Decimal = Decimal("0.85"),
    wallet_address: str | None = "0xabc123",
    ts: datetime | None = None,
) -> WhaleAlert:
    return WhaleAlert(
        chain="ethereum",
        symbol=symbol,
        direction=direction,
        amount_asset=Decimal("200"),
        amount_usd=amount_usd,
        wallet_address=wallet_address,
        confidence=confidence,
        source="whale_alert_api",
        timestamp=ts or _NOW,
    )


def _make_bullish_whale() -> WhaleMomentumSignal:
    """Build a bullish whale signal with tier2 boost (0.10)."""
    alerts = [
        _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("50000000"), wallet_address="0xaaaa1234"),
        _make_alert(direction=WhaleDirection.ACCUMULATION, amount_usd=Decimal("30000000"), wallet_address="0xbbbb5678"),
        _make_alert(direction=WhaleDirection.INFLOW, amount_usd=Decimal("5000000"), wallet_address="0xcccc9012"),
    ]
    return compute_whale_momentum(alerts, median_net_flow_30d=Decimal("10000000"))


def _make_neutral_whale() -> WhaleMomentumSignal:
    """Build a neutral whale signal with zero boost."""
    return compute_whale_momentum([])


# ---------------------------------------------------------------------------
# is_trend_strong tests
# ---------------------------------------------------------------------------


class TestIsTrendStrong:
    def test_literal_trend_strong(self):
        """Backward compat: literal 'TREND_STRONG' always qualifies."""
        assert is_trend_strong("TREND_STRONG") is True

    def test_trending_high_conf_high_stability(self):
        """TRENDING + conf >= 0.70 + stability >= 0.60 qualifies."""
        assert is_trend_strong("TRENDING", confidence=0.75, stability=0.65) is True

    def test_trending_low_conf_rejected(self):
        """TRENDING with low confidence does NOT qualify."""
        assert is_trend_strong("TRENDING", confidence=0.50, stability=0.80) is False

    def test_trending_low_stability_rejected(self):
        """TRENDING with low stability does NOT qualify."""
        assert is_trend_strong("TRENDING", confidence=0.80, stability=0.50) is False

    def test_ranging_never_qualifies(self):
        """RANGING never qualifies, even with high numbers."""
        assert is_trend_strong("RANGING", confidence=0.95, stability=0.95) is False

    def test_volatile_never_qualifies(self):
        assert is_trend_strong("VOLATILE", confidence=0.95, stability=0.95) is False

    def test_crisis_never_qualifies(self):
        assert is_trend_strong("CRISIS", confidence=0.95, stability=0.95) is False

    def test_boundary_exact_thresholds(self):
        """Exact boundary values qualify (>= not >)."""
        assert is_trend_strong("TRENDING", confidence=0.70, stability=0.60) is True

    def test_boundary_just_below_conf(self):
        assert is_trend_strong("TRENDING", confidence=0.699, stability=0.60) is False


# ---------------------------------------------------------------------------
# apply_whale_boost_to_signal tests
# ---------------------------------------------------------------------------


class TestApplyWhaleBoostToSignal:
    def test_boost_applied_in_trend_strong(self):
        """Boost applied when regime qualifies and confidence >= 0.30."""
        whale = _make_bullish_whale()
        boosted, applied, reason = apply_whale_boost_to_signal(
            base_confidence=0.65,
            whale=whale,
            regime="TRENDING",
            regime_confidence=0.80,
            regime_stability=0.70,
        )
        assert applied is True
        assert reason == "whale_boost_applied"
        assert boosted > 0.65  # boosted by sqs_boost
        assert boosted <= 1.0

    def test_no_boost_in_ranging(self):
        """No boost when regime is RANGING."""
        whale = _make_bullish_whale()
        boosted, applied, reason = apply_whale_boost_to_signal(
            base_confidence=0.65,
            whale=whale,
            regime="RANGING",
            regime_confidence=0.80,
            regime_stability=0.70,
        )
        assert applied is False
        assert reason == "regime_not_trend_strong"
        assert boosted == 0.65

    def test_defensive_override_low_confidence(self):
        """GR-14: base confidence < 0.30 → no boost regardless of whale."""
        whale = _make_bullish_whale()
        boosted, applied, reason = apply_whale_boost_to_signal(
            base_confidence=0.20,
            whale=whale,
            regime="TRENDING",
            regime_confidence=0.80,
            regime_stability=0.70,
        )
        assert applied is False
        assert reason == "defensive_override"
        assert boosted == 0.20

    def test_no_boost_neutral_whale(self):
        """No boost when whale signal has zero sqs_boost."""
        whale = _make_neutral_whale()
        boosted, applied, reason = apply_whale_boost_to_signal(
            base_confidence=0.65,
            whale=whale,
            regime="TRENDING",
            regime_confidence=0.80,
            regime_stability=0.70,
        )
        assert applied is False
        assert reason == "no_whale_boost"
        assert boosted == 0.65

    def test_boost_capped_at_1(self):
        """Boosted confidence never exceeds 1.0."""
        whale = _make_bullish_whale()
        boosted, applied, reason = apply_whale_boost_to_signal(
            base_confidence=0.95,
            whale=whale,
            regime="TRENDING",
            regime_confidence=0.80,
            regime_stability=0.70,
        )
        assert applied is True
        assert boosted == 1.0

    def test_trending_low_stability_no_boost(self):
        """TRENDING with low stability: regime not strong enough."""
        whale = _make_bullish_whale()
        boosted, applied, reason = apply_whale_boost_to_signal(
            base_confidence=0.65,
            whale=whale,
            regime="TRENDING",
            regime_confidence=0.80,
            regime_stability=0.40,
        )
        assert applied is False
        assert reason == "regime_not_trend_strong"


# ---------------------------------------------------------------------------
# Telemetry persistence tests
# ---------------------------------------------------------------------------


class TestWhaleBoostTelemetry:
    def _make_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        _apply_schema(conn)
        return conn

    def test_log_whale_momentum_writes_row(self):
        """log_whale_momentum inserts a row that can be read back."""
        conn = self._make_db()
        log_whale_momentum(
            conn,
            symbol="BTC",
            net_flow_usd_24h=-50000000.0,
            exchange_reserve_change_pct=0.0,
            is_bullish_flow=True,
            is_bearish_flow=False,
            momentum_score=0.85,
            sqs_boost=0.10,
            size_modifier=1.2,
            stablecoin_mint_usd_24h=0.0,
            timestamp=_NOW.isoformat(),
        )
        conn.commit()
        rows = conn.execute("SELECT symbol, momentum_score, sqs_boost FROM whale_momentum_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "BTC"
        assert rows[0][1] == pytest.approx(0.85)
        assert rows[0][2] == pytest.approx(0.10)

    def test_log_whale_momentum_from_signal(self):
        """Can log whale momentum from a computed WhaleMomentumSignal."""
        conn = self._make_db()
        whale = _make_bullish_whale()
        log_whale_momentum(
            conn,
            symbol=str(whale.symbol),
            net_flow_usd_24h=float(whale.net_flow_usd_24h),
            exchange_reserve_change_pct=float(whale.exchange_reserve_change_pct),
            is_bullish_flow=bool(whale.is_bullish_flow),
            is_bearish_flow=bool(whale.is_bearish_flow),
            momentum_score=float(whale.momentum_score),
            sqs_boost=float(whale.sqs_boost),
            size_modifier=float(whale.size_modifier),
            stablecoin_mint_usd_24h=float(whale.stablecoin_mint_usd_24h),
            timestamp=_NOW.isoformat(),
        )
        conn.commit()
        rows = conn.execute("SELECT COUNT(*) FROM whale_momentum_log").fetchone()
        assert rows[0] == 1


# ---------------------------------------------------------------------------
# Pipeline integration tests (using mock pipeline)
# ---------------------------------------------------------------------------


class TestPipelineWhaleBoostIntegration:
    """Test _apply_whale_momentum_boost and _persist_whale_momentum via mocks."""

    def _make_mock_pipeline(self, *, whale_alerts: list | None = None, v25_conn=None):
        """Create a mock pipeline with whale boost methods."""
        from src.main import ArgusPipeline

        # We can't instantiate ArgusPipeline easily (needs config etc.),
        # so we test the static-like methods directly by calling them as unbound.
        pipeline = MagicMock(spec=ArgusPipeline)
        pipeline._whale_alerts = whale_alerts or []
        pipeline.v25_conn = v25_conn
        pipeline._LOG = MagicMock()
        # Bind real methods
        pipeline._apply_whale_momentum_boost = ArgusPipeline._apply_whale_momentum_boost.__get__(pipeline)
        pipeline._persist_whale_momentum = ArgusPipeline._persist_whale_momentum.__get__(pipeline)
        return pipeline

    def test_no_alerts_returns_signal_unchanged(self):
        """With no whale alerts, signal passes through unchanged."""
        pipeline = self._make_mock_pipeline()
        signal = MagicMock()
        signal.confidence = 0.70
        regime = MagicMock()
        regime.regime = "TRENDING"
        regime.confidence = 0.80
        regime.stability = 0.70

        result = pipeline._apply_whale_momentum_boost(
            signal=signal, regime_state=regime, symbol="BTC", now=_NOW
        )
        assert result is signal  # Same object, not modified

    def test_boost_applied_with_alerts(self):
        """With bullish alerts and strong trend, signal confidence is boosted."""
        alerts = [
            _make_alert(direction=WhaleDirection.OUTFLOW, amount_usd=Decimal("50000000"), wallet_address="0xaaaa1234"),
            _make_alert(direction=WhaleDirection.ACCUMULATION, amount_usd=Decimal("30000000"), wallet_address="0xbbbb5678"),
            _make_alert(direction=WhaleDirection.INFLOW, amount_usd=Decimal("5000000")),
        ]
        pipeline = self._make_mock_pipeline(whale_alerts=alerts)
        signal = MagicMock()
        signal.confidence = 0.70
        boosted_signal = MagicMock()
        signal.model_copy.return_value = boosted_signal
        regime = MagicMock()
        regime.regime = "TRENDING"
        regime.confidence = 0.80
        regime.stability = 0.70

        result = pipeline._apply_whale_momentum_boost(
            signal=signal, regime_state=regime, symbol="BTC", now=_NOW
        )
        # Signal should have been boosted (model_copy called)
        signal.model_copy.assert_called_once()
        call_kwargs = signal.model_copy.call_args
        update = call_kwargs[1]["update"]
        assert "confidence" in update
        assert update["confidence"] > 0.70

    def test_persist_whale_momentum_with_db(self):
        """_persist_whale_momentum writes to DB when connection available."""
        conn = sqlite3.connect(":memory:")
        _apply_schema(conn)
        pipeline = self._make_mock_pipeline(v25_conn=conn)
        whale = _make_bullish_whale()
        pipeline._persist_whale_momentum(whale=whale, now=_NOW)
        rows = conn.execute("SELECT COUNT(*) FROM whale_momentum_log").fetchone()
        assert rows[0] == 1

    def test_persist_whale_momentum_no_db(self):
        """_persist_whale_momentum silently skips when no DB."""
        pipeline = self._make_mock_pipeline(v25_conn=None)
        whale = _make_bullish_whale()
        # Should not raise
        pipeline._persist_whale_momentum(whale=whale, now=_NOW)
