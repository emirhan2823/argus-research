from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.data.market_state import Bar
from argus_py.strategy.tophunter_short import detect_pivot_low_indices, evaluate_tophunter_short_v1


def _bars_for_pivot_break():
    # Pivot low at idx=4 (left=2, right=2), latest close breaks below pivot low.
    lows = [10.0, 9.0, 8.0, 7.0, 6.0, 7.0, 8.0, 7.5, 5.5]
    highs = [12.0, 11.5, 10.5, 9.5, 8.5, 9.5, 10.5, 9.0, 7.2]
    closes = [11.0, 10.0, 9.0, 8.0, 7.0, 8.0, 9.0, 8.0, 5.8]
    bars = []
    ts = 1_700_000_000.0
    for i in range(len(lows)):
        bars.append(
            Bar(
                timestamp=ts + i * 3600.0,
                open=closes[i],
                high=highs[i],
                low=lows[i],
                close=closes[i],
                volume=1000.0 + i,
            )
        )
    return bars


def test_detect_pivot_low_indices_finds_expected_index():
    bars = _bars_for_pivot_break()
    idxs = detect_pivot_low_indices(bars, left=2, right=2)
    assert 4 in idxs


def test_regime_rejection_when_adx_is_high():
    bars = _bars_for_pivot_break()
    signal = evaluate_tophunter_short_v1(bars, adx_value=25.0, max_adx=20.0, left=2, right=2)
    assert signal.decision == "NO_GO"
    assert signal.reason_code == "REJECT_REGIME_ADX"


def test_signal_go_when_pivot_break_and_adx_filter_pass():
    bars = _bars_for_pivot_break()
    signal = evaluate_tophunter_short_v1(bars, adx_value=15.0, max_adx=20.0, left=2, right=2)
    assert signal.decision == "GO"
    assert signal.direction == "SELL"
    assert signal.stop_price is not None and signal.entry_price is not None
    assert signal.stop_price > signal.entry_price
    assert signal.tp2_price is not None and signal.tp2_price < signal.entry_price
