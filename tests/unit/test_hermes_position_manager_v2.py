from __future__ import annotations

from argus_py.broker.paper import PaperBroker
from argus_py.ops.hermes_position_manager_v2 import HermesPositionManagerV2, urgency_from_score


def _open_position(broker: PaperBroker) -> None:
    ok, _ = broker.execute_strategy(
        symbol="BTCUSDT",
        decision="GO",
        direction="BUY",
        price=100.0,
        timestamp=1_700_000_000.0,
        risk_pct=0.005,
        leverage=1.0,
        custom_sl_price=95.0,
        custom_tp_price=110.0,
    )
    assert ok is True


def test_urgency_mapping() -> None:
    assert urgency_from_score(-85.0) == "CRITICAL"
    assert urgency_from_score(65.0) == "HIGH"
    assert urgency_from_score(45.0) == "MEDIUM"
    assert urgency_from_score(10.0) == "LOW"


def test_hermes_position_manager_adjust_and_close() -> None:
    broker = PaperBroker(start_balance=1000.0, mode="paper")
    _open_position(broker)
    mgr = HermesPositionManagerV2(broker)

    out_sl = mgr.apply(
        symbol="BTCUSDT",
        sentiment_score=-60.0,
        urgency="HIGH",
        market_price=99.0,
        timestamp=1_700_000_060.0,
    )
    assert out_sl.handled is True
    assert out_sl.action == "ADJUST_SL"
    assert broker.details["BTCUSDT"].sl_price is not None

    out_tp = mgr.apply(
        symbol="BTCUSDT",
        sentiment_score=70.0,
        urgency="HIGH",
        market_price=101.0,
        timestamp=1_700_000_120.0,
    )
    assert out_tp.handled is True
    assert out_tp.action == "ADJUST_TP"
    assert broker.details["BTCUSDT"].tp_price is not None

    out_close = mgr.apply(
        symbol="BTCUSDT",
        sentiment_score=-90.0,
        urgency="CRITICAL",
        market_price=98.0,
        timestamp=1_700_000_180.0,
    )
    assert out_close.handled is True
    assert out_close.action == "CLOSE_POSITION"
    assert "BTCUSDT" not in broker.details
