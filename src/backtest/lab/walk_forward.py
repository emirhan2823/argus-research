"""Walk-forward window generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def generate_windows(
    *,
    n_rows: int,
    train_size: int,
    test_size: int,
    step_size: int,
    expanding: bool = False,
) -> list[WalkForwardWindow]:
    if train_size <= 0 or test_size <= 0 or step_size <= 0:
        raise ValueError("train_size/test_size/step_size must be positive")
    if train_size + test_size > n_rows:
        return []

    windows: list[WalkForwardWindow] = []
    train_start = 0
    train_end = train_size
    while train_end + test_size <= n_rows:
        test_start = train_end
        test_end = test_start + test_size
        windows.append(
            WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        if expanding:
            train_end += step_size
        else:
            train_start += step_size
            train_end += step_size
    return windows
