from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.autopilot.autopilot import AutoPilotEngine, AutoPilotMode, TradePosition
from argus_py.autopilot.config import AutoPilotConfig


def _pos(mode=AutoPilotMode.PULSE, entry=100.0, qty=1.0, hwm=110.0):
    return TradePosition(
        symbol="BTCUSDT",
        entry_price=entry,
        quantity=qty,
        mode=mode,
        entry_time=0.0,
        high_water_mark=hwm,
        engine="orion",
    )


def test_corse_vs_pulse_stop_thresholds():
    engine = AutoPilotEngine()

    corse = _pos(mode=AutoPilotMode.CORSE, entry=100.0)
    pulse = _pos(mode=AutoPilotMode.PULSE, entry=100.0)

    # -6% should stop pulse (5%), but not corse (8%)
    s_pulse = engine.evaluate("BTCUSDT", 94.0, 70, "HOLD", pulse, 10000, 0)
    s_corse = engine.evaluate("BTCUSDT", 94.0, 70, "HOLD", corse, 10000, 0)

    assert s_pulse.action == "SELL"
    assert s_corse.action != "SELL"


def test_stop_loss_trigger_at_correct_threshold():
    engine = AutoPilotEngine()
    pos = _pos(mode=AutoPilotMode.PULSE, entry=100.0)
    sig = engine.evaluate("BTCUSDT", 94.9, 70, "HOLD", pos, 10000, 0)
    assert sig.action == "SELL"
    assert "Stop Loss" in sig.reason


def test_trim_profit_trigger_at_correct_threshold():
    engine = AutoPilotEngine()
    pos = _pos(mode=AutoPilotMode.PULSE, entry=100.0)
    sig = engine.evaluate("BTCUSDT", 111.0, 70, "HOLD", pos, 10000, 0)
    assert sig.action == "TRIM"
    assert abs(sig.quantity - 0.3) < 1e-9
    assert sig.trim_percentage == 0.3


def test_trailing_stop_activation_and_trigger():
    engine = AutoPilotEngine()
    pos = _pos(mode=AutoPilotMode.PULSE, entry=100.0, hwm=110.0)

    # pnl=+8%, dd from hwm ~1.82% > pulse trail distance 1.5%.
    sig = engine.evaluate("BTCUSDT", 108.0, 70, "HOLD", pos, 10000, 0)
    assert sig.action == "SELL"
    assert "Trailing Stop" in sig.reason


def test_position_sizing_respects_one_percent_risk_rule():
    cfg = AutoPilotConfig(max_risk_per_trade_pct=1.0)
    engine = AutoPilotEngine(config=cfg)

    sig = engine.evaluate(
        symbol="BTCUSDT",
        current_price=50000,
        council_score=80,
        council_action="ACCUMULATE",
        existing_position=None,
        portfolio_equity=10000,
        cash_available=5000,
    )

    assert sig.action == "BUY"

    # risk_amount=100, assumed_stop=5% => position_value=2000 -> qty=0.04
    assert abs(sig.quantity - 0.04) < 1e-9


def test_update_high_water_mark_increases_only():
    engine = AutoPilotEngine()
    pos = _pos(hwm=105.0)

    updated = engine.update_high_water_mark(pos, 108.0)
    assert updated.high_water_mark == 108.0

    updated = engine.update_high_water_mark(pos, 107.0)
    assert updated.high_water_mark == 108.0


def test_entry_rejected_when_score_too_low():
    engine = AutoPilotEngine()
    sig = engine.evaluate("BTCUSDT", 50000, 50, "ACCUMULATE", None, 10000, 5000)
    assert sig.action == "HOLD"
    assert "Score too low" in sig.reason


def test_entry_rejected_without_buy_action():
    engine = AutoPilotEngine()
    sig = engine.evaluate("BTCUSDT", 50000, 80, "HOLD", None, 10000, 5000)
    assert sig.action == "HOLD"
    assert "No buy signal" in sig.reason


def test_thesis_broken_exit():
    engine = AutoPilotEngine()
    pos = _pos(mode=AutoPilotMode.CORSE, entry=100.0, hwm=102.0)
    sig = engine.evaluate("BTCUSDT", 99.0, 50, "HOLD", pos, 10000, 0)
    assert sig.action == "SELL"
    assert "Thesis Broken" in sig.reason
