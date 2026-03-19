from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.portfolio.manager import CorrelationBucket, PortfolioLimits, PortfolioManager, SymbolConfig


def _pm(limits=None):
    symbols = [
        SymbolConfig("BTCUSDT", bucket=CorrelationBucket.BTC_ECOSYSTEM, max_position_pct=30, priority=1),
        SymbolConfig("ETHUSDT", bucket=CorrelationBucket.ETH_ECOSYSTEM, max_position_pct=25, priority=1),
        SymbolConfig("SOLUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, max_position_pct=15, priority=2),
        SymbolConfig("BNBUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, max_position_pct=15, priority=2),
    ]
    return PortfolioManager(symbols=symbols, limits=limits)


def test_multi_symbol_state_tracking_and_bucket_exposure():
    pm = _pm()
    pm.update_state(positions={"BTCUSDT": 3000, "SOLUSDT": 1000}, cash=6000)

    assert pm.state.total_equity == 10000
    assert pm.state.exposure_by_bucket["BTC_ECOSYSTEM"] == 3000
    assert pm.state.exposure_by_bucket["ALTCOIN_MAJOR"] == 1000


def test_can_open_position_symbol_not_configured():
    pm = _pm()
    pm.update_state({}, cash=10000)
    ok, reason = pm.can_open_position("DOGEUSDT", 500)
    assert ok is False
    assert reason == "Symbol not configured"


def test_correlation_bucket_limit_enforced():
    limits = PortfolioLimits(max_correlated_exposure_pct=40)
    pm = _pm(limits=limits)
    pm.update_state(positions={"SOLUSDT": 3500}, cash=6500)  # equity=10000

    ok, reason = pm.can_open_position("BNBUSDT", 1000)
    assert ok is False
    assert "correlation limit" in reason


def test_position_size_limit_checked_correctly():
    pm = _pm()
    pm.update_state(positions={}, cash=10000)

    # ETH max 25% -> 2500
    ok, reason = pm.can_open_position("ETHUSDT", 2600)
    assert ok is False
    assert "Exceeds max position size" in reason


def test_cash_reserve_maintained():
    limits = PortfolioLimits(min_cash_reserve_pct=10)
    pm = _pm(limits=limits)
    pm.update_state(positions={"BTCUSDT": 3000}, cash=7000)

    ok, reason = pm.can_open_position("ETHUSDT", 6500)  # would leave 500 < 1000 reserve
    assert ok is False
    assert reason == "Would violate cash reserve"


def test_max_open_positions_limit():
    limits = PortfolioLimits(max_open_positions=1)
    pm = _pm(limits=limits)
    pm.update_state(positions={"BTCUSDT": 3000}, cash=7000)

    ok, reason = pm.can_open_position("ETHUSDT", 1000)
    assert ok is False
    assert "Max positions" in reason


def test_daily_trade_limit_enforced():
    limits = PortfolioLimits(max_daily_trades=1)
    pm = _pm(limits=limits)
    pm.update_state(positions={}, cash=10000)
    pm.state.daily_trades = 1

    ok, reason = pm.can_open_position("ETHUSDT", 1000)
    assert ok is False
    assert reason == "Max daily trades reached"


def test_opportunity_ranking_by_priority_then_score():
    pm = _pm()
    pm.update_state(positions={}, cash=10000)

    signals = {"SOLUSDT": 90, "BTCUSDT": 70, "ETHUSDT": 75}
    decisions = pm.rank_opportunities(signals)

    assert [d.symbol for d in decisions][:2] == ["ETHUSDT", "BTCUSDT"]
    # Same priority (1), ETH score higher than BTC.


def test_score_below_threshold_skipped():
    pm = _pm()
    pm.update_state(positions={}, cash=10000)

    decisions = pm.rank_opportunities({"BTCUSDT": 60})
    assert len(decisions) == 1
    assert decisions[0].action == "SKIP"


def test_can_open_position_success_path():
    pm = _pm()
    pm.update_state(positions={"BTCUSDT": 2000}, cash=8000)

    ok, reason = pm.can_open_position("ETHUSDT", 2000)
    assert ok is True
    assert reason == "OK"


def test_rank_opportunity_blocked_reason_when_hold():
    limits = PortfolioLimits(max_open_positions=1)
    pm = _pm(limits=limits)
    pm.update_state(positions={"BTCUSDT": 5000}, cash=5000)

    decisions = pm.rank_opportunities({"ETHUSDT": 90})
    assert decisions[0].action == "HOLD"
    assert decisions[0].blocked_by is not None
