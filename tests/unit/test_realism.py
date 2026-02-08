from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.broker.paper import PaperBroker
from argus_py.broker.realism import RealismEngine


def test_commission_matches_binance_taker_default():
    engine = RealismEngine()
    commission = engine.calculate_commission(quantity=0.02, price=50000, is_taker=True)
    assert abs(commission - 0.4) < 1e-9


def test_slippage_scales_with_position_size():
    engine = RealismEngine()
    small = abs(engine.calculate_slippage(price=50000, quantity=0.01, side="BUY"))
    large = abs(engine.calculate_slippage(price=50000, quantity=0.04, side="BUY"))
    assert large > small


def test_funding_for_24h_uses_three_periods():
    engine = RealismEngine()
    funding = engine.calculate_funding(position_value=1000, hours_held=24)
    # 1 bps per 8h -> 3 periods
    assert abs(funding - 0.3) < 1e-9


def test_round_trip_cost_estimation_reasonable():
    engine = RealismEngine()
    costs = engine.estimate_round_trip_cost(
        price=50000,
        quantity=0.02,
        hold_hours=24,
        atr=500,
    )
    assert costs["notional"] == 1000
    assert 1.3 <= costs["total_cost"] <= 1.8
    assert costs["cost_bps"] > 0


def test_get_effective_price_adverse_direction():
    engine = RealismEngine()
    buy_fill = engine.get_effective_price(price=50000, quantity=0.02, side="BUY")
    sell_fill = engine.get_effective_price(price=50000, quantity=0.02, side="SELL")
    assert buy_fill > 50000
    assert sell_fill < 50000


def test_paper_broker_uses_realism_engine_for_commission():
    broker = PaperBroker(start_balance=1000)

    # Make commission path observable.
    broker.realism_engine.calculate_commission = lambda quantity, price, is_taker=True: 1.23

    broker.place_order(
        symbol="BTCUSDT",
        side="BUY",
        price=100.0,
        quantity=1.0,
        sl=98.0,
        tp=104.0,
        timestamp=1.0,
        mark_price=100.0,
    )

    assert broker.trades[-1].commission == 1.23
