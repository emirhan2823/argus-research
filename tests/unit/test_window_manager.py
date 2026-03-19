from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.window_manager import WalkForwardWindowManager



def test_window_manager_strict_slices_without_lookahead() -> None:
    mgr = WalkForwardWindowManager(train_bars=120, test_bars=30, step_bars=30)
    windows = mgr.split_index(total_bars=300)

    assert len(windows) == 6
    for w in windows:
        assert w.train_end <= w.test_start
        assert (w.train_end - w.train_start) == 120
        assert (w.test_end - w.test_start) == 30

    WalkForwardWindowManager.validate_no_lookahead(windows)



def test_window_manager_split_timestamps_monotonic_only() -> None:
    mgr = WalkForwardWindowManager(train_bars=3, test_bars=2, step_bars=1)
    ts = pd.date_range("2026-01-01", periods=12, freq="h")
    tw = mgr.split_timestamps(list(ts))
    assert tw
    assert tw[0].train_start == ts[0]
    assert tw[0].train_end == ts[2]
    assert tw[0].test_start == ts[3]
    assert tw[0].test_end == ts[4]

    bad = list(ts)
    bad[3], bad[4] = bad[4], bad[3]
    with pytest.raises(ValueError):
        mgr.split_timestamps(bad)



def test_window_manager_frame_split_shapes() -> None:
    mgr = WalkForwardWindowManager(train_bars=50, test_bars=10, step_bars=10)
    frame = pd.DataFrame({"x": range(150)})
    chunks = mgr.split_frame(frame)
    assert len(chunks) == 10
    train, test = chunks[0]
    assert len(train) == 50
    assert len(test) == 10
    assert train["x"].iloc[-1] == 49
    assert test["x"].iloc[0] == 50
