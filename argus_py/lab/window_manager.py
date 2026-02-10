from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import pandas as pd


@dataclass(frozen=True)
class WindowSlice:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class TimeWindowSlice:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


class WalkForwardWindowManager:
    """Strict walk-forward slicer with no-lookahead guarantees."""

    def __init__(
        self,
        train_bars: int,
        test_bars: int,
        step_bars: int,
    ) -> None:
        if train_bars <= 0 or test_bars <= 0 or step_bars <= 0:
            raise ValueError("train/test/step bars must be > 0")
        self.train_bars = int(train_bars)
        self.test_bars = int(test_bars)
        self.step_bars = int(step_bars)

    def split_index(self, total_bars: int) -> List[WindowSlice]:
        if total_bars <= 0:
            return []

        windows: List[WindowSlice] = []
        train_start = 0

        while True:
            train_end = train_start + self.train_bars
            test_start = train_end
            test_end = test_start + self.test_bars

            if test_end > total_bars:
                break

            windows.append(
                WindowSlice(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            train_start += self.step_bars

        return windows

    def split_timestamps(self, timestamps: Sequence[pd.Timestamp]) -> List[TimeWindowSlice]:
        if not timestamps:
            return []

        ts = pd.to_datetime(pd.Index(timestamps), utc=False)
        if not ts.is_monotonic_increasing:
            raise ValueError("timestamps must be monotonic increasing")

        index_windows = self.split_index(len(ts))
        time_windows: List[TimeWindowSlice] = []
        for win in index_windows:
            # End fields represent inclusive last timestamp in each segment.
            time_windows.append(
                TimeWindowSlice(
                    train_start=ts[win.train_start],
                    train_end=ts[win.train_end - 1],
                    test_start=ts[win.test_start],
                    test_end=ts[win.test_end - 1],
                )
            )
        return time_windows

    def split_frame(self, frame: pd.DataFrame) -> List[tuple[pd.DataFrame, pd.DataFrame]]:
        windows = self.split_index(len(frame))
        out: List[tuple[pd.DataFrame, pd.DataFrame]] = []
        for win in windows:
            train_df = frame.iloc[win.train_start : win.train_end].copy()
            test_df = frame.iloc[win.test_start : win.test_end].copy()
            out.append((train_df, test_df))
        return out

    @staticmethod
    def validate_no_lookahead(windows: Iterable[WindowSlice]) -> None:
        for win in windows:
            if win.train_end > win.test_start:
                raise ValueError("lookahead detected: train overlaps test")
            if win.train_start >= win.train_end:
                raise ValueError("invalid train range")
            if win.test_start >= win.test_end:
                raise ValueError("invalid test range")
