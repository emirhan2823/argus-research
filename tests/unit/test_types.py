"""Phase 1 Gate — Tests for all pydantic v2 data models."""

import math
from datetime import datetime, timezone

import pytest

from src.core.types import (
    Decision,
    EngineSignal,
    ExecutionResult,
    FeatureVector,
    NewsSentiment,
    PortfolioState,
    Position,
    RegimeState,
    RiskVerdict,
    TelemetryEvent,
    TradeRecord,
)

NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_feature_vector(**overrides) -> FeatureVector:
    """Helper: build a valid crypto FeatureVector with sensible defaults."""
    defaults = dict(
        timestamp=NOW,
        symbol="BTCUSDT",
        asset_class="crypto",
        # Volatility (6)
        atr_14=500.0, atr_14_pct=0.01, atr_ratio_5_20=1.2,
        realized_vol_20d=0.45, parkinson_vol=0.42, bb_width=0.03,
        # Trend (6)
        adx_14=30.0, price_vs_ma200=1.05, ema_21_vs_55=0.02,
        lr_slope_20=0.001, supertrend_dir=1, aroon_osc=60.0,
        # Momentum (5)
        rsi_14=55.0, bb_pct_b=0.6, roc_10=0.02, willr_14=-40.0, cci_20=80.0,
        # Volume (5)
        volume_ratio=1.2, obv_slope_10=100.0, vwap_dev_pct=0.005,
        cmf_20=0.1, volume_delta=50.0,
        # Microstructure (5)
        spread_pct=0.001,
        orderbook_imbalance=0.1,
        trade_flow_imbalance=0.05,
        depth_ratio=1.0,
        large_trade_ratio=0.15,
        # Crypto-Native (7)
        funding_rate=0.0001,
        funding_pctile_30d=50.0,
        oi_change_4h_pct=0.02,
        oi_change_24h_pct=0.05,
        liquidation_est=1000000.0,
        long_short_ratio=1.1,
        basis_pct=0.002,
        # Cross-Asset (4)
        btc_dominance_delta_24h=-0.5,
        btc_eth_corr_30d=0.85,
        total_mcap_momentum=0.03,
        stablecoin_flow=500000.0,
        # Statistical (4)
        return_autocorr_20=0.05, hurst_exponent=0.55,
        entropy_50=3.2, frac_diff_price=42000.0,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def _make_equity_feature_vector(**overrides) -> FeatureVector:
    """Helper: build a valid us_equity FeatureVector (no crypto-native fields)."""
    defaults = dict(
        timestamp=NOW,
        symbol="AAPL",
        asset_class="us_equity",
        # Volatility
        atr_14=3.5, atr_14_pct=0.02, atr_ratio_5_20=1.1,
        realized_vol_20d=0.25, parkinson_vol=0.22, bb_width=0.04,
        # Trend
        adx_14=28.0, price_vs_ma200=1.10, ema_21_vs_55=0.01,
        lr_slope_20=0.002, supertrend_dir=1, aroon_osc=70.0,
        # Momentum
        rsi_14=60.0, bb_pct_b=0.7, roc_10=0.03, willr_14=-30.0, cci_20=100.0,
        # Volume
        volume_ratio=1.5, obv_slope_10=200.0, vwap_dev_pct=0.003,
        cmf_20=0.15, volume_delta=80.0,
        # Microstructure — only spread, rest None
        spread_pct=0.0005,
        # Crypto-native: all None (default)
        # Statistical
        return_autocorr_20=0.03, hurst_exponent=0.48,
        entropy_50=3.0, frac_diff_price=175.0,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


# ── FeatureVector Tests ───────────────────────────────────────────


class TestFeatureVector:
    def test_create_crypto_feature_vector(self):
        fv = _make_feature_vector()
        assert fv.symbol == "BTCUSDT"
        assert fv.asset_class == "crypto"
        assert fv.atr_14 == 500.0
        assert fv.funding_rate == 0.0001

    def test_create_equity_feature_vector(self):
        fv = _make_equity_feature_vector()
        assert fv.symbol == "AAPL"
        assert fv.asset_class == "us_equity"
        assert fv.funding_rate is None
        assert fv.basis_pct is None
        assert fv.orderbook_imbalance is None

    def test_rejects_nan_in_required_field(self):
        with pytest.raises(ValueError, match="NaN not allowed"):
            _make_feature_vector(atr_14=float("nan"))

    def test_rejects_nan_in_multiple_required_fields(self):
        with pytest.raises(ValueError, match="NaN not allowed"):
            _make_feature_vector(rsi_14=float("nan"))

    def test_allows_none_for_optional_fields(self):
        fv = _make_feature_vector(chronos_forecast_1h=None, lgbm_direction=None)
        assert fv.chronos_forecast_1h is None
        assert fv.lgbm_direction is None

    def test_frozen(self):
        fv = _make_feature_vector()
        with pytest.raises(Exception):  # ValidationError for frozen
            fv.atr_14 = 999.0  # type: ignore[misc]

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            _make_feature_vector(bogus_field=42.0)

    def test_hermes_sentiment_fields(self):
        fv = _make_feature_vector(
            hermes_sentiment_score=-45.0,
            hermes_sentiment_confidence=0.8,
            hermes_urgency="HIGH",
        )
        assert fv.hermes_sentiment_score == -45.0
        assert fv.hermes_urgency == "HIGH"


# ── RegimeState Tests ─────────────────────────────────────────────


class TestRegimeState:
    def test_valid_regime(self):
        rs = RegimeState(
            regime="TRENDING", confidence=0.8, stability=0.7,
            candles_in_regime=10, rule_regime="TRENDING", ml_regime="TRENDING",
            timestamp=NOW,
        )
        assert rs.regime == "TRENDING"

    def test_rejects_confidence_above_1(self):
        with pytest.raises(Exception):
            RegimeState(
                regime="TRENDING", confidence=1.5, stability=0.7,
                candles_in_regime=10, rule_regime="TRENDING", ml_regime="TRENDING",
                timestamp=NOW,
            )

    def test_rejects_negative_candles(self):
        with pytest.raises(Exception):
            RegimeState(
                regime="TRENDING", confidence=0.8, stability=0.7,
                candles_in_regime=-1, rule_regime="TRENDING", ml_regime="TRENDING",
                timestamp=NOW,
            )

    def test_hermes_override_field(self):
        rs = RegimeState(
            regime="CRISIS", confidence=0.95, stability=0.1,
            candles_in_regime=0, rule_regime="VOLATILE", ml_regime="VOLATILE",
            hermes_override="CRISIS", timestamp=NOW,
        )
        assert rs.hermes_override == "CRISIS"

    def test_frozen(self):
        rs = RegimeState(
            regime="RANGING", confidence=0.6, stability=0.8,
            candles_in_regime=5, rule_regime="RANGING", ml_regime="RANGING",
            timestamp=NOW,
        )
        with pytest.raises(Exception):
            rs.regime = "TRENDING"  # type: ignore[misc]


# ── EngineSignal Tests ────────────────────────────────────────────


class TestEngineSignal:
    def test_valid_signal(self):
        sig = EngineSignal(
            engine="TITAN", sub_strategy="trend_follow",
            asset_class="crypto", symbol="BTCUSDT",
            bias="long", confidence=0.7, stop_distance=0.02,
            expected_return=0.05, atr=500.0,
        )
        assert sig.engine == "TITAN"

    def test_rejects_stop_distance_above_010(self):
        with pytest.raises(Exception):
            EngineSignal(
                engine="TITAN", sub_strategy="trend_follow",
                asset_class="crypto", symbol="BTCUSDT",
                bias="long", confidence=0.7, stop_distance=0.15,
                expected_return=0.05, atr=500.0,
            )

    def test_rejects_zero_stop_distance(self):
        with pytest.raises(Exception):
            EngineSignal(
                engine="TITAN", sub_strategy="trend_follow",
                asset_class="crypto", symbol="BTCUSDT",
                bias="long", confidence=0.7, stop_distance=0.0,
                expected_return=0.05, atr=500.0,
            )

    def test_hermes_engine(self):
        sig = EngineSignal(
            engine="HERMES", sub_strategy="news_sentiment",
            asset_class="us_equity", symbol="TSLA",
            bias="short", confidence=0.75, stop_distance=0.05,
            expected_return=0.03, atr=8.0,
        )
        assert sig.engine == "HERMES"
        assert sig.asset_class == "us_equity"


# ── Decision Tests ────────────────────────────────────────────────


class TestDecision:
    def _make_decision(self, **overrides):
        defaults = dict(
            action="long", asset_class="crypto", symbol="BTCUSDT",
            execution_mode="auto", position_size=0.05, leverage=1.5,
            stop_loss=0.02, take_profit=0.04, confidence=0.7,
            engine="TITAN", reason="trend confirmed", timestamp=NOW,
        )
        defaults.update(overrides)
        return Decision(**defaults)

    def test_valid_decision(self):
        d = self._make_decision()
        assert d.action == "long"

    def test_rejects_leverage_above_20(self):
        with pytest.raises(Exception):
            self._make_decision(leverage=21.0)

    def test_rejects_position_size_above_015(self):
        with pytest.raises(Exception):
            self._make_decision(position_size=0.20)

    def test_advisory_decision(self):
        d = self._make_decision(
            execution_mode="advisory",
            asset_class="bist",
            symbol="THYAO",
            suggested_entry_price=185.0,
            tp_levels=[190.0, 195.0, 200.0],
            conditional_alerts=["If price drops below 180, close position"],
        )
        assert d.execution_mode == "advisory"
        assert d.tp_levels == [190.0, 195.0, 200.0]
        assert len(d.conditional_alerts) == 1

    def test_adjust_sl_action(self):
        d = self._make_decision(action="adjust_sl")
        assert d.action == "adjust_sl"

    def test_frozen(self):
        d = self._make_decision()
        with pytest.raises(Exception):
            d.action = "short"  # type: ignore[misc]


# ── NewsSentiment Tests ───────────────────────────────────────────


class TestNewsSentiment:
    def test_valid_sentiment(self):
        ns = NewsSentiment(
            headline="SEC approves Bitcoin ETF",
            source="coindesk",
            asset_class="crypto",
            affected_symbols=["BTCUSDT", "ETHUSDT"],
            sentiment_score=75.0,
            confidence=0.9,
            urgency="HIGH",
            action="ALERT_ONLY",
            reasoning="Positive regulatory development",
            timestamp=NOW,
        )
        assert ns.sentiment_score == 75.0
        assert ns.urgency == "HIGH"

    def test_rejects_score_above_100(self):
        with pytest.raises(Exception):
            NewsSentiment(
                headline="test", source="test", asset_class="crypto",
                affected_symbols=["BTC"], sentiment_score=150.0,
                confidence=0.5, urgency="LOW", action="NONE",
                reasoning="test", timestamp=NOW,
            )

    def test_rejects_score_below_minus_100(self):
        with pytest.raises(Exception):
            NewsSentiment(
                headline="test", source="test", asset_class="crypto",
                affected_symbols=["BTC"], sentiment_score=-150.0,
                confidence=0.5, urgency="LOW", action="NONE",
                reasoning="test", timestamp=NOW,
            )

    def test_close_position_action(self):
        ns = NewsSentiment(
            headline="Exchange hacked",
            source="theblock",
            asset_class="crypto",
            affected_symbols=["BTCUSDT"],
            sentiment_score=-85.0,
            confidence=0.95,
            urgency="CRITICAL",
            action="CLOSE_POSITION",
            reasoning="Exchange security breach",
            timestamp=NOW,
        )
        assert ns.action == "CLOSE_POSITION"
        assert ns.urgency == "CRITICAL"


# ── RiskVerdict Tests ─────────────────────────────────────────────


class TestRiskVerdict:
    def test_valid_verdict(self):
        rv = RiskVerdict(approved=True, reason="all checks passed", risk_level=0)
        assert rv.approved is True

    def test_rejects_risk_level_above_4(self):
        with pytest.raises(Exception):
            RiskVerdict(approved=False, reason="test", risk_level=5)

    def test_rejects_negative_risk_level(self):
        with pytest.raises(Exception):
            RiskVerdict(approved=False, reason="test", risk_level=-1)


# ── ExecutionResult Tests ─────────────────────────────────────────


class TestExecutionResult:
    def test_auto_execution(self):
        er = ExecutionResult(
            success=True, execution_mode="auto", order_id="ORD123",
            fill_price=42000.0, fill_quantity=0.1, slippage=0.0001,
            fees=4.2, sl_order_id="SL123", reason="filled", timestamp=NOW,
        )
        assert er.execution_mode == "auto"
        assert er.sl_order_id == "SL123"

    def test_advisory_execution(self):
        er = ExecutionResult(
            success=True, execution_mode="advisory",
            advisory_message="BUY THYAO at 185 TL, SL: 180, TP: 195/200",
            reason="advisory signal sent", timestamp=NOW,
        )
        assert er.execution_mode == "advisory"
        assert er.advisory_message is not None


# ── Position Tests ────────────────────────────────────────────────


class TestPosition:
    def test_auto_position(self):
        p = Position(
            symbol="BTCUSDT", asset_class="crypto", side="long",
            size=0.1, entry_price=42000.0, current_price=42500.0,
            unrealized_pnl=50.0, unrealized_pnl_pct=0.012,
            sl_price=41000.0, entry_time=NOW, duration_hours=2.5,
            exchange_sl_order_id="SL123", execution_mode="auto",
        )
        assert p.asset_class == "crypto"

    def test_advisory_position(self):
        p = Position(
            symbol="THYAO", asset_class="bist", side="long",
            size=100.0, entry_price=185.0, current_price=190.0,
            unrealized_pnl=500.0, unrealized_pnl_pct=0.027,
            sl_price=180.0, entry_time=NOW, duration_hours=48.0,
            exchange_sl_order_id="MANUAL", execution_mode="advisory",
        )
        assert p.execution_mode == "advisory"


# ── PortfolioState Tests ──────────────────────────────────────────


class TestPortfolioState:
    def test_with_allocations(self):
        ps = PortfolioState(
            total_equity=10000.0, available_balance=7000.0,
            positions=[], has_positions=False,
            daily_pnl=50.0, daily_pnl_pct=0.005,
            drawdown=0.01, peak_equity=10100.0,
            trades_today=3, consecutive_losses=0, equity_ma_20d=9800.0,
            allocation_crypto_pct=0.30, allocation_equity_pct=0.20,
            allocation_commodity_pct=0.10, allocation_cash_pct=0.40,
            timestamp=NOW,
        )
        assert ps.allocation_crypto_pct + ps.allocation_equity_pct + \
               ps.allocation_commodity_pct + ps.allocation_cash_pct == 1.0


# ── TradeRecord Tests ─────────────────────────────────────────────


class TestTradeRecord:
    def test_with_asset_class_and_execution_mode(self):
        tr = TradeRecord(
            trade_id="T001", symbol="NVDA", asset_class="us_equity", side="long",
            entry_time=NOW, exit_time=NOW, entry_price=800.0, exit_price=820.0,
            size=10.0, pnl=200.0, pnl_pct=0.025, fees=5.0, slippage=0.5,
            net_pnl_pct=0.024, regime_at_entry="TRENDING", regime_at_exit="TRENDING",
            engine="TITAN", sub_strategy="trend_follow",
            confidence_at_entry=0.72, stop_distance=0.03, duration_hours=24.0,
            features_at_entry={"adx_14": 30.0}, reason_entry="trend confirmed",
            reason_exit="TP hit", execution_mode="auto",
        )
        assert tr.asset_class == "us_equity"
        assert tr.execution_mode == "auto"


# ── TelemetryEvent Tests ─────────────────────────────────────────


class TestTelemetryEvent:
    def test_valid_event(self):
        te = TelemetryEvent(
            event_type="candle_close", timestamp=NOW, run_id="RUN001",
        )
        assert te.event_type == "candle_close"

    def test_with_inputs_hash(self):
        te = TelemetryEvent(
            event_type="decision_made", timestamp=NOW, run_id="RUN001",
            inputs_hash="abc123",
        )
        assert te.inputs_hash == "abc123"
